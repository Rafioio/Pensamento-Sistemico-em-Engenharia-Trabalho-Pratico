# Desvios Ambientais por Falha Humana — Modelo Baseado em Agentes
### ELE637 Pensamento Sistêmico em Engenharia — Trabalho Prático

---

## 1. Título e Contexto

Este repositório contém um **modelo baseado em agentes (ABM — Agent-Based Model)** para estudar a dinâmica de **desvios ambientais causados por falha humana** (descarte incorreto de resíduos, vazamentos, lixo fora do lugar) em um ambiente industrial. O modelo é a versão reformulada do ABM do Grupo 3 e reproduz as figuras do relatório.

No ambiente simulado:
- **Trabalhadores** executam as tarefas diárias. Cada um pode cometer um erro (deixar resíduo na célula onde está) e pode corrigir o resíduo que encontra.
- **Corretores** fazem a supervisão. Erram menos, corrigem mais e, por estarem presentes, reduzem a chance de erro dos trabalhadores que estão por perto.
- **Resíduo** é a marca deixada no ambiente (grade). Ele fica parado, é visível para quem está por perto e estimula novos erros na vizinhança (contágio).

**Pergunta do modelo:** como a pressão operacional, a supervisão e a moral determinam se a desordem se estabiliza em um nível baixo ou escala, e quais alavancas reduzem o erro? (mesma pergunta da Seção 2.2 do relatório)

**Escala de tempo:** um passo corresponde a cerca de uma hora de operação; 600 passos cobrem algumas semanas de turnos.

**Mudanças em relação à versão anterior (G3):** a pressão operacional $P$ e a moral $M$ passaram a ser **exógenas e constantes** em cada execução (não há mais moral decaindo com a desordem). Os agentes agem sobre a **própria célula** (e não sobre células adjacentes), o resíduo é uma **grade binária** e os corretores podem seguir três **políticas de movimento**.

---

## 2. Relação com o Diagrama de Loop Causal

Os nomes dos laços seguem o DLC do relatório (Seção 3). O modelo computacional representa diretamente só os mecanismos rápidos; os laços com atraso entram como parâmetros exógenos.

| Mecanismo no modelo | Tipo | Laço do DLC | Como aparece no código |
|---|---|---|---|
| Contágio | Reforço (+) | **R1** (desordem visível) | Resíduo $\rightarrow$ $\uparrow$ desordem visível $D$ $\rightarrow$ $\uparrow$ probabilidade de erro $\rightarrow$ mais resíduo |
| Correção em campo | Balanceador (−) | — (mecanismo local, não está no DLC) | Quanto mais resíduo, mais células são corrigidas, com probabilidade $\sigma(c + \gamma M)$ |
| Supervisão em campo | Balanceador (−) só com a política `reativa` | parte de **B1** (supervisão) | Corretor por perto $\rightarrow$ $S = 1$ $\rightarrow$ $\downarrow$ erro. Só fecha laço se o corretor for atraído pela desordem; com `aleatoria` e `cobertura` é uma influência sem realimentação |
| Medidas administrativas e pressão | **R2** e **B1** | — | Por padrão, $P$ exógeno e constante em cada execução. Com `pressao_dinamica=True`, cada erro dispara uma medida administrativa com atraso (seção 2.1) |
| Medida social e moral | **B2** e **B3** | — | Por padrão, $M_i$ fixo por agente. Com `moral_dinamica=True`, cada erro eliminado melhora a moral com atraso (seção 2.1) |

**Por que sem atrasos no cenário base:** a implementação de medidas administrativas e a formação da moral levam semanas a meses, mais do que o horizonte de uma execução. Por isso, nas figuras do relatório, $P$ e $M$ são constantes em cada execução. As dinâmicas com atraso abaixo estão implementadas, mas vêm **desligadas por padrão**, e com elas desligadas o modelo dá exatamente os mesmos resultados.

### 2.1 Dinâmicas com atrasos (opcionais, `model/dinamicas.py`)

Ligadas por `pressao_dinamica=True` e `moral_dinamica=True` em `Params`, ou por `--pressao-dinamica` e `--moral-dinamica` no `run_simulacao.py`.

