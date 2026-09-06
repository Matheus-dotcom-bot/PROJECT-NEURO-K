# Protocolo de benchmark físico — PROJECT-NEURO-K

## Objetivo

Produzir medições `MEASURED` que possam ser reproduzidas e auditadas, comparando execução local de `A @ B` com offload para um worker em outro host.

Este protocolo não transforma automaticamente qualquer resultado em evidência científica. O objetivo é controlar as principais fontes conhecidas de variação e preservar metadados suficientes para repetir o experimento.

## 1. Topologia

Use dois computadores fisicamente separados:

```text
HOST LOCAL                         HOST WORKER
┌─────────────────┐               ┌─────────────────┐
│ orchestrator.py │ ── TCP ─────> │   worker.py     │
│ NumPy / BLAS    │               │   NumPy / BLAS   │
└─────────────────┘               └─────────────────┘
```

Não use `127.0.0.1` para o experimento físico. O endereço do worker deve ser o IP privado ou endereço de rede explicitamente escolhido para o teste.

O PoC não implementa autenticação nem TLS; execute o experimento em uma rede controlada.

## 2. Controle do ambiente

Registre, para os dois hosts:

- modelo de CPU;
- número de núcleos físicos e lógicos;
- RAM total;
- sistema operacional e versão;
- versão do Python;
- versão do NumPy;
- versão do pyzmq;
- biblioteca BLAS/LAPACK efetivamente usada;
- configuração de threads do BLAS;
- versão do kernel, quando relevante;
- tipo e velocidade nominal da interface de rede;
- conexão utilizada entre os hosts;
- carga relevante em segundo plano.

O `--metadata` do `orchestrator.py` registra automaticamente parte importante dessas informações, inclusive `threadpool_info()` e variáveis de ambiente relacionadas a threads.

## 3. Threads do BLAS

Matmul do NumPy pode utilizar OpenBLAS, MKL ou outra implementação BLAS e pode executar com múltiplas threads. A comparação entre máquinas só é interpretável se a política de threads for conhecida e mantida constante. citeturn0search0turn0search6

Para uma comparação inicial controlada, prefira **1 thread de BLAS em ambos os hosts**. Exemplos de variáveis que podem ser relevantes:

```text
OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
MKL_NUM_THREADS=1
BLIS_NUM_THREADS=1
VECLIB_MAXIMUM_THREADS=1
```

A variável exata depende do backend instalado. Não presuma que todas têm efeito; confirme a configuração registrada pelo runtime.

## 4. Preparação

Em ambos os hosts:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -v
```

No Windows, use o equivalente do ambiente virtual com PowerShell.

Antes da coleta, execute pelo menos um teste funcional completo do protocolo.

## 5. Warm-up

Não use a primeira execução como medição principal.

Para cada tamanho `N`, faça pelo menos **3 warm-ups** antes das repetições medidas. Isso permite que importações já tenham ocorrido e reduz o efeito de inicialização do runtime/BLAS.

O warm-up não deve entrar no CSV de resultados medidos.

## 6. Tamanhos

Uma primeira campanha recomendada:

```text
N = 256, 512, 1024, 2048
```

Se a memória dos hosts permitir, tamanhos maiores podem ser adicionados posteriormente. O limite do worker deve permanecer explícito.

Compare pelo menos:

```text
float32
float64
```

como campanhas separadas, porque o custo computacional e o volume de dados são diferentes.

## 7. Repetições

Use **10 repetições medidas por combinação de tamanho e dtype** como ponto de partida.

Não agregue as observações no CSV antes da análise. Preserve cada execução individual para permitir cálculo posterior de:

- mediana;
- média;
- desvio-padrão;
- percentis;
- intervalo de confiança, quando aplicável;
- coeficiente de variação.

A mediana é particularmente útil para inspeção inicial quando há outliers de sistema ou rede.

## 8. Ordem experimental

Evite executar todos os `N` de um mesmo tipo em uma única ordem fixa se houver risco de efeitos temporais.

Uma estratégia simples é executar campanhas separadas e repetir a ordem, por exemplo:

```text
256 → 512 → 1024 → 2048
2048 → 1024 → 512 → 256
```

Se a campanha crescer, use randomização controlada e registre a semente/ordem.

## 9. Comando de coleta

No worker:

```bash
python worker.py --host 0.0.0.0 --port 5555
```

No host local:

```bash
python orchestrator.py \
  --worker tcp://IP_DO_WORKER:5555 \
  --sizes 256 512 1024 2048 \
  --warmup-runs 3 \
  --repetitions 10 \
  --results benchmark-results-measured.csv \
  --metadata benchmark-metadata.json
```

**Atenção:** `0.0.0.0` é apenas o endereço de bind de exemplo para uma rede controlada. Não exponha o worker diretamente à Internet.

## 10. O que o CSV mede

Cada linha `MEASURED` representa uma execução.

O pipeline registra, quando há offload:

- tempo local;
- serialização local;
- envio de A;
- envio de B;
- desserialização no worker;
- computação no worker;
- serialização de C;
- recepção de C;
- tempo total de offload;
- ganho percentual observado.

Uma decisão `LOCAL` é uma decisão do modelo e não uma medição de offload naquela linha.

## 11. Validação numérica

Quando existe uma referência local disponível, o orquestrador compara o resultado remoto com `A @ B` usando `np.allclose`.

Uma campanha com erro de validação, payload inválido ou falha de comunicação deve ser investigada e não deve ser apresentada como resultado de desempenho válido.

## 12. Metadados de rede

Além do JSON produzido pelo `--metadata`, registre manualmente:

- hosts envolvidos;
- IPs privados ou identificadores não sensíveis dos hosts;
- tipo de conexão;
- RTT de referência;
- largura de banda nominal;
- horário da campanha;
- condições relevantes da rede.

Não inclua credenciais, tokens ou outros segredos nos artefatos.

## 13. Regras para publicação

Nunca relabel uma linha `SIMULATED` como `MEASURED`.

Uma linha pode ser marcada `MEASURED` somente quando tiver sido produzida por uma execução real do orquestrador.

Publique o CSV junto com o JSON de metadados correspondente. Se houver alteração de hardware, software, BLAS, configuração de threads ou topologia de rede, trate a coleta como uma nova campanha.

## 14. Interpretação

Não conclua que o offload é "mais rápido" a partir de uma única execução.

A pergunta experimental é mais próxima de:

> Para uma determinada configuração de hardware, software, rede, tamanho e dtype, qual é a distribuição observada do custo local e do custo de offload?

A decisão adaptativa do NEURO-K continua sendo uma heurística. O benchmark serve para testar e calibrar essa heurística, não para provar que o offload é universalmente superior.

## 15. Checklist antes da coleta

- [ ] Dois hosts fisicamente separados.
- [ ] Mesmo código/commit identificado nos dois hosts.
- [ ] Dependências instaladas e `pip check` concluído.
- [ ] Testes automatizados concluídos.
- [ ] Backend BLAS identificado.
- [ ] Número de threads conhecido.
- [ ] Warm-up definido.
- [ ] Número de repetições definido.
- [ ] Tamanhos e dtypes definidos.
- [ ] Rede controlada.
- [ ] CSV de saída separado do histórico `SIMULATED`.
- [ ] JSON de metadados preservado.

## Resultado esperado

A primeira campanha não precisa produzir um grande número de dados. Ela precisa produzir **dados rastreáveis**.

O objetivo desta etapa é estabelecer uma linha de base experimental confiável antes de treinar ou ajustar qualquer modelo de decisão com os resultados.
