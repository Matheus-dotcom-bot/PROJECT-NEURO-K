# ZeroMQ benchmark checklist

- Worker reachable before campaign.
- N values: 256, 512, 1024, 2048.
- dtypes: float32, float64.
- 2 warm-ups and 10 measured repetitions.
- Raw output under `results/zeromq/`.
- `execution=ZEROMQ_WORKER` on every successful observation.
- Run the shared analyzer before any Vercel comparison.
- Never treat simulated rows as physical measurements.