**Pressão (laços R2 e B1).** Restrição: `0 < a < c < b`. Cada erro novo agenda três eventos:

| Evento | Variação de $P$ | Quando | Laço do DLC |
|---|---|---|---|
| Início da medida administrativa | $+p$ | $c$ passos depois | R2: a medida aumenta a pressão |
| Fim do pico da medida | $-p$ | $c + a$ passos depois | — |
| Efeito preventivo consolidado | $-q$ | $c + b$ passos depois | B1: a medida reduz o desvio, com atraso |

Se $P$ ficar abaixo de `pressaoMin` por `h` passos seguidos, volta ao piso. `z` é uma influência externa contínua (fator externo do DLC).

**Moral (laço B3).** A moral individual começa com média exata `moral_inicial`. Cada erro eliminado agenda uma melhora `x` na moral média, que entra `y` passos depois. A cada passo também atuam a depreciação natural (`depreciacao`) e a influência externa (`z_moral`), e a variação líquida é somada à moral de cada agente.

| Campo | Base | Significado |
|---|:---:|---|
| `pressaoMin`, `z` | 0,1; 0,0 | piso da pressão; influência externa por passo |
| `p`, `q` | 0,05; 0,02 | aumento temporário; redução consolidada |
| `a`, `c`, `b`, `h` | 5; 10; 20; 5 | duração do pico; atraso da medida; atraso da redução; passos abaixo do piso |
| `moral_inicial`, `x`, `y` | 0,5; 0,01; 10 | moral média inicial; ganho por correção; atraso do ganho |
| `depreciacao`, `z_moral` | 0,0; 0,0 | queda natural por passo; influência externa |

```
        Pressão P (exógena) ──┐          Moral M (exógena) ──┐
                              ▼                              ▼
   ┌───────────────► Probabilidade de erro ◄── Supervisão S ◄── Corretores
   │  R1 (+)                  │  (S reduz erro)
   │                          ▼
 Desordem visível D ◄──── Resíduo na grade ────► Correção (−)
   (vizinhança)                ▲                     │
                               └─────────────────────┘
```

---

## 3. Agentes do Modelo

| Agente | Quantidade | Movimento | Comete erro? | Corrige resíduo? | Atributos |
|---|:---:|---|---|---|---|
| **Trabalhador** | $N_T$ | 1 passo por ciclo, ao acaso | Sim: $\sigma(\ldots)$ com sensibilidade à desordem, pressão e supervisão | Sim: $\sigma(c_T + \gamma_T M)$ | posição, moral $M_i$ |
| **Corretor** | $K$ | 1 passo por ciclo, segundo a política (aleatória, reativa ou cobertura) | Sim, mas com intercepto menor e sem efeito da supervisão | Sim: $\sigma(c_A + \gamma_A M)$ | posição, moral $M_i$ |

O ambiente é uma grade toroidal $L \times L$ com uma célula de resíduo (0 ou 1) por posição. **Cada célula comporta no máximo um agente.** Os $N_T$ primeiros agentes são trabalhadores e os $K$ últimos são corretores.

---

## 4. Equações do Modelo

### 4.1 Probabilidade de erro
Para cada agente $i$ no passo $t$:

$$p_i^{\text{erro}} = \sigma\!\bigl(b + b_P \cdot P + b_D \cdot D_i - b_S \cdot S_i - b_M \cdot M_i\bigr), \qquad \sigma(x) = \frac{1}{1 + e^{-x}}$$

- **Trabalhador:** $z = b_T + b_{PT} P + b_{DT} D_i - b_{ST} S_i - b_{MT} M_i$
- **Corretor:** $z = b_A + b_{PA} P + b_{DA} D_i - b_{MA} M_i$ (sem o termo de supervisão)

Onde:
- $D_i$: **desordem visível**, fração das 8 células da vizinhança de Moore (sem a célula própria) que têm resíduo;
- $S_i \in \{0, 1\}$: **supervisão**, vale 1 se há ao menos um corretor a distância de Chebyshev $\le r_s$ (grade toroidal);
- $P$: pressão operacional (aumenta o erro); $M_i$: moral individual (reduz o erro).

