"""Script exemplo: Varredura do parâmetro de Pressão (0.0 a 1.0 em passos de 0.05).

Calcula e plota a quantidade de erros ativos e a desordem na janela final
em função da pressão operacional base (P).
"""

from __future__ import annotations
import sys
from dataclasses import replace
from pathlib import Path

# Garante raiz do projeto no path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import numpy as np
from configs.paths import OUTPUT_DIR
from model.model import BASE, JANELA_FINAL, simular


def varredura_pressao():
    # 1. Definindo intervalo de varredura
    valores_pressao = np.arange(0.0, 1.05, 0.05)  # de 0.0 a 1.0 com passo 0.05
    sementes = [0, 1, 2, 3, 4]                    # 5 repetições por ponto
    T = 600                                       # passos por simulação

    medias_erros = []
    desvios_erros = []
    medias_desordem = []

    print("=" * 65)
    print(f" VARREDURA DE PARÂMETRO: PRESSÃO (P) DE 0.0 A 1.0")
    print(f" Pontos: {len(valores_pressao)} | Sementes por ponto: {len(sementes)} | T: {T}")
    print("=" * 65)

    for P in valores_pressao:
        erros_ponto = []
        desordem_ponto = []

        for s in sementes:
            par = replace(
                BASE,
                P=0.5,                    # Pressão inicial
                pressao_dinamica=True,    # Ativa dinâmicas com delay
                a=6,                      # Pico dura 6 ticks
                c=9,                      # Atraso adm de 9 ticks
                b=15,                     # Redução preventiva após 15 ticks
                p=0.08,                   # Magnitude do aumento
                q=0.04,                   # Magnitude da redução
                pressaoMin=0.1,           # Piso basal
                h=5,                      # Turnos para recuperação do piso
                moral_dinamica=True,      # Moral também dinâmica
                depreciacao=0.002,        # taxa com que a moral cai
                x=0.015,                  # valor que a moral aumenta
                y=10,                     # delay para moral aumentar
                T=T
            )

        res = simular(par, salvar=True)  # Salva JSON em persistencia/

            # Média dos últimos JANELA_FINAL passos
            erros_fim = np.mean(res["erros_ativos"][-JANELA_FINAL:])
            desordem_fim = np.mean(res["desordem"][-JANELA_FINAL:])

            erros_ponto.append(erros_fim)
            desordem_ponto.append(desordem_fim)

        media_e = float(np.mean(erros_ponto))
        desvio_e = float(np.std(erros_ponto))
        media_d = float(np.mean(desordem_ponto))

        medias_erros.append(media_e)
        desvios_erros.append(desvio_e)
        medias_desordem.append(media_d)

        print(f"P = {P:4.2f} | Erros Finais: {media_e:6.1f} (± {desvio_e:4.1f}) | Desordem: {media_d:.4f}")

    # 2. Geração do Gráfico
    medias_erros_arr = np.array(medias_erros)
    desvios_erros_arr = np.array(desvios_erros)

    fig, ax1 = plt.subplots(figsize=(9, 5))

    cor_erros = "crimson"
    ax1.plot(valores_pressao, medias_erros_arr, "o-", color=cor_erros, linewidth=2, label="Erros Ativos (Média)")
    ax1.fill_between(
        valores_pressao,
        medias_erros_arr - desvios_erros_arr,
        medias_erros_arr + desvios_erros_arr,
        color=cor_erros,
        alpha=0.2,
        label="Desvio Padrão (±1σ)",
    )
    ax1.set_xlabel("Pressão Operacional Base (P)", fontsize=11)
    ax1.set_ylabel("Quantidade de Erros Ativos no Final da Simulação", color=cor_erros, fontsize=11)
    ax1.tick_params(axis="y", labelcolor=cor_erros)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Eixo secundário: Fração de desordem
    ax2 = ax1.twinx()
    ax2.plot(valores_pressao, medias_desordem, "s--", color="black", alpha=0.6, label="Fração de Desordem da Grade")
    ax2.set_ylabel("Fração de Desordem (Células com Resíduo)", color="black", fontsize=11)
    ax2.tick_params(axis="y", labelcolor="black")

    plt.title("Sensibilidade: Quantidade de Erros Finais em Função da Pressão Base", fontsize=12)
    ax1.legend(loc="upper left")
    fig.tight_layout()

    saida_png = OUTPUT_DIR / "analise_erros_vs_pressao.png"
    fig.savefig(saida_png, dpi=200)
    print("\n" + "=" * 65)
    print(f" Concluído! Gráfico salvo em: {saida_png.resolve()}")
    print("=" * 65)


if __name__ == "__main__":
    varredura_pressao()
