# Resultados do baseline Vercel — campanha 2026-09-06

## Proveniência

- Workflow: `Vercel benchmark`
- Run: `34006882503`
- Commit avaliado: `0bc10ee6ac3c2334ea46b5ca0dfbb86914a95efe`
- Endpoint: `https://project-neuro-k.vercel.app`
- Execução: `VERCEL_FUNCTION`
- Repetições: 10 por combinação
- Warm-ups: 3 por combinação
- Tamanhos: 256, 512, 1024, 2048
- Dtypes: float32, float64
- Linhas medidas: 80
- Erros: 0
- Runtime: Python 3.12.13, NumPy 2.5.2, Linux x86_64, 2 CPUs lógicas reportadas

Os resultados abaixo são **medidos** pelo endpoint Vercel nessa campanha específica. Eles não devem ser misturados com `benchmark-results.csv`, que preserva dados `SIMULATED` históricos.

## Resumo estatístico

| dtype | N | repetições | mediana compute (s) | média compute (s) | p95 compute (s) | mediana HTTP (s) | média HTTP (s) | p95 HTTP (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| float32 | 256 | 10 | 0.000258 | 0.000260 | 0.000284 | 0.104675 | 0.108503 | 0.128554 |
| float32 | 512 | 10 | 0.001898 | 0.001898 | 0.001910 | 0.105926 | 0.104667 | 0.107955 |
| float32 | 1024 | 10 | 0.023137 | 0.023137 | 0.034710 | 0.159736 | 0.165713 | 0.191382 |
| float32 | 2048 | 10 | 0.330786 | 0.330786 | 0.352608 | 0.873898 | 0.831519 | 0.971056 |
| float64 | 256 | 10 | 0.000521 | 0.000521 | 0.000545 | 0.094477 | 0.097365 | 0.105527 |
| float64 | 512 | 10 | 0.003795 | 0.003795 | 0.007728 | 0.118842 | 0.121907 | 0.141519 |
| float64 | 1024 | 10 | 0.081254 | 0.081254 | 0.098639 | 0.281045 | 0.281775 | 0.297086 |
| float64 | 2048 | 10 | 0.433099 | 0.433099 | 0.552081 | 1.087340 | 1.128182 | 1.400959 |

## Leitura técnica

1. O pipeline Vercel completou 80/80 medições com `status=MEASURED`.
2. Para matrizes pequenas, o custo HTTP domina claramente o tempo de computação: em N=256, a mediana de compute fica abaixo de 1 ms enquanto a mediana HTTP fica perto de 0,1 s.
3. O custo computacional cresce fortemente com N, como esperado para multiplicação matricial `O(N^3)`. Em N=2048, o compute mediano chega a aproximadamente 0,331 s em float32 e 0,433 s em float64.
4. O tempo HTTP também cresce nas cargas maiores, mas não deve ser interpretado como custo de um worker ZeroMQ equivalente: trata-se de uma chamada HTTP a uma função serverless.
5. O float32 apresentou menor tempo de compute que float64 em todos os quatro tamanhos nesta campanha.
6. A dispersão de `http_elapsed_s` em N=2048 é relevante, especialmente em float64. Isso reforça a necessidade de usar medianas/p95 e repetir campanhas antes de qualquer conclusão de desempenho geral.

## Limites de interpretação

- `t_compute_s` mede somente a multiplicação NumPy dentro da função após o warm-up.
- `http_elapsed_s` mede o tempo observado pelo cliente para a requisição HTTP e, portanto, inclui overhead de rede/invocação além do compute.
- O runtime reportado é o ambiente observado pelo endpoint durante a campanha; não é equivalente à máquina de build do Vercel.
- Esta campanha é um **baseline cloud**, não uma medição de offload ZeroMQ entre dois hosts físicos.
- Não há base metodológica para afirmar que Vercel é mais rápido ou mais lento que o worker ZeroMQ sem uma campanha ZeroMQ comparável, com hardware, BLAS, threads e rede devidamente registrados.

## Arquivos

- `results/vercel/benchmark-results-vercel-2026-09-06.csv` — 80 medições da campanha.
- `results/vercel/benchmark-metadata-vercel-2026-09-06.json` — metadados de runtime e configuração.
- `benchmark-results.csv` — permanece separado e preserva as linhas históricas `SIMULATED`.
