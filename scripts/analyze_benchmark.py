#!/usr/bin/env python3
"""Analyze NEURO-K benchmark observations without mixing execution environments.

The raw benchmark schema is intentionally shared by VERCEL_FUNCTION and
ZEROMQ_WORKER. Each input row represents one measured repetition. The analyzer
emits one aggregate row per execution/n/dtype group and preserves the execution
label so cross-environment comparisons can be made later, never implicitly.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

REQUIRED_COLUMNS = {
    "execution",
    "n",
    "dtype",
    "status",
    "t_compute_s",
    "http_elapsed_s",
}

OUTPUT_COLUMNS = [
    "execution",
    "n",
    "dtype",
    "samples",
    "errors",
    "compute_mean_s",
    "compute_median_s",
    "compute_std_s",
    "compute_p95_s",
    "transport_mean_s",
    "transport_median_s",
    "transport_std_s",
    "transport_p95_s",
    "overhead_mean_s",
    "overhead_median_s",
    "overhead_std_s",
    "overhead_p95_s",
    "overhead_pct_of_transport",
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def stats(values: list[float]) -> tuple[float, float, float, float]:
    if not values:
        return math.nan, math.nan, math.nan, math.nan
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return statistics.fmean(values), statistics.median(values), std, percentile(values, 0.95)


def fmt(value: float) -> str:
    return "" if math.isnan(value) else f"{value:.9f}"


def analyze(input_path: Path) -> list[dict[str, str]]:
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

        groups: dict[tuple[str, int, str], dict[str, list[float] | int]] = {}
        for row in reader:
            key = (row["execution"], int(row["n"]), row["dtype"])
            group = groups.setdefault(key, {"compute": [], "transport": [], "errors": 0})
            status = (row.get("status") or "").upper()
            try:
                compute = float(row["t_compute_s"])
                transport = float(row["http_elapsed_s"])
            except (TypeError, ValueError):
                group["errors"] = int(group["errors"]) + 1
                continue
            if status == "ERROR":
                group["errors"] = int(group["errors"]) + 1
                continue
            group["compute"].append(compute)  # type: ignore[union-attr]
            group["transport"].append(transport)  # type: ignore[union-attr]

    output: list[dict[str, str]] = []
    for (execution, n, dtype), group in sorted(groups.items()):
        compute = group["compute"]  # type: ignore[assignment]
        transport = group["transport"]  # type: ignore[assignment]
        overhead = [max(t - c, 0.0) for t, c in zip(transport, compute)]
        cm, cmed, cs, cp95 = stats(compute)
        tm, tmed, ts, tp95 = stats(transport)
        om, omed, os, op95 = stats(overhead)
        overhead_pct = (om / tm * 100.0) if tm and not math.isnan(tm) else math.nan
        output.append({
            "execution": execution,
            "n": str(n),
            "dtype": dtype,
            "samples": str(len(compute)),
            "errors": str(group["errors"]),
            "compute_mean_s": fmt(cm),
            "compute_median_s": fmt(cmed),
            "compute_std_s": fmt(cs),
            "compute_p95_s": fmt(cp95),
            "transport_mean_s": fmt(tm),
            "transport_median_s": fmt(tmed),
            "transport_std_s": fmt(ts),
            "transport_p95_s": fmt(tp95),
            "overhead_mean_s": fmt(om),
            "overhead_median_s": fmt(omed),
            "overhead_std_s": fmt(os),
            "overhead_p95_s": fmt(op95),
            "overhead_pct_of_transport": fmt(overhead_pct),
        })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate NEURO-K benchmark observations")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = analyze(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"WROTE {args.output} ({len(rows)} groups)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
