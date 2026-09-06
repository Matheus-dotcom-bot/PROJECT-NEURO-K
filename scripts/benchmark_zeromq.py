#!/usr/bin/env python3
"""Collect measured ZeroMQ offload observations using the shared benchmark schema.

The worker is expected to be reachable at --worker. Every measured repetition
is an independent ZEROMQ_WORKER observation. No simulated rows are generated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
from pathlib import Path

import numpy as np

from orchestrator import NeuroKOrchestrator

FIELDNAMES = [
    "timestamp_utc", "status", "execution", "vercel_url", "n", "dtype",
    "seed", "t_compute_s", "result_checksum", "matrix_bytes",
    "http_elapsed_s", "error",
]


def checksum(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def run(args: argparse.Namespace) -> None:
    args.results.parent.mkdir(parents=True, exist_ok=True)
    write_header = not args.results.exists() or args.results.stat().st_size == 0
    orchestrator = NeuroKOrchestrator(args.worker, timeout_ms=args.timeout_ms)
    try:
        with args.results.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            for n in args.sizes:
                for dtype_name in args.dtypes:
                    dtype = np.dtype(dtype_name)
                    seed = n * 1000 + (32 if dtype == np.dtype("float32") else 64)
                    rng = np.random.default_rng(seed)
                    a = rng.random((n, n)).astype(dtype, copy=False)
                    b = rng.random((n, n)).astype(dtype, copy=False)
                    for _ in range(args.warmup_runs):
                        orchestrator._remote_once(n, dtype, a, b)
                    for repetition in range(args.repetitions):
                        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        try:
                            t0 = time.perf_counter()
                            remote = orchestrator._remote_once(n, dtype, a, b)
                            elapsed = time.perf_counter() - t0
                            writer.writerow({
                                "timestamp_utc": timestamp,
                                "status": "MEASURED",
                                "execution": "ZEROMQ_WORKER",
                                "vercel_url": "",
                                "n": n,
                                "dtype": str(dtype),
                                "seed": seed,
                                "t_compute_s": remote["t_remote_compute"],
                                "result_checksum": checksum(remote["C"]),
                                "matrix_bytes": a.nbytes + b.nbytes,
                                "http_elapsed_s": elapsed,
                                "error": "",
                            })
                            handle.flush()
                            print(f"MEASURED ZEROMQ_WORKER n={n} dtype={dtype} repetition={repetition + 1}")
                        except Exception as exc:
                            writer.writerow({
                                "timestamp_utc": timestamp,
                                "status": "ERROR",
                                "execution": "ZEROMQ_WORKER",
                                "vercel_url": "",
                                "n": n,
                                "dtype": str(dtype),
                                "seed": seed,
                                "t_compute_s": "",
                                "result_checksum": "",
                                "matrix_bytes": a.nbytes + b.nbytes,
                                "http_elapsed_s": "",
                                "error": str(exc),
                            })
                            handle.flush()
                            print(f"ERROR ZEROMQ_WORKER n={n} dtype={dtype}: {exc}")
    finally:
        orchestrator.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", default="tcp://127.0.0.1:5555")
    parser.add_argument("--sizes", nargs="+", type=int, default=[256, 512, 1024, 2048])
    parser.add_argument("--dtypes", nargs="+", choices=["float32", "float64"], default=["float32", "float64"])
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmup-runs", type=int, default=2)
    parser.add_argument("--timeout-ms", type=int, default=120_000)
    parser.add_argument("--results", type=Path, default=Path("results/zeromq/benchmark-results-zeromq.csv"))
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmup_runs < 0 or args.timeout_ms < 1:
        parser.error("repetitions >= 1, warmup-runs >= 0 and timeout-ms >= 1 are required")
    run(args)


if __name__ == "__main__":
    main()
