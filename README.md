# PROJECT-NEURO-K

**Adaptive Computational Offloading — Proof of Concept**

> Projeto de portfólio técnico de Matheus Pedroso, voltado a Engenharia Computacional, arquitetura de sistemas e engenharia de performance.

## 🎯 Objetivo

O PROJECT-NEURO-K investiga uma pergunta prática:

> **Quando vale a pena transferir uma carga de álgebra linear de uma máquina local para um worker remoto?**

A versão atual substitui a proposta conceitual baseada em webhook por um **worker remoto funcional**, usando **ZeroMQ para transporte binário de buffers NumPy**.

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

- `orchestrator.py` — calibração, decisão e benchmark.
- `worker.py` — execução remota da multiplicação de matrizes.
- `requirements.txt` — dependências Python.
- `.gitignore` — artefatos locais ignorados.

## 🔬 Decisão adaptativa

A decisão não usa mais valores fixos como “CPU = 2 GFLOPS” ou “worker = 2× mais rápido”.

O orquestrador executa uma etapa de **calibração** e mede:

- tempo local;
- tempo do worker;
- taxa de transferência observada;
- RTT aproximado.

Depois utiliza essas medições para estimar o custo de uma carga maior.

A regra conceitual é:

```text
T_offload ≈ T_remote_compute + T_transfer + T_RTT
```

e:

```text
OFFLOAD se T_offload < T_local
```

A estimativa de custo é uma heurística baseada em escala `O(N³)`. Portanto, ela é uma previsão e deve ser validada pelo benchmark real.

## 💾 Memória

A memória mínima aproximada para uma multiplicação matricial é estimada por:

```text
3 × N² × sizeof(dtype)
```

correspondendo a A, B e C.

O monitoramento utiliza `psutil.virtual_memory().available` e não requer privilégios root.

**Importante:** essa estimativa é um limite inferior. Bibliotecas BLAS podem utilizar memória adicional.

## 📡 Transporte

As matrizes são enviadas como buffers binários:

```python
np.ascontiguousarray(A).tobytes()
```

e reconstruídas no worker com:

```python
np.frombuffer(buffer, dtype=dtype)
```

Isso evita JSON para os dados numéricos. A reconstrução via `frombuffer` evita uma cópia adicional naquele ponto, mas o pipeline completo **não é declarado como zero-copy end-to-end**.

## 🧪 Benchmark

O benchmark é executável, mas **nenhum número é inventado neste README**.

Para executar:

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

Você também pode escolher os tamanhos:

```bash
python orchestrator.py --sizes 256 512 1024 2048
```

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
- testes automatizados;
- benchmark em máquinas separadas;
- controle de threads/BLAS para comparação rigorosa;
- persistência de resultados experimentais.

## 🧭 Próximos passos

1. Adicionar testes automatizados para protocolo e integridade numérica.
2. Executar benchmarks em hosts fisicamente separados.
3. Salvar resultados em CSV.
4. Implementar um modelo de decisão alimentado por histórico de medições.
5. Avaliar `float32`, `float64` e diferentes bibliotecas BLAS.
6. Investigar batching e operações assíncronas.

## 📌 Classificação

**Estado atual: Proof of Concept (PoC) funcional e reproduzível, sujeito à validação experimental no ambiente de execução.**

Não são apresentados ganhos de desempenho como fato até que os benchmarks sejam realmente executados.

---

### Créditos

**Matheus Pedroso** — projeto e desenvolvimento.

Assistência de IA foi utilizada como apoio à arquitetura e revisão técnica. As decisões, código e validação do repositório devem ser verificadas pelo autor.

**Versão:** 2.1
