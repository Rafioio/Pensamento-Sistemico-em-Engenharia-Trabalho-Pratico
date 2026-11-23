# Pensamento Sistêmico em Engenharia - Simulação Baseada em Agentes (ABM)

Modelo Baseado em Agentes (ABM) para estudo de dinâmicas organizacionais, contágio de desordem, pressão operacional, moral dos trabalhadores e atuação de supervisores/corretores.

---

## 📁 Estrutura de Diretórios

```
Pensamento-Sistemico-em-Engenharia-Trabalho-Pratico/
│
├── configs/
│   ├── params.py         # Dataclass Params com parâmetros do modelo e validações
│   └── paths.py          # Resolução de diretórios (ROOT, OUTPUTS, PERSISTENCIA)
│
├── model/
│   ├── __init__.py       # Exportações públicas do pacote
│   ├── model.py          # Lógica central do ABM, simular(), rodar() e figuras
│   ├── dinamicas.py      # Dinâmica com delays para Pressão e Moral
│   ├── persistencia.py   # Serialização JSON/CSV, validação e carregamento
│   └── utils/
│       └── interface.py  # Funções auxiliares de interface
│
├── outputs/              # Gráficos e figuras geradas do artigo
├── persistencia/         # Armazenamento persistente das simulações (JSON/CSV)
│   └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── test_persistencia.py       # Validação geral de persistência
│   ├── test_pressao_dinamica.py   # Testes unitários da dinâmica de pressão
│   └── test_moral_dinamica.py     # Testes unitários da dinâmica de moral
│
├── run_model.py          # Geração de todas as figuras comparativas
├── run_simulacao.py      # Execução de simulações com persistência via CLI
├── requirements.txt      # Dependências do projeto
└── README.md             # Documentação do projeto
```

---

## ⏱️ Dinâmicas Temporais com Atrasos (Delays)

### 1. Dinâmica de Pressão (`pressão.txt`)
- **Restrição:** `0 < a < c < b`
- **Gatilho (novo erro criado):** agenda 3 eventos:
  1. `(+p, c)`: início da medida administrativa
  2. `(-p, c+a)`: fim do pico da medida administrativa
  3. `(-q, c+b)`: efeito preventivo consolidado
- **Piso mínimo:** se `pressao < pressaoMin` por `h` turnos consecutivos, força retorno ao piso.

### 2. Dinâmica de Moral (`moral.txt`)
- **Inicialização:** agentes iniciam com desvios centrados garantindo média exata igual a `moral_inicial`.
- **Gatilho (erro eliminado):** agenda `CD` com `impacto = x` e `tempo_restante = y`.
- **Atualização:** a cada ciclo aplica maturação de CDs, depreciação natural e influência externa (`z_moral`), propagando o delta líquido para a moral individual de cada agente.

---

## 🚀 Como Executar

### 1. Executar simulações com persistência de dados

```bash
# Execução padrão (estática, cenário base):
python run_simulacao.py

# Ativando dinâmicas de pressão e moral com delays:
python run_simulacao.py --pressao-dinamica --moral-dinamica --seeds 42 123 --salvar-csv
```

### 2. Rodar suites de testes unitários

```bash
python tests/test_pressao_dinamica.py
python tests/test_moral_dinamica.py
python tests/test_persistencia.py
```


---

## 📊 Estrutura dos Dados Persistidos

Os resultados de cada simulação são salvos em `persistencia/sim_<timestamp>_seed_<seed>.json`.

### Formato do JSON:

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

---

## 📈 Carregando Dados em Python / Pandas

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