### 4.2 Probabilidade de correção

$$p_i^{\text{corr}} = \sigma\!\bigl(c + \gamma \cdot M_i\bigr)$$

com $(c, \gamma) = (c_T, \gamma_T)$ para trabalhadores e $(c_A, \gamma_A)$ para corretores. É constante no tempo, pois $M_i$ é fixo.

### 4.3 Moral individual
Sorteada uma vez no início da simulação e mantida fixa:

$$M_i \sim \mathcal{N}(\bar{M},\, \sigma_M^2), \quad M_i \in [0, 1] \;\;(\text{truncada})$$

### 4.4 Atualização do resíduo da célula do agente
Com o estado do início do passo, cada agente sorteia um erro e uma correção. Na célula onde está:

$$\text{resíduo} \leftarrow \begin{cases} 1 & \text{se houve erro} \\ 0 & \text{se não houve erro, havia resíduo e houve correção} \\ \text{resíduo anterior} & \text{caso contrário} \end{cases}$$

Se erro e correção ocorrem no mesmo passo, **o erro prevalece**.

### 4.5 Valores de referência (cenário base, $D = 0$, $S = 0$)
Calculados a partir das equações com os parâmetros base ($P = 0{,}5$, $M = 0{,}5$):

| Grandeza | Trabalhador | Corretor |
|---|:---:|:---:|
| Probabilidade de erro | $\sigma(-2{,}4) \approx 8\%$ | $\sigma(-3{,}7) \approx 2{,}4\%$ |
| Probabilidade de correção | $\sigma(0) = 50\%$ | $\sigma(2) \approx 88\%$ |

---

## 5. Parâmetros do Modelo

Definidos na dataclass `Params` em `configs/params.py`.

### Ambiente e agentes

| Símbolo | Campo | Valor base | Significado |
|---|---|:---:|---|
| $L$ | `L` | 30 | Lado da grade toroidal (900 células) |
| $N_T$ | `N_T` | 120 | Número de trabalhadores |
| $K$ | `K` | 8 | Número de corretores |
| $r_s$ | `r_s` | 3 | Raio de supervisão (distância de Chebyshev) |
| $T$ | `T` | 600 | Passos de tempo |
| — | `seed` | 0 | Semente aleatória (as simulações usam sementes `0, 1, 2, ...`) |
| — | `init` | 0,0 | Fração inicial de células com resíduo |

### Pressão e moral (exógenas)

| Símbolo | Campo | Valor base | Significado |
|---|---|:---:|---|
| $P$ | `P` | 0,5 | Pressão operacional |
| $\bar{M}$ | `M_bar` | 0,5 | Moral média |
| $\sigma_M$ | `M_sd` | 0,25 | Dispersão da moral entre agentes |

### Probabilidade de erro

| Símbolo | Campo | Valor base | Significado |
|---|---|:---:|---|
| $b_T$ / $b_A$ | `bT` / `bA` | −2,0 / −3,0 | Intercepto (trabalhadores / corretores) |
| $b_{PT}$ / $b_{PA}$ | `bPT` / `bPA` | 1,2 / 0,6 | Peso da pressão |
| $b_{DT}$ / $b_{DA}$ | `bDT` / `bDA` | 1,4 / 1,4 | Peso da desordem visível (contágio) |
| $b_{ST}$ | `bST` | 1,0 | Peso da supervisão (só trabalhadores) |
| $b_{MT}$ / $b_{MA}$ | `bMT` / `bMA` | 2,0 / 2,0 | Peso da moral |

### Probabilidade de correção

| Símbolo | Campo | Valor base | Significado |
|---|---|:---:|---|
| $c_T$ / $c_A$ | `cT` / `cA` | −1,5 / 1,0 | Intercepto (trabalhadores / corretores) |
| $\gamma_T$ / $\gamma_A$ | `gT` / `gA` | 3,0 / 2,0 | Peso da moral |

### Política de movimento dos corretores

| Campo | Valor base | Significado |
|---|:---:|---|
| `politica` | `"aleatoria"` | `"aleatoria"`, `"reativa"` ou `"cobertura"` (ver seção 6) |
| `eps` | 0,1 | Probabilidade de o corretor ignorar a política e andar ao acaso |

