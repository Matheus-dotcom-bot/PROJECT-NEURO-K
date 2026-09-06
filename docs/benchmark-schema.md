# NEURO-K benchmark schema

The benchmark pipeline keeps **raw observations** and **aggregated analysis** separate.
The same raw schema is used by each execution environment, while `execution` keeps
environments explicitly separated.

## Raw observations

| Column | Meaning |
|---|---|
| `timestamp_utc` | UTC timestamp of the observation |
| `status` | `MEASURED` or `ERROR` |
| `execution` | Execution environment, e.g. `VERCEL_FUNCTION` or `ZEROMQ_WORKER` |
| `vercel_url` | Vercel endpoint; blank for non-Vercel environments |
| `n` | Problem size / matrix dimension |
| `dtype` | Numeric dtype, e.g. `float32`, `float64` |
| `seed` | Reproducibility seed |
| `t_compute_s` | Compute time reported by the execution environment |
| `result_checksum` | Result checksum used to verify the computation |
| `matrix_bytes` | Input matrix payload size in bytes |
| `http_elapsed_s` | End-to-end transport elapsed time measured by the client |
| `error` | Error text when `status=ERROR` |

For ZeroMQ, keep the same columns. `vercel_url` remains blank and
`http_elapsed_s` is retained as the compatibility name for the measured
client-side transport elapsed time. This avoids changing the statistical schema
while making the transport semantics explicit in the metadata/documentation.

## Aggregate output

`scripts/analyze_benchmark.py` groups by `execution + n + dtype` and emits:

- mean, median, standard deviation and p95 for compute time;
- mean, median, standard deviation and p95 for transport time;
- mean, median, standard deviation and p95 for communication/transport overhead;
- overhead as a percentage of mean transport time;
- valid sample count and error count.

Communication overhead is defined as:

`max(transport_elapsed_s - compute_s, 0)`

The clamp prevents negative measurement artifacts from becoming negative
communication cost. It does **not** claim that the transport is literally only
network time; it represents everything measured outside the reported remote
compute interval.

## Comparison rule

Do not combine Vercel and ZeroMQ rows into a single statistical population.
Generate one aggregate table per execution environment first. Only then compare
matching `n` and `dtype` groups side by side.

The resulting evidence can support the NEURO-K question:

> At what problem size does the measured cost of communication stop outweighing
the benefit of offloading?
