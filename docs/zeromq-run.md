# ZeroMQ benchmark

Start `worker.py` on the target worker, then run `scripts/benchmark_zeromq.py` from the orchestrator host.

Default campaign: N=256,512,1024,2048; float32,float64; 10 measured repetitions and 2 warm-ups per combination.

Output is `results/zeromq/benchmark-results-zeromq.csv` with `execution=ZEROMQ_WORKER`. Keep it separate from Vercel and historical simulated observations.

Analyze with `python scripts/analyze_benchmark.py results/zeromq/benchmark-results-zeromq.csv results/analysis/zeromq_worker_summary.csv`.
