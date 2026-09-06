# ZeroMQ benchmark runbook

Run `worker.py` on the target worker and then run `scripts/benchmark_zeromq.py` from the orchestrator host.

Default campaign: N=256,512,1024,2048; float32,float64; 10 measured repetitions and 2 warm-ups per combination.

Output: `results/zeromq/benchmark-results-zeromq.csv` using `execution=ZEROMQ_WORKER` and the shared schema. Do not mix these rows with Vercel or historical simulated observations.

Analyze with:

```bash
python scripts/analyze_benchmark.py results/zeromq/benchmark-results-zeromq.csv results/analysis/zeromq_worker_summary.csv
```

The collector deliberately measures every requested size rather than using the adaptive prediction decision, so the resulting curve can be used to calibrate the heuristic later.