### Parâmetros da análise (`model/model.py`)

| Constante | Valor | Significado |
|---|:---:|---|
| `SEMENTES` | `range(10)` | Repetições do cenário base |
| `JANELA_FINAL` | 50 | A "desordem final" é a média dos últimos 50 passos |

---

## 6. Ciclo de Atualização

A cada passo de tempo (função `simular` em `model/model.py`):

1. **Percepção:** cada agente calcula a desordem visível $D_i$ (vizinhança de Moore) e a supervisão $S_i$ (corretor a distância $\le r_s$).
2. **Erro e correção:** com o estado do início do passo, cada agente sorteia se comete erro e se corrige. O resíduo da célula do agente é atualizado conforme a seção 4.4.
3. **Movimento:** os agentes se movem **um por vez, em ordem aleatória** (atualização assíncrona). Cada um escolhe entre ficar ou ir para uma das 8 células vizinhas livres.
   - **Trabalhadores:** escolhem ao acaso entre as opções livres.
   - **Corretores:** seguem a política configurada, mas com probabilidade `eps` andam ao acaso.

| Política | Regra de movimento do corretor |
|---|---|
| `aleatoria` | Escolhe ao acaso entre as opções livres. |
| `reativa` | Vai para a opção com **mais resíduo** na janela de raio $r_s$ (desempate ao acaso). |
| `cobertura` | Vai para a opção que **maximiza a distância ao corretor mais próximo** (espalha os corretores pela planta). |

Com $K < 2$, as políticas `reativa` e `cobertura` se comportam como `aleatoria`.

---

## 7. Medidas Macroscópicas

A cada passo são registradas:

- **`desordem`:** fração de células com resíduo, $\text{waste.mean()}$;
- **`erro`:** fração de trabalhadores que cometeram erro no passo;
- **`prejuizo`:** número total de células com resíduo, $\text{waste.sum()}$ (calculada, mas não plotada nas figuras atuais).

Nas comparações entre cenários usa-se a **desordem final**: média da `desordem` nos últimos `JANELA_FINAL = 50` passos, tomada sobre as sementes.

---

## 8. Estrutura do Repositório

```
.
├── configs/
│   ├── params.py            # dataclass Params (todos os parâmetros do modelo)
│   └── paths.py             # caminhos do projeto (OUTPUT_DIR, PERSISTENCIA_DIR, ...)
├── model/
│   ├── model.py             # simulação (simular) e geração das figuras
│   ├── dinamicas.py         # dinâmicas de pressão e moral com atrasos (opcionais)
│   ├── persistencia.py      # salvar/carregar simulações em JSON e CSV
│   └── utils/
│       └── interface.py     # reservado (vazio por enquanto)
├── outputs/                 # figuras geradas (PNG), fig1 a fig6
├── persistencia/            # dados das simulações salvas (ignorado pelo git)
├── tests/
│   ├── test_persistencia.py     # testes da persistência
│   ├── test_pressao_dinamica.py # testes da dinâmica de pressão
│   └── test_moral_dinamica.py   # testes da dinâmica de moral
├── relatorio/
│   ├── relatorio.tex        # relatório (lê as figuras direto de ../outputs)
│   ├── referencias.bib      # bibliografia (usada também pelos slides)
│   └── figuras/             # diagrama de loop causal
├── slides/
│   ├── slides.tex           # apresentação em Beamer (formato das aulas)
│   └── figuras/             # logos e diagrama de loop causal
├── requirements.txt         # dependências com versões fixadas
├── run_model.py             # gera todas as figuras do relatório
├── run_simulacao.py         # roda simulações pela linha de comando e salva os dados
└── README.md
```

---

## 9. Como Rodar

### Pré-requisitos
Python 3 recente (3.11 ou superior recomendado, pois o `requirements.txt` fixa versões novas das bibliotecas).

### Instalação

