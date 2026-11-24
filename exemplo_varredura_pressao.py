"""Script de Varredura de Parâmetros e Análise de Sensibilidade do Modelo ABM.

Realiza análises de sensibilidade alterando UMA variável por vez a partir dos
valores BASE, executando múltiplas sementes (mínimo 3) para calcular média e desvio padrão.

Variáveis suportadas:
- Pressão operacional (pressao): 0.0 a 1.0
- Moral média (moral): 0.0 a 1.0
- Número de corretores (K): 1 a 8
- Correção basal dos trabalhadores (cT): -3.0 a 0.0
- Correção basal dos corretores (cA): 0.0 a 3.0
- Sensibilidade à moral dos trabalhadores (gT): 0.0 a 5.0
- Sensibilidade à moral dos corretores (gA): 0.0 a 5.0
- Tipos de movimento / política dos corretores (movimento): ["aleatoria", "reativa", "cobertura"]
"""

from __future__ import annotations
import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

# Garante raiz do projeto no path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
from configs.paths import OUTPUT_DIR
from model.model import BASE, JANELA_FINAL, simular

# Definição das configurações de cada varredura
CONFIGURACOES_VARREDURA: Dict[str, Dict[str, Any]] = {
    "pressao": {
        "titulo": "Pressão Operacional Base (P)",
        "param_campo": "P",
        "valores": np.linspace(0.0, 1.0, 11),  # [0.0, 0.1, ..., 1.0]
        "xlabel": "Pressão Operacional (P)",
        "tipo": "continuo",
    },
    "moral": {
        "titulo": "Moral Média Inicial / Basal",
        "param_campo": "moral",  # Atualiza M_bar e moral_inicial
        "valores": np.linspace(0.0, 1.0, 11),  # [0.0, 0.1, ..., 1.0]
        "xlabel": "Moral Média (M_bar)",
        "tipo": "continuo",
    },
    "K": {
        "titulo": "Número de Corretores (K)",
        "param_campo": "K",
        "valores": np.arange(1, 9),  # 1, 2, 3, 4, 5, 6, 7, 8
        "xlabel": "Número de Corretores (K)",
        "tipo": "discreto",
    },
    "cT": {
        "titulo": "Correção Basal dos Trabalhadores (cT)",
        "param_campo": "cT",
        "valores": np.linspace(-3.0, 0.0, 7),  # -3.0, -2.5, ..., 0.0
        "xlabel": "Parâmetro cT",
        "tipo": "continuo",
    },
    "cA": {
        "titulo": "Correção Basal dos Corretores (cA)",
        "param_campo": "cA",
        "valores": np.linspace(0.0, 3.0, 7),  # 0.0, 0.5, ..., 3.0
        "xlabel": "Parâmetro cA",
        "tipo": "continuo",
    },
    "gT": {
        "titulo": "Sensibilidade à Moral dos Trabalhadores (gT)",
        "param_campo": "gT",
        "valores": np.linspace(0.0, 5.0, 6),  # 0.0, 1.0, ..., 5.0
        "xlabel": "Parâmetro gT",
        "tipo": "continuo",
    },
    "gA": {
        "titulo": "Sensibilidade à Moral dos Corretores (gA)",
        "param_campo": "gA",
        "valores": np.linspace(0.0, 5.0, 6),  # 0.0, 1.0, ..., 5.0
        "xlabel": "Parâmetro gA",
        "tipo": "continuo",
    },
    "movimento": {
        "titulo": "Tipos de Movimento / Política dos Corretores",
        "param_campo": "politica",
        "valores": ["aleatoria", "reativa", "cobertura"],
        "xlabel": "Política de Movimento",
        "tipo": "categorico",
    },
}


def _configurar_parametros_para_valor(campo: str, val: Any, semente: int, T: int) -> Any:
    """Aplica o valor de teste mantendo todos os outros parâmetros no BASE."""
    if campo == "moral":
        # Sincroniza tanto M_bar quanto moral_inicial
        return replace(BASE, M_bar=float(val), moral_inicial=float(val), seed=semente, T=T)
    elif campo == "K":
        return replace(BASE, K=int(val), seed=semente, T=T)
    elif campo in ("cT", "cA", "gT", "gA", "P"):
        return replace(BASE, **{campo: float(val), "seed": semente, "T": T})
    elif campo == "politica":
        return replace(BASE, politica=str(val), seed=semente, T=T)
    else:
        return replace(BASE, **{campo: val, "seed": semente, "T": T})


