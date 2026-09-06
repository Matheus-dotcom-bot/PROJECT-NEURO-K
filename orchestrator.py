"""PROJECT-NEURO-K adaptive offloading orchestrator.

The orchestrator calibrates the local machine and worker instead of assuming
fixed GFLOPS/bandwidth. Matrix payloads are sent as raw NumPy bytes over
ZeroMQ; control messages use small JSON metadata only.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

import numpy as np
import psutil
import zmq


@dataclass
class Calibration:
    local_seconds: float
    worker_seconds: float
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
            if not ready.get("ok"):
                raise RuntimeError(ready.get("error", "worker rejected request"))
            t_control = time.perf_counter() - t0

            a_bytes = np.ascontiguousarray(a).tobytes()
            b_bytes = np.ascontiguousarray(b).tobytes()

            t0 = time.perf_counter()
            socket.send(a_bytes)
            socket.recv_json()
            t_send_a = time.perf_counter() - t0

            t0 = time.perf_counter()
            socket.send(b_bytes)
            socket.recv_json()
            t_send_b = time.perf_counter() - t0

            t0 = time.perf_counter()
            meta = socket.recv_json()
            t_wait_result_meta = time.perf_counter() - t0

            socket.send_string("SEND_RESULT")
            t0 = time.perf_counter()
            result_bytes = socket.recv()
            t_receive_c = time.perf_counter() - t0

            c = np.frombuffer(result_bytes, dtype=dtype).reshape(n, n)

            return {
                "C": c,
                "t_control": t_control,
                "t_send_a": t_send_a,
                "t_send_b": t_send_b,
                "t_wait_result_meta": t_wait_result_meta,
                "t_receive_c": t_receive_c,
                "t_remote_deserialize": meta["t_deserialize"],
                "t_remote_compute": meta["t_compute"],
                "t_remote_serialize": meta["t_serialize"],
            }
        finally:
            socket.close()

    def calibrate(self, n: int = 128, repetitions: int = 3) -> Calibration:
        dtype = np.dtype(np.float64)
        a = np.random.default_rng(0).random((n, n), dtype=np.float64)
        b = np.random.default_rng(1).random((n, n), dtype=np.float64)

        # Warm-up local BLAS.
        np.matmul(a, b)

        local_times = []
        for _ in range(repetitions):
            t0 = time.perf_counter()
            np.matmul(a, b)
            local_times.append(time.perf_counter() - t0)

        remote_times = []
        transfer_rates = []
        rtts = []

        for _ in range(repetitions):
            t0 = time.perf_counter()
            result = self._remote_once(n, dtype, a, b)
            total = time.perf_counter() - t0
            remote_times.append(total)

            payload = len(a.tobytes()) + len(b.tobytes()) + len(result["C"].tobytes())
            transfer_time = (
                result["t_send_a"] + result["t_send_b"] + result["t_receive_c"]
            )
            if transfer_time > 0:
                transfer_rates.append(payload / transfer_time)

            rtts.append(result["t_control"])

        self.calibration = Calibration(
            local_seconds=float(np.median(local_times)),
            worker_seconds=float(np.median(remote_times)),
            bandwidth_bytes_per_second=float(np.median(transfer_rates)),
            rtt_seconds=float(np.median(rtts)),
        )
        return self.calibration

    def predict(self, n: int, dtype=np.dtype(np.float64)) -> tuple[bool, str]:
        if self.calibration is None:
            raise RuntimeError("run calibrate() before predict()")

        required = self.required_bytes(n, dtype)
        if self.available_memory() < int(required * 1.2):
            return True, "RAM_PRESSURE"

        # Scale the measured compute time approximately by N^3. This is a
        # prediction, not a claim that matmul is exactly linear in N^3.
        scale = (n / 128.0) ** 3
        local_est = self.calibration.local_seconds * scale
        remote_compute_est = self.calibration.worker_seconds * scale

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

        # If RAM pressure is the reason, allocating a complete local C is not
        # safe. For a controlled benchmark, use the normal baseline only when
        # memory permits it.
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
                "t_send_a": remote["t_send_a"],
                "t_send_b": remote["t_send_b"],
                "t_receive_c": remote["t_receive_c"],
                "t_remote_deserialize": remote["t_remote_deserialize"],
                "t_remote_compute": remote["t_remote_compute"],
                "t_remote_serialize": remote["t_remote_serialize"],
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", default="tcp://127.0.0.1:5555")
    parser.add_argument("--sizes", nargs="+", type=int, default=[256, 512, 1024, 2048])
    args = parser.parse_args()

    orchestrator = NeuroKOrchestrator(args.worker)
    try:
        calibration = orchestrator.calibrate()
        print("Calibration:", calibration)
        for n in args.sizes:
            try:
                print(orchestrator.benchmark(n))
            except Exception as exc:
                print({"n": n, "error": str(exc)})
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