```bash
git clone https://github.com/Rafioio/Pensamento-Sistemico-em-Engenharia-Trabalho-Pratico.git
cd Pensamento-Sistemico-em-Engenharia-Trabalho-Pratico

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Mac/Linux:             source .venv/bin/activate

python -m pip install -r requirements.txt
```

### Execução
**Sempre a partir da raiz do repositório** (a pasta que contém `run_model.py`), porque os módulos são importados como `configs.params` e `model.model`:

```bash
python run_model.py
```

O script usa o backend `Agg` do matplotlib: **não abre janelas**, apenas salva os PNGs em `outputs/`. A pasta `outputs/` precisa existir (ela já vem no repositório). A execução pode levar alguns minutos, porque roda centenas de simulações (as figuras 3 e 4 são varreduras de parâmetros).

Para rodar só uma figura, ou simular com outros parâmetros:

```python
from dataclasses import replace
from configs.params import Params
from model.model import simular, fig_extremos

par = replace(Params(), K=12, P=0.8, politica="reativa", seed=1)
res = simular(par)
print(res["desordem"][-50:].mean())   # desordem final
```

### Simulações com persistência de dados (`run_simulacao.py`)

Para rodar simulações com persistência de dados em `persistencia/`:

```bash
# Execução padrão (sementes 0, 1 e 2, 600 passos cada):
python run_simulacao.py

# Personalizando sementes, passos e exportando também série em CSV:
python run_simulacao.py --seeds 42 123 999 --passos 300 --salvar-csv

# Ajustando parâmetros operacionais (pressão, número de corretores):
python run_simulacao.py --seeds 1 2 3 --pressao 0.8 --corretores 12 --politica reativa

# Ligando as dinâmicas de pressão e moral com atrasos:
python run_simulacao.py --pressao-dinamica --moral-dinamica --seeds 42 123 --salvar-csv
```

### Testes

```bash
python tests/test_pressao_dinamica.py
python tests/test_moral_dinamica.py
python tests/test_persistencia.py
```

### Formato dos dados salvos

Os resultados de cada simulação são salvos em `persistencia/sim_<timestamp>_seed_<seed>.json`.

Formato do JSON:

```json
{
  "seed": 42,
  "timestamp": "2026-11-23T01:50:37.803814",
  "parametros_iniciais": {
    "L": 30,
    "N_T": 120,
    "K": 8,
    "r_s": 3,
    "T": 600,
    "P": 0.5,
    "M_bar": 0.5,
    "politica": "aleatoria",
    ...
  },
  "total_erros_criados": 451,
  "total_erros_eliminados": 286,
  "resumo": {
    "passos_totais": 600,
    "erros_ativos_final": 112,
    "desordem_final": 0.1244,
    "desordem_media_janela_final": 0.0864,
    "moral_media_final": 0.5210
  },
  "serie_temporal": [
    {
      "passo": 0,
      "moral_media": 0.5210,
      "erros_ativos": 8,
      "pressao": 0.5,
      "desordem": 0.0089,
      "taxa_erro_trabalhadores": 0.0667,
      "erros_criados_passo": 8,
      "erros_eliminados_passo": 0
    },
    ...
  ]
}
```

Para carregar em Python (o `pandas` é opcional e não está no `requirements.txt`; sem ele, a série volta como lista de dicionários):

```python
from model.persistencia import carregar_simulacao, carregar_para_dataframe
import pandas as pd

# Carregamento nativo:
dados = carregar_simulacao("persistencia/sim_20261123_015037_seed_42.json")
print("Seed:", dados["seed"])
print("Total erros criados:", dados["total_erros_criados"])
print("Total erros eliminados:", dados["total_erros_eliminados"])

# Carregamento em DataFrame para gráficos e relatórios:
metadados, df = carregar_para_dataframe("persistencia/sim_20261123_015037_seed_42.json")
print(df.head())

# Exemplo de gráfico rápido:
df.plot(x="passo", y=["moral_media", "desordem", "pressao"])
```

### Relatório e slides

O relatório e os slides estão em LaTeX dentro do repositório e leem os gráficos direto de `outputs/`. Depois de rodar `python run_model.py`, basta recompilar para que as figuras novas entrem no PDF.