def executar_varredura(
    param_chave: str,
    sementes: List[int] = [0, 1, 2, 3, 4, 6],
    T: int = 600,
    salvar_simulacoes: bool = False,
    salvar_grafico: bool = True,
) -> Dict[str, Any]:
    """Executa a varredura para uma variável específica alterando 1 parâmetro por vez."""
    cfg = CONFIGURACOES_VARREDURA[param_chave]
    campo = cfg["param_campo"]
    valores = cfg["valores"]
    titulo = cfg["titulo"]
    tipo = cfg["tipo"]

    medias_erros = []
    desvios_erros = []
    medias_desordem = []
    desvios_desordem = []

    print("-" * 65)
    print(f" VARREDURA: {titulo}")
    print(f" Valores ({len(valores)}): {valores} | Sementes ({len(sementes)}): {sementes} | T: {T}")
    print("-" * 65)

    for val in valores:
        erros_s = []
        desordem_s = []

        for s in sementes:
            par = _configurar_parametros_para_valor(campo, val, s, T)
            res = simular(par, salvar=salvar_simulacoes)

            # Média da janela final
            erros_s.append(np.mean(res["erros_ativos"][-JANELA_FINAL:]))
            desordem_s.append(np.mean(res["desordem"][-JANELA_FINAL:]))

        m_erro = float(np.mean(erros_s))
        s_erro = float(np.std(erros_s))
        m_des = float(np.mean(desordem_s))
        s_des = float(np.std(desordem_s))

        medias_erros.append(m_erro)
        desvios_erros.append(s_erro)
        medias_desordem.append(m_des)
        desvios_desordem.append(s_des)

        rotulo_val = f"{val:5.2f}" if isinstance(val, (int, float, np.floating, np.integer)) else f"{val:>10}"
        print(f"  {campo} = {rotulo_val} | Erros Finais: {m_erro:6.1f} (± {s_erro:4.1f}) | Desordem: {m_des:.4f}")

    dados_resultado = {
        "chave": param_chave,
        "titulo": titulo,
        "campo": campo,
        "tipo": tipo,
        "xlabel": cfg["xlabel"],
        "valores": valores,
        "medias_erros": np.array(medias_erros),
        "desvios_erros": np.array(desvios_erros),
        "medias_desordem": np.array(medias_desordem),
        "desvios_desordem": np.array(desvios_desordem),
    }

    if salvar_grafico:
        salvar_grafico_individual(dados_resultado)

    return dados_resultado


def salvar_grafico_individual(dados: Dict[str, Any]) -> Path:
    """Gera e salva o gráfico individual da variável analisada."""
    fig, ax1 = plt.subplots(figsize=(8.5, 4.5))

    valores = dados["valores"]
    m_erros = dados["medias_erros"]
    s_erros = dados["desvios_erros"]
    m_des = dados["medias_desordem"]
    tipo = dados["tipo"]
    chave = dados["chave"]

    cor_erro = "crimson"
    cor_desordem = "#2b2b2b"

    if tipo == "categorico":
        # Gráfico de barras para variáveis categóricas (políticas de movimento)
        x_indices = np.arange(len(valores))
        ax1.bar(
            x_indices,
            m_erros,
            yerr=s_erros,
            capsize=5,
            color=cor_erro,
            alpha=0.75,
            edgecolor=cor_erro,
            width=0.45,
            label="Erros Ativos (Média ± Desvio)",
        )
        ax1.set_xticks(x_indices)
        ax1.set_xticklabels([str(v) for v in valores], fontsize=10)
    else:
        # Gráfico de linha contínua/discreta com banda de desvio padrão
        ax1.plot(valores, m_erros, "o-", color=cor_erro, linewidth=2, label="Erros Ativos (Média)")
        ax1.fill_between(
            valores,
            m_erros - s_erros,
            m_erros + s_erros,
            color=cor_erro,
            alpha=0.2,
            label="Desvio Padrão (±1σ)",
        )
        if tipo == "discreto":
            ax1.set_xticks(valores)

    ax1.set_xlabel(dados["xlabel"], fontsize=11)
    ax1.set_ylabel("Quantidade de Erros Ativos no Fim", color=cor_erro, fontsize=11)
    ax1.tick_params(axis="y", labelcolor=cor_erro)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Eixo secundário: Fração de desordem
    ax2 = ax1.twinx()
    if tipo == "categorico":
        ax2.plot(x_indices, m_des, "s--", color=cor_desordem, linewidth=1.5, markersize=7, label="Fração de Desordem")
    else:
        ax2.plot(valores, m_des, "s--", color=cor_desordem, linewidth=1.5, alpha=0.7, label="Fração de Desordem")
    ax2.set_ylabel("Fração de Desordem da Grade", color=cor_desordem, fontsize=11)
    ax2.tick_params(axis="y", labelcolor=cor_desordem)

    plt.title(f"Sensibilidade: Erros Finais vs {dados['titulo']}", fontsize=12)
    ax1.legend(loc="upper left")
    fig.tight_layout()

    arquivo_saida = OUTPUT_DIR / f"varredura_{chave}.png"
    fig.savefig(arquivo_saida, dpi=200)
    plt.close(fig)
    print(f"  -> Gráfico salvo em: {arquivo_saida.resolve()}")
    return arquivo_saida


