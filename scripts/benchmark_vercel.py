#!/usr/bin/env python3
"""Collect measured baseline observations from the Vercel API.

This collector deliberately writes a separate CSV. It never modifies the
historical benchmark-results.csv, which contains simulated observations.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FIELDNAMES = [
    "timestamp_utc",
    "status",
    "execution",
    "vercel_url",
    "n",
    "dtype",
    "seed",
    "t_compute_s",
    "result_checksum",
    "matrix_bytes",
    "http_elapsed_s",
    "error",
]


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"

    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=120) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def append_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the Vercel NEURO-K baseline")
    parser.add_argument("--url", required=True, help="Base Vercel URL, for example https://example.vercel.app")
    parser.add_argument("--sizes", nargs="+", type=int, default=[256, 512, 1024, 2048])
    parser.add_argument("--dtypes", nargs="+", choices=["float32", "float64"], default=["float64"])
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmup-runs", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--results", default="benchmark-results-vercel.csv")
    parser.add_argument("--metadata", default="benchmark-metadata-vercel.json")
    args = parser.parse_args()

    if args.repetitions <= 0 or args.warmup_runs < 0:
        parser.error("repetitions must be positive and warmup-runs cannot be negative")

    base_url = args.url.rstrip("/")
    health = request_json(f"{base_url}/health")
    runtime = request_json(f"{base_url}/runtime")

    metadata = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "execution": "VERCEL_FUNCTION",
        "vercel_url": base_url,
        "health": health,
        "runtime": runtime,
        "sizes": args.sizes,
        "dtypes": args.dtypes,
        "repetitions": args.repetitions,
        "warmup_runs": args.warmup_runs,
        "seed": args.seed,
    }
    Path(args.metadata).write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    results = Path(args.results)

    for dtype in args.dtypes:
        for n in args.sizes:
            for _ in range(args.warmup_runs):
                request_json(f"{base_url}/benchmark", {"n": n, "dtype": dtype, "seed": args.seed})

            for repetition in range(args.repetitions):
                seed = args.seed + repetition
                timestamp = datetime.now(timezone.utc).isoformat()
                started = time.perf_counter()
                try:
                    response = request_json(
                        f"{base_url}/benchmark",
                        {"n": n, "dtype": dtype, "seed": seed},
                    )
                    http_elapsed = time.perf_counter() - started
                    append_row(
                        results,
                        {
                            "timestamp_utc": timestamp,
                            "status": response.get("status", "ERROR"),
                            "execution": response.get("execution", "VERCEL_FUNCTION"),
                            "vercel_url": base_url,
                            "n": n,
                            "dtype": dtype,
                            "seed": seed,
                            "t_compute_s": response.get("t_compute_s", ""),
                            "result_checksum": response.get("result_checksum", ""),
                            "matrix_bytes": response.get("matrix_bytes", ""),
                            "http_elapsed_s": http_elapsed,
                            "error": "",
                        },
                    )
                    print(f"MEASURED {dtype} N={n} rep={repetition + 1}/{args.repetitions} http={http_elapsed:.6f}s")
                except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    http_elapsed = time.perf_counter() - started
                    append_row(
                        results,
                        {
                            "timestamp_utc": timestamp,
                            "status": "ERROR",
                            "execution": "VERCEL_FUNCTION",
                            "vercel_url": base_url,
                            "n": n,
                            "dtype": dtype,
                            "seed": seed,
                            "t_compute_s": "",
                            "result_checksum": "",
                            "matrix_bytes": "",
                            "http_elapsed_s": http_elapsed,
                            "error": str(exc),
                        },
                    )
                    print(f"ERROR {dtype} N={n} rep={repetition + 1}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
