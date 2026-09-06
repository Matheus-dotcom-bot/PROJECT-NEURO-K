# PROJECT-NEURO-K

**Adaptive Computational Offloading — Proof of Concept**

> Projeto de portfólio técnico de Matheus Pedroso, voltado a Engenharia Computacional, arquitetura de sistemas e engenharia de performance.

## 🎯 Objetivo

O PROJECT-NEURO-K investiga uma pergunta prática:

> **Quando vale a pena transferir uma carga de álgebra linear de uma máquina local para um worker remoto?**

A implementação atual usa um **worker remoto funcional**, com **ZeroMQ para transporte binário de buffers NumPy**.

O projeto é deliberadamente tratado como **Proof of Concept (PoC)**. Ele não afirma ser um sistema HPC de produção.

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
│ NumPy / BLAS         │
│ matrix multiplication│
└──────────────────────┘
```

### Componentes

- `orchestrator.py` — calibração, previsão, execução do benchmark e persistência dos resultados.
- `worker.py` — execução remota da multiplicação de matrizes.
- `benchmark-results.csv` — resultados experimentais; as linhas existentes marcadas como `SIMULATED` são dados de simulação e não medições reais.
- `requirements.txt` — dependências Python.
- `.gitignore` — artefatos locais ignorados.

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

A computação é escalada aproximadamente por `O(N³)`. Portanto, a decisão é uma **heurística de previsão** e deve ser validada pelo benchmark real.

## 💾 Memória

A memória mínima aproximada para uma multiplicação matricial é estimada por:

```text
3 × N² × sizeof(dtype)
```

correspondendo a A, B e C.

O monitoramento utiliza `psutil.virtual_memory().available` e não requer privilégios root.

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

O protocolo ZeroMQ `REQ/REP` mantém a alternância obrigatória de request/response. O fluxo é:

```text
REQUEST → READY
A       → A_RECEIVED
B       → RESULT_READY
SEND_RESULT → binary C
```

## 🧪 Benchmark

O arquivo `benchmark-results.csv` pode conter dados de simulação e medições reais. **Resultados simulados são explicitamente marcados como `SIMULATED` e não devem ser apresentados como evidência experimental.**

Para executar um benchmark real:

### 1. Criar ambiente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Iniciar o worker

Em um terminal:

```bash
python worker.py --port 5555
```

### 3. Executar o orquestrador

Em outro terminal:

```bash
python orchestrator.py --worker tcp://127.0.0.1:5555
```

Você também pode escolher os tamanhos e o arquivo de resultados:

```bash
python orchestrator.py --sizes 256 512 1024 2048 --results benchmark-results.csv
```

As medições reais são gravadas com `status=MEASURED`. Em uma execução experimental séria, recomenda-se realizar o benchmark com o worker em uma máquina separada para que rede e computação remota sejam efetivamente avaliadas.

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
- testes automatizados de protocolo e integridade numérica;
- benchmark em máquinas fisicamente separadas;
- controle de threads/BLAS para comparação rigorosa;
- modelo de decisão treinado com histórico suficiente.

## 🧭 Próximos passos

1. Adicionar testes automatizados para protocolo e integridade numérica.
2. Executar benchmarks em hosts fisicamente separados.
3. Comparar `float32`, `float64` e diferentes bibliotecas BLAS.
4. Alimentar o modelo de decisão com histórico de medições reais.
5. Investigar batching e operações assíncronas.
6. Adicionar autenticação e transporte seguro ao worker.

## 📌 Classificação

**Estado atual: Proof of Concept (PoC) funcional, com protocolo ZeroMQ corrigido e suporte à persistência de benchmarks reais.**

Os números atualmente marcados como `SIMULATED` são apenas dados de simulação. Ganhos de desempenho não devem ser tratados como fatos até que sejam obtidos por execução experimental reproduzível.

---

### Créditos

**Matheus Pedroso** — projeto e desenvolvimento.

Assistência de IA foi utilizada como apoio à arquitetura e revisão técnica. As decisões, código e validação do repositório devem ser verificadas pelo autor.

**Versão:** 2.2
