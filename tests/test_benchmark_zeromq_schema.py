from pathlib import Path

from scripts.benchmark_zeromq import FIELDNAMES


def test_zeromq_schema_matches_shared_required_fields() -> None:
    required = {
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
    }
    assert required.issubset(FIELDNAMES)
    assert FIELDNAMES[2] == "execution"


def test_default_result_location_is_not_historical_csv() -> None:
    source = Path("scripts/benchmark_zeromq.py").read_text(encoding="utf-8")
    assert "results/zeromq/benchmark-results-zeromq.csv" in source
    assert "benchmark-results.csv" not in source.split("default=", 1)[-1].split(")", 1)[0]