def gerar_painel_completo(todos_resultados: List[Dict[str, Any]]) -> Path:
    """Gera um painel comparativo geral 4x2 com todos os parâmetros avaliados."""
    n_vars = len(todos_resultados)
    fig, axs = plt.subplots(4, 2, figsize=(15, 16))
    axs_flat = axs.flatten()

    for idx, dados in enumerate(todos_resultados):
        ax = axs_flat[idx]
        valores = dados["valores"]
        m_erros = dados["medias_erros"]
        s_erros = dados["desvios_erros"]
        tipo = dados["tipo"]

        if tipo == "categorico":
            x_idx = np.arange(len(valores))
            ax.bar(x_idx, m_erros, yerr=s_erros, capsize=4, color="crimson", alpha=0.7, edgecolor="darkred")
            ax.set_xticks(x_idx)
            ax.set_xticklabels([str(v) for v in valores], fontsize=9)
        else:
            ax.plot(valores, m_erros, "o-", color="crimson", linewidth=1.8, markersize=5)
            ax.fill_between(valores, m_erros - s_erros, m_erros + s_erros, color="crimson", alpha=0.2)
            if tipo == "discreto":
                ax.set_xticks(valores)

        ax.set_title(dados["titulo"], fontsize=11, fontweight="bold")
        ax.set_xlabel(dados["xlabel"], fontsize=9)
        ax.set_ylabel("Erros Ativos Finais", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4)

    # Esconde subplots extras se houver
    for j in range(n_vars, len(axs_flat)):
        fig.delaxes(axs_flat[j])

    fig.suptitle("Análise Global de Sensibilidade - Erros Finais por Parâmetro (ABM)", fontsize=14, y=0.995)
    fig.tight_layout()

    arquivo_painel = OUTPUT_DIR / "varredura_painel_completo.png"
    fig.savefig(arquivo_painel, dpi=200)
    plt.close(fig)
    print(f"\n[OK] Painel consolidado salvo em: {arquivo_painel.resolve()}")
    return arquivo_painel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Varredura de parâmetros e análise de sensibilidade com gráficos de erro."
    )
    parser.add_argument(
        "--parametro",
        type=str,
        default="todos",
        choices=["todos", "pressao", "moral", "K", "cT", "cA", "gT", "gA", "movimento"],
        help="Variável para varredura (ou 'todos' para rodar toda a bateria). Padrão: 'todos'.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[0, 1, 2],
        help="Sementes aleatórias por ponto (mínimo 3 recomendado). Padrão: 0 1 2.",
    )
    parser.add_argument(
        "--passos",
        type=int,
        default=300,
        help="Duração T em ticks de cada simulação. Padrão: 300.",
    )
    parser.add_argument(
        "--salvar-simulacoes",
        action="store_true",
        help="Se ativado, persiste os dados JSON de cada corrida em persistencia/.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 65)
    print(" BATERIA DE ANÁLISE DE SENSIBILIDADE ABM")
    print(f" Parâmetro: {args.parametro} | Sementes: {args.seeds} | Passos (T): {args.passos}")
    print("=" * 65)

    if args.parametro == "todos":
        chaves = list(CONFIGURACOES_VARREDURA.keys())
    else:
        chaves = [args.parametro]

    resultados = []
    for chave in chaves:
        res = executar_varredura(
            param_chave=chave,
            sementes=args.seeds,
            T=args.passos,
            salvar_simulacoes=args.salvar_simulacoes,
            salvar_grafico=True,
        )
        resultados.append(res)

    if len(resultados) > 1:
        gerar_painel_completo(resultados)

    print("\n" + "=" * 65)
    print(f" Concluído! Gráficos gerados com sucesso na pasta: {OUTPUT_DIR.resolve()}")
    print("=" * 65)


if __name__ == "__main__":
    main()
