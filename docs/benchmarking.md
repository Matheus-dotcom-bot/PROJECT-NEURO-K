# Benchmarking guide

## Purpose

The benchmark measures whether the adaptive decision made during calibration agrees with the observed end-to-end behavior of local versus remote matrix multiplication.

This repository distinguishes two kinds of data:

- `SIMULATED`: manually constructed or illustrative values. They are not experimental evidence.
- `MEASURED`: values produced by `orchestrator.py` during an actual run.

## What is measured

The orchestrator records local execution time, remote compute time, payload transfer components, result reception time, total offload time, and observed gain when a local baseline is available.

The prediction model is intentionally simple:

```text
T_offload ≈ T_remote_compute + T_transfer + T_RTT
```

The compute component is extrapolated from calibration using an approximate `O(N³)` scaling rule. This is useful as a PoC heuristic, but it should not be interpreted as a performance model with scientific accuracy.

## Local smoke benchmark

For a quick end-to-end validation:

```bash
python worker.py --host 127.0.0.1 --port 5555
```

Then, in another terminal:

```bash
python orchestrator.py \
  --worker tcp://127.0.0.1:5555 \
  --sizes 64 128 256 \
  --results benchmark-results.csv
```

This validates the complete path:

1. calibration;
2. adaptive prediction;
3. NumPy buffer serialization;
4. ZeroMQ transport;
5. remote matrix multiplication;
6. result reconstruction;
7. numerical comparison;
8. CSV persistence.

## Interpreting results

`gain_percent` is calculated as:

```text
((T_local - T_offload) / T_local) × 100
```

Positive values mean the measured offload path was faster than the measured local baseline for that row. Negative values mean offloading was slower.

A `LOCAL` decision does not prove that local execution is globally optimal; it only means the calibrated prediction selected the local path.

## Reproducible CI validation

`.github/workflows/benchmark.yml` runs a small benchmark on GitHub-hosted Linux infrastructure and validates that:

- exactly three measured rows are produced;
- sizes `64, 128, 256` are present;
- no execution error is recorded;
- the CSV is uploaded as a workflow artifact.

The CI benchmark is a **pipeline smoke test**, not a claim about the performance of a remote production deployment. Both the orchestrator and worker run on the same CI host, so network characteristics are not representative of a geographically or physically separate worker.

## Serious experimental benchmark

For a portfolio-grade performance study, run the worker and orchestrator on separate machines and record at least:

- CPU model and core count;
- RAM capacity and available memory;
- OS and Python version;
- NumPy version and BLAS backend;
- CPU thread configuration;
- network link type and nominal bandwidth;
- network RTT;
- matrix size and dtype;
- number of repetitions;
- median and dispersion of each timing component.

Do not compare a single run from two different environments as if it were a controlled experiment. Repeat measurements and keep the raw CSV files so conclusions remain auditable.

## Current repository policy

The tracked `benchmark-results.csv` contains simulated rows from the project's development history. They remain in the repository for provenance and are explicitly marked `SIMULATED`. New real measurements should be appended only when they were actually produced by the benchmark command, or stored as a separate experiment with enough metadata to identify the environment.
