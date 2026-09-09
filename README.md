# PROJECT-NEURO-K

**Adaptive Computational Offloading — Proof of Concept**

> **Em uma frase:** PoC em Python que decide, a partir de calibração observada, quando uma multiplicação matricial deve ser executada localmente ou enviada a um worker remoto via ZeroMQ.

[![CI](https://github.com/Matheus-dotcom-bot/PROJECT-NEURO-K/actions/workflows/ci.yml/badge.svg)](https://github.com/Matheus-dotcom-bot/PROJECT-NEURO-K/actions/workflows/ci.yml)

**Estado:** funcional / experimental · **Validação:** testes automatizados · **Benchmark:** simulado e protocolo físico definido

### O que demonstra

- 🧠 decisão adaptativa baseada em medições de calibração;
- ⚙️ offloading de buffers NumPy por ZeroMQ/TCP;
- 🧪 testes unitários e de integração automatizados;
- ☁️ baseline cloud separado via FastAPI/Vercel;
- 📊 benchmark com metadados e distinção explícita entre `SIMULATED` e `MEASURED`.

> **Importante:** os resultados atualmente marcados como `SIMULATED` são dados de simulação. Eles não são apresentados como evidência experimental.

---
## 🎯 Objetivo

O PROJECT-NEURO-K investiga uma pergunta prática:

> **Quando vale a pena transferir uma carga de álgebra linear de uma máquina local para um worker remoto?**

A implementação usa um **worker remoto funcional**, com **ZeroMQ para transporte binário de buffers NumPy**.

O projeto é deliberadamente tratado como **Proof of Concept (PoC)**. Ele não afirma ser um sistema HPC de produção.

## ☁️ Vercel e worker físico

O projeto também possui uma camada **FastAPI hospedada na Vercel**. Ela fornece endpoints de saúde, runtime e um benchmark de referência executado dentro da função serverless.

O benchmark da Vercel é identificado como `VERCEL_FUNCTION` e **não deve ser confundido com o benchmark ZeroMQ físico**. Funções serverless são ambientes efêmeros; portanto, a Vercel não é tratada como um worker TCP/ZeroMQ persistente.

A arquitetura experimental fica:

```text
                         HTTP
┌───────────────────┐  ───────>  ┌─────────────────────────┐
│ Cliente / pesquisa│             │ Vercel Function         │
└─────────┬─────────┘             │ FastAPI cloud baseline  │
          │                       └─────────────────────────┘
          │ ZeroMQ / TCP
          ▼
┌─────────────────────────┐
│ Worker persistente      │
│ worker.py               │
│ NumPy / BLAS            │
└─────────────────────────┘
```

Assim, a Vercel serve como **baseline de execução cloud e camada HTTP**, enquanto o worker ZeroMQ continua sendo o alvo do experimento de offload.

## 🏗️ Arquitetura

```text
┌──────────────────────┐
│   Local Orchestrator │
│                      │
│ psutil               │
│ calibration          │
│ decision model       │
│ NumPy / BLAS         │
└──────────┬───────────┘
           │ ZeroMQ / TCP
           │ NumPy raw bytes
           ▼
┌──────────────────────┐
│    Remote Worker     │
│                      │
│ validation / limits  │
│ NumPy / BLAS         │
│ matrix multiplication│
└──────────────────────┘
```

### Estrutura

```text
PROJECT-NEURO-K/
├── api/
│   └── index.py
├── orchestrator.py
├── worker.py
├── requirements.txt
├── benchmark-results.csv
├── tests/
│   ├── test_orchestrator.py
│   └── test_integration.py
├── docs/
│   ├── benchmarking.md
│   └── experimental-benchmark-protocol.md
└── .github/
    └── workflows/
        ├── ci.yml
        └── benchmark.yml
```

### Componentes

- `api/index.py` — API FastAPI para Vercel, incluindo baseline cloud.
- `orchestrator.py` — calibração, previsão, benchmark, repetições e metadados de ambiente.
- `worker.py` — execução remota da multiplicação de matrizes com validação de entrada e limites de recursos.
- `tests/` — testes unitários e teste de integração do protocolo ZeroMQ.
- `.github/workflows/ci.yml` — compilação e testes automatizados em cada push/PR.
- `.github/workflows/benchmark.yml` — smoke benchmark reproduzível no GitHub Actions, com CSV e metadados como artefatos.
- `docs/benchmarking.md` — metodologia e interpretação dos resultados.
- `docs/experimental-benchmark-protocol.md` — protocolo para medições físicas reproduzíveis.
- `benchmark-results.csv` — histórico; linhas `SIMULATED` são dados de simulação, não medições reais.

## 🔬 Decisão adaptativa

A decisão não usa valores fixos como “CPU = 2 GFLOPS” ou “worker = 2× mais rápido”.

O orquestrador executa uma etapa de **calibração** e mede:

- tempo local de multiplicação;
- tempo de computação no worker;
- taxa de transferência observada;
- RTT do primeiro ciclo de controle.

Para a previsão, o custo remoto é estimado como:

```text
T_offload ≈ T_remote_compute + T_transfer + T_RTT
```

e:

```text
OFFLOAD se T_offload < T_local
```

A computação é escalada aproximadamente por `O(N³)`. Portanto, a decisão é uma **heurística de previsão**, não uma garantia de desempenho.

## 💾 Memória

A memória mínima aproximada para uma multiplicação matricial é estimada por:

```text
3 × N² × sizeof(dtype)
```

correspondendo a A, B e C.

O monitoramento utiliza `psutil.virtual_memory().available` e não requer privilégios root.

O worker também aplica um limite de segurança de **512 MiB de working set por padrão**, considerando A, B e C. O limite pode ser ajustado com `--max-memory-mb` para experimentos controlados.

**Importante:** essa estimativa é um limite inferior. Bibliotecas BLAS podem utilizar memória adicional.

## 📡 Transporte e protocolo

As matrizes são enviadas como buffers binários:

```python
np.ascontiguousarray(A).tobytes()
```

e reconstruídas no worker com:

```python
np.frombuffer(buffer, dtype=dtype)
```

Isso evita JSON para os dados numéricos. A reconstrução via `frombuffer` evita uma cópia adicional naquele ponto, mas o pipeline completo **não é declarado como zero-copy end-to-end**.

O protocolo ZeroMQ `REQ/REP` mantém a alternância obrigatória de request/response:

```text
REQUEST → READY
A       → A_RECEIVED
B       → RESULT_READY
SEND_RESULT → binary C
```

O worker aceita explicitamente `float32` e `float64`, valida o tamanho dos payloads e rejeita tipos e matrizes fora dos limites configurados.

Por padrão, o worker escuta em `127.0.0.1`. Para uso em rede, o endereço de bind deve ser configurado conscientemente e a comunicação deve ser protegida por controles externos adequados; o PoC **não implementa autenticação nem TLS**.

## 🧪 Testes automatizados

Execute localmente:

```bash
python -m unittest discover -s tests -v
```

A suíte cobre:

- estimativas de memória;
- pré-condição e validação da calibração;
- rejeição de tamanhos de matriz inválidos;
- decisão de offload quando o worker é previsto como mais rápido;
- decisão local quando comunicação domina;
- condição de pressão de RAM;
- persistência e schema do CSV;
- registro do tempo de serialização;
- protocolo ZeroMQ e integridade numérica `A @ B == C`;
- rejeição de working sets acima do limite do worker;
- validação da configuração do worker.

O GitHub Actions executa os mesmos testes em Python 3.12 e também verifica a compilação dos módulos.

## 📊 Benchmark

O arquivo `benchmark-results.csv` pode conter dados de simulação e medições reais. **Resultados simulados são explicitamente marcados como `SIMULATED` e não devem ser apresentados como evidência experimental.**

Os campos de tempo incluem a serialização local dos buffers, transferência dos operandos, desserialização e computação no worker, serialização do resultado e recepção do resultado. Isso permite separar melhor o custo do pipeline de offload.

O orquestrador suporta:

- `--warmup-runs` para evitar registrar a primeira execução como se fosse representativa;
- `--repetitions` para obter múltiplas observações por tamanho;
- `--metadata` para registrar Python, plataforma, CPU, memória inicial, versão das bibliotecas e informações do BLAS/thread pool.

### Benchmark físico recomendado

Para uma primeira coleta real, use dois hosts fisicamente separados, fixe a configuração de threads do BLAS e execute, por exemplo:

```bash
python orchestrator.py \
  --worker tcp://IP_DO_WORKER:5555 \
  --sizes 256 512 1024 2048 \
  --warmup-runs 3 \
  --repetitions 10 \
  --results benchmark-results-measured.csv \
  --metadata benchmark-metadata.json
```

**Não execute esse comando sobre o `benchmark-results.csv` histórico**, pois esse arquivo contém as linhas simuladas preservadas para proveniência.

### Baseline Vercel

A API cloud pode ser consultada com:

```text
GET /health
GET /runtime
POST /benchmark
```

Exemplo de corpo para `POST /benchmark`:

```json
{
  "n": 512,
  "dtype": "float64",
  "seed": 0
}
```

A resposta registra `status=MEASURED`, `execution=VERCEL_FUNCTION`, tamanho da matriz, dtype, seed, tempo de computação e checksum do resultado. Esse tempo é **medição do ambiente serverless**, não ganho de offload ZeroMQ.

### Validação automática

O workflow `Benchmark validation` executa um smoke benchmark com `N=64,128,256`, três repetições e um warm-up por tamanho. Além do CSV, publica os metadados do runtime como artefato. Isso valida **corretude e reprodutibilidade do pipeline**, mas não substitui um benchmark físico.

Para o protocolo completo, consulte `docs/experimental-benchmark-protocol.md`.

## ⚠️ Limitações conhecidas

Esta é uma PoC, não uma plataforma de produção.

Ainda seriam necessários, entre outros:

- autenticação do worker;
- TLS ou rede privada segura;
- reconexão e retry robustos;
- controle de concorrência;
- backpressure;
- filas assíncronas;
- chunking/streaming para cargas muito grandes;
- observabilidade;
- benchmark em máquinas fisicamente separadas;
- controle de threads/BLAS para comparação rigorosa;
- modelo de decisão treinado com histórico suficiente;
- análise estatística com múltiplas execuções e intervalos de confiança.

A Vercel não é usada como substituta artificial de um worker persistente. Ela fornece uma referência cloud separada para comparação e demonstração da API.

## 🧭 Próximos passos

1. Usar o endpoint Vercel como baseline cloud.
2. Executar o protocolo ZeroMQ em hosts fisicamente separados.
3. Preservar os metadados de hardware, software, BLAS e rede junto dos resultados.
4. Comparar `float32` e `float64` sob configuração controlada.
5. Alimentar o modelo de decisão com histórico de medições reais.
6. Investigar batching e operações assíncronas.
7. Expandir observabilidade e análise estatística dos benchmarks.

## 📌 Classificação

**Estado atual: Proof of Concept (PoC) funcional, testado automaticamente, com API Vercel e protocolo de benchmark físico definido.**

Os números atualmente marcados como `SIMULATED` são apenas dados de simulação. Ganhos de desempenho não devem ser tratados como fatos até que sejam obtidos por execução experimental reproduzível.

---

### Créditos

**Matheus Pedroso** — projeto e desenvolvimento.

Assistência de IA foi utilizada como apoio à arquitetura e revisão técnica. As decisões, código e validação do repositório são verificadas pelo autor.

**Versão:** 2.6
