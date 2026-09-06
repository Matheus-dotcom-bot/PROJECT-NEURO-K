# NEURO-K ZeroMQ benchmark

This experiment measures the `ZEROMQ_WORKER` execution environment without
combining it with Vercel observations.

## Campaign

The default campaign is the same matrix used for the Vercel evidence:

- `N = 256, 512, 1024, 2048`
- `dtype = float32, float64`
- `10` measured repetitions per `N × dtype`
- `2` warm-up runs per `N × dtype`

That produces up to 80 measured observations, excluding warm-ups and errors.

## Run

Start the worker on the target machine:

```bash
python worker.py --host 0.0.0.0 --port 5555
```

From the orchestrator machine:

```bash
python scripts/benchmark_zeromq.py \
  --worker tcp://WORKER_HOST:5555 \
  --sizes 256 512 1024 2048 \
  --dtypes float32 float64 \
  --repetitions 10 \
  --warmup-runs 2 \
  --results results/zeromq/benchmark-results-zeromq.csv
```

The collector deliberately bypasses the adaptive decision and measures the
remote path at every requested size. This is necessary to characterize the
transport/compute curve before the NEURO-K heuristic is allowed to decide.

## Measurements

Each successful row records:

- `execution=ZEROMQ_WORKER`;
- remote `t_compute_s` from the worker;
- client-side end-to-end `http_elapsed_s` as the shared schema's transport
  elapsed field (the name is retained for compatibility; it is not HTTP);
- result checksum;
- input matrix payload size;
- reproducibility seed.

The transport elapsed value includes ZeroMQ request/control exchange,
serialization and transfer, plus remote execution as observed by the client.
The analysis layer therefore derives communication/external overhead as:

`max(transport_elapsed_s - compute_s, 0)`

## Analysis

After collecting the CSV, run:

```bash
python scripts/analyze_benchmark.py \
  results/zeromq/benchmark-results-zeromq.csv \
  results/analysis/zeromq_worker_summary.csv
```

Do not append these rows to the historical simulated `benchmark-results.csv`.
Do not compare individual observations directly with Vercel observations. First
aggregate each execution environment independently by `execution + n + dtype`.
Only then perform the side-by-side Vercel × ZeroMQ comparison.
