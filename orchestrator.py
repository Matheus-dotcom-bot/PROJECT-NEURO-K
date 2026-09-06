"""PROJECT-NEURO-K adaptive offloading orchestrator.

The orchestrator calibrates the local machine and worker instead of assuming
fixed GFLOPS/bandwidth. Matrix payloads are sent as raw NumPy bytes over
ZeroMQ; control messages use small JSON metadata only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psutil
import zmq
from threadpoolctl import threadpool_info


@dataclass
class Calibration:
    local_seconds: float
    worker_compute_seconds: float
    bandwidth_bytes_per_second: float
    rtt_seconds: float


class NeuroKOrchestrator:
    def __init__(self, worker_addr: str, timeout_ms: int = 10_000) -> None:
        self.worker_addr = worker_addr
        self.timeout_ms = timeout_ms
        self.context = zmq.Context()
        self.calibration: Calibration | None = None

    def close(self) -> None:
        self.context.term()

    @staticmethod
    def available_memory() -> int:
        return int(psutil.virtual_memory().available)

    @staticmethod
    def matrix_bytes(n: int, dtype: np.dtype) -> int:
        return n * n * dtype.itemsize

    @staticmethod
    def required_bytes(n: int, dtype: np.dtype) -> int:
        # A, B and C. This is a lower-bound estimate; BLAS implementations
        # may require additional workspace.
        return 3 * NeuroKOrchestrator.matrix_bytes(n, dtype)

    def _socket(self) -> zmq.Socket:
        socket = self.context.socket(zmq.REQ)
        socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(self.worker_addr)
        return socket

    def _remote_once(self, n: int, dtype: np.dtype, a: np.ndarray, b: np.ndarray) -> dict:
        socket = self._socket()
        try:
            t0 = time.perf_counter()
            socket.send_json({"op": "matmul", "n": n, "dtype": str(dtype)})
            ready = socket.recv_json()
            t_control = time.perf_counter() - t0
            if not ready.get("ok"):
                raise RuntimeError(ready.get("error", "worker rejected request"))

            t0 = time.perf_counter()
            a_bytes = np.ascontiguousarray(a).tobytes()
            b_bytes = np.ascontiguousarray(b).tobytes()
            t_serialization = time.perf_counter() - t0

            t0 = time.perf_counter()
            socket.send(a_bytes)
            ack_a = socket.recv_json()
            t_send_a = time.perf_counter() - t0
            if not ack_a.get("ok"):
                raise RuntimeError(ack_a.get("error", "worker rejected A"))

            t0 = time.perf_counter()
            socket.send(b_bytes)
            meta = socket.recv_json()
            t_send_b = time.perf_counter() - t0
            if not meta.get("ok"):
                raise RuntimeError(meta.get("error", "worker rejected B"))

            socket.send_string("SEND_RESULT")
            t0 = time.perf_counter()
            result_bytes = socket.recv()
            t_receive_c = time.perf_counter() - t0

            expected = self.matrix_bytes(n, dtype)
            if len(result_bytes) != expected:
                raise RuntimeError("worker returned an invalid result size")

            c = np.frombuffer(result_bytes, dtype=dtype).reshape(n, n)

            return {
                "C": c,
                "t_control": t_control,
                "t_serialization": t_serialization,
                "t_send_a": t_send_a,
                "t_send_b": t_send_b,
                "t_receive_c": t_receive_c,
                "t_remote_deserialize": meta["t_deserialize"],
                "t_remote_compute": meta["t_compute"],
                "t_remote_serialize": meta["t_serialize"],
            }
        finally:
            socket.close()

    def calibrate(self, n: int = 128, repetitions: int = 3) -> Calibration:
        if repetitions < 1:
            raise ValueError("repetitions must be >= 1")

        dtype = np.dtype(np.float64)
        a = np.random.default_rng(0).random((n, n), dtype=np.float64)
        b = np.random.default_rng(1).random((n, n), dtype=np.float64)

        np.matmul(a, b)  # warm-up local BLAS

        local_times = []
        for _ in range(repetitions):
            t0 = time.perf_counter()
            np.matmul(a, b)
            local_times.append(time.perf_counter() - t0)

        worker_compute_times = []
        transfer_rates = []
        rtts = []

        for _ in range(repetitions):
            result = self._remote_once(n, dtype, a, b)
            worker_compute_times.append(result["t_remote_compute"])

            payload = len(a.tobytes()) + len(b.tobytes()) + len(result["C"].tobytes())
            transfer_time = result["t_send_a"] + result["t_send_b"] + result["t_receive_c"]
            if transfer_time > 0:
                transfer_rates.append(payload / transfer_time)

            rtts.append(result["t_control"])

        self.calibration = Calibration(
            local_seconds=float(np.median(local_times)),
            worker_compute_seconds=float(np.median(worker_compute_times)),
            bandwidth_bytes_per_second=float(np.median(transfer_rates)),
            rtt_seconds=float(np.median(rtts)),
        )
        return self.calibration

    def predict(self, n: int, dtype=np.dtype(np.float64)) -> tuple[bool, str]:
        if self.calibration is None:
            raise RuntimeError("run calibrate() before predict()")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError("n must be a positive integer")

        required = self.required_bytes(n, dtype)
        if self.available_memory() < int(required * 1.2):
            return True, "RAM_PRESSURE"

        scale = (n / 128.0) ** 3
        local_est = self.calibration.local_seconds * scale
        remote_compute_est = self.calibration.worker_compute_seconds * scale

        payload = self.matrix_bytes(n, dtype) * 3
        transfer_est = payload / max(self.calibration.bandwidth_bytes_per_second, 1.0)
        offload_est = remote_compute_est + transfer_est + self.calibration.rtt_seconds

        if offload_est < local_est:
            return True, "PREDICTED_FASTER"
        return False, "PREDICTED_LOCAL_FASTER"

    def benchmark(self, n: int, dtype=np.dtype(np.float64)) -> dict:
        dtype = np.dtype(dtype)
        should_offload, reason = self.predict(n, dtype)

        rng = np.random.default_rng(n)
        a = rng.random((n, n)).astype(dtype, copy=False)
        b = rng.random((n, n)).astype(dtype, copy=False)

        local_available = self.available_memory() >= int(self.required_bytes(n, dtype) * 1.2)
        t_local = None
        c_local = None
        if local_available:
            t0 = time.perf_counter()
            c_local = np.matmul(a, b)
            t_local = time.perf_counter() - t0

        if not should_offload:
            return {
                "n": n,
                "dtype": str(dtype),
                "decision": "LOCAL",
                "reason": reason,
                "t_local": t_local,
                "t_offload_total": None,
                "gain_percent": None,
            }

        t0 = time.perf_counter()
        remote = self._remote_once(n, dtype, a, b)
        t_total = time.perf_counter() - t0

        if c_local is not None and not np.allclose(c_local, remote["C"], rtol=1e-5, atol=1e-8):
            raise RuntimeError("local and remote results differ")

        return {
            "n": n,
            "dtype": str(dtype),
            "decision": "OFFLOAD",
            "reason": reason,
            "t_local": t_local,
            "t_offload_total": t_total,
            "gain_percent": None if t_local is None else ((t_local - t_total) / t_local) * 100,
            "metrics": {
                "t_serialization": remote["t_serialization"],
                "t_send_a": remote["t_send_a"],
                "t_send_b": remote["t_send_b"],
                "t_receive_c": remote["t_receive_c"],
                "t_remote_deserialize": remote["t_remote_deserialize"],
                "t_remote_compute": remote["t_remote_compute"],
                "t_remote_serialize": remote["t_remote_serialize"],
            },
        }


def runtime_metadata(worker: str, sizes: list[int], repetitions: int, warmup_runs: int) -> dict:
    """Capture enough environment information to reproduce a measurement."""
    return {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "numpy": np.__version__,
        "pyzmq": zmq.__version__,
        "available_memory_bytes_at_start": int(psutil.virtual_memory().available),
        "blas_runtime": threadpool_info(),
        "blas_environment": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS",
            )
            if os.environ.get(name) is not None
        },
        "worker": worker,
        "sizes": sizes,
        "repetitions": repetitions,
        "warmup_runs": warmup_runs,
    }


def append_result(path: Path, result: dict) -> None:
    fieldnames = [
        "timestamp", "status", "n", "dtype", "decision", "reason",
        "t_local_s", "t_serialization_s", "t_send_a_s", "t_send_b_s",
        "t_remote_deserialize_s", "t_remote_compute_s", "t_remote_serialize_s",
        "t_receive_c_s", "t_offload_total_s", "gain_percent", "error",
    ]
    metrics = result.get("metrics", {})
    row = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "MEASURED",
        "n": result.get("n"),
        "dtype": result.get("dtype"),
        "decision": result.get("decision"),
        "reason": result.get("reason"),
        "t_local_s": result.get("t_local"),
        "t_serialization_s": metrics.get("t_serialization"),
        "t_send_a_s": metrics.get("t_send_a"),
        "t_send_b_s": metrics.get("t_send_b"),
        "t_remote_deserialize_s": metrics.get("t_remote_deserialize"),
        "t_remote_compute_s": metrics.get("t_remote_compute"),
        "t_remote_serialize_s": metrics.get("t_remote_serialize"),
        "t_receive_c_s": metrics.get("t_receive_c"),
        "t_offload_total_s": result.get("t_offload_total"),
        "gain_percent": result.get("gain_percent"),
        "error": None,
    }
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", default="tcp://127.0.0.1:5555")
    parser.add_argument("--sizes", nargs="+", type=int, default=[256, 512, 1024, 2048])
    parser.add_argument("--results", type=Path, default=Path("benchmark-results.csv"))
    parser.add_argument("--metadata", type=Path, default=None)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--warmup-runs", type=int, default=1)
    args = parser.parse_args()

    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")
    if args.warmup_runs < 0:
        parser.error("--warmup-runs must be >= 0")

    orchestrator = NeuroKOrchestrator(args.worker)
    try:
        if args.metadata is not None:
            args.metadata.parent.mkdir(parents=True, exist_ok=True)
            args.metadata.write_text(
                json.dumps(
                    runtime_metadata(args.worker, args.sizes, args.repetitions, args.warmup_runs),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

        calibration = orchestrator.calibrate()
        print("Calibration:", calibration)
        for n in args.sizes:
            for warmup_index in range(args.warmup_runs):
                orchestrator.benchmark(n)
                print(f"Warm-up {warmup_index + 1}/{args.warmup_runs} for N={n}")

            for repetition in range(args.repetitions):
                try:
                    result = orchestrator.benchmark(n)
                    append_result(args.results, result)
                    print(f"Measurement {repetition + 1}/{args.repetitions}:", result)
                except Exception as exc:
                    error = {"n": n, "error": str(exc)}
                    print(error)
                    append_result(
                        args.results,
                        {
                            "n": n,
                            "dtype": "float64",
                            "decision": "ERROR",
                            "reason": "EXECUTION_ERROR",
                            "error": str(exc),
                        },
                    )
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