```bash
cd relatorio
pdflatex relatorio.tex && bibtex relatorio && pdflatex relatorio.tex && pdflatex relatorio.tex

cd ../slides
pdflatex slides.tex && bibtex slides && pdflatex slides.tex && pdflatex slides.tex
```

No Overleaf, importe o repositório inteiro (ou suba a pasta toda num .zip) e defina `relatorio/relatorio.tex` ou `slides/slides.tex` como documento principal; os caminhos `../outputs` e `../relatorio/referencias.bib` só funcionam com essa estrutura.

---

## 10. Saída Esperada

### Terminal

```text
-> fig_cenario_base
Cenário base: desordem final = 0.16
-> fig_extremos
Extremo base: desordem final = 0.16
Extremo sem corretores (K=0): desordem final = 0.22
Extremo pressão mínima (P=0): desordem final = 0.09
Extremo pressão máxima (P=1): desordem final = 0.28
Extremo moral nula: desordem final = 0.64
Extremo moral máxima: desordem final = 0.03
-> fig_mapa_PK
-> fig_sensibilidade
-> fig_choque
-> fig_limiar
Limiar init=0.0: 0.0->0.131, ..., 5.0->0.743, ...
Limiar init=0.7: 0.0->0.131, ..., 5.0->0.743, ...
Figuras salvas em .../outputs
```

### Figuras (em `outputs/`)

| Arquivo | Conteúdo | Leitura principal |
|---|---|---|
| `fig1_cenario_base.png` | Desordem e taxa de erro ao longo do tempo (média ± desvio de 10 sementes) e estado final da grade com os corretores | A desordem sobe nos primeiros ~50 passos e se estabiliza em torno de 0,16; a taxa de erro dos trabalhadores fica perto de 0,09 |
| `fig2_extremos.png` | Cenário base contra valores extremos (K=0, P=0, P=1, moral nula, moral máxima) | A moral é o parâmetro de maior efeito: moral nula leva a cerca de 0,64 de desordem e moral máxima a cerca de 0,03. Sem corretores fica em torno de 0,22; P=1 em torno de 0,27; P=0 em torno de 0,09 |
| `fig3_mapa_PK.png` | Mapa de calor da desordem final em função da pressão $P$ e do número de corretores $K$ | Variação gradual, de 0,07 ($P=0$, $K=16$) a 0,38 ($P=1$, $K=0$); sem ponto de virada |
| `fig4_sensibilidade.png` | Sensibilidade a $b_D$, $b_S$, $r_s$ e $c_T$, para as três políticas | $c_T$ tem o maior efeito (0,34 a 0,10). As três políticas dão 0,157, 0,151 e 0,152 no cenário base, dentro do ruído |
| `fig5_choque_pressao.png` | Resposta a um pulso de pressão ($P = 1$ nos passos 100 a 150) | A desordem sobe durante o pulso (pico perto de 0,28) e **volta ao patamar do cenário base** cerca de 50 passos depois, sem efeito permanente |
| `fig6_limiar_contagio.png` | Desordem final em função do peso do contágio $b_D$, partindo da grade limpa (`init = 0`) e da grade 70% suja (`init = 0,7`) | As duas curvas coincidem (um único equilíbrio, sem histerese), mas a resposta é não linear: 0,16 em $b_D = 1{,}4$, 0,23 em 2,8, 0,74 em 5 e quase 1 acima de 6 |

*Os valores citados são médias sobre as sementes e podem variar na segunda casa decimal; confira os números impressos no terminal.*

---

## 11. Limitações

- Nas figuras do relatório, $P$ e $M$ são exógenos e constantes. As dinâmicas com atraso (seção 2.1) já estão implementadas, mas ainda não foram usadas nas análises nem calibradas.
- Não há turnos, tarefas ou layout de planta: a grade é homogênea e toroidal.
- Trabalhadores se movem ao acaso, sem rotinas de trabalho.
- As figuras 3 e 4 usam poucas sementes por ponto (`n = 3`) e a figura 6 usa 4, então pequenas diferenças entre curvas (por exemplo, entre políticas) estão dentro do ruído.
- Os parâmetros são ilustrativos e não foram calibrados com dados reais.
