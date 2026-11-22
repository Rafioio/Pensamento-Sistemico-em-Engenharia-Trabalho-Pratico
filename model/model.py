import os
from dataclasses import replace
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from configs.params import Params
from configs.paths import *


BASE = Params()          # cenário base (valores em abm_desvios.py)
SEMENTES = range(10)     # repetições do cenário base
JANELA_FINAL = 50        # a "desordem final" é a média dos últimos passos

import numpy as np


def janela(a, r):
    """Soma de `a` na janela (2r+1)x(2r+1) em torno de cada célula, com borda toroidal."""
    out = np.zeros(a.shape)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            out += np.roll(np.roll(a, dx, axis=0), dy, axis=1)
    return out


def simular(par: Params, P_t=None):
    """Roda uma simulação. P_t(t) opcional faz a pressão variar no tempo.
    Retorna dict com séries temporais e o estado final."""
    rng = np.random.default_rng(par.seed)
    L = par.L
    waste = np.zeros((L, L))                                   # 1 = há resíduo
    m_base = np.clip(rng.normal(par.m0, par.m_sd, (L, L)), 0, 1)  # moral "de fábrica"
    m = m_base.copy()                                          # moral atual
    pos = rng.integers(0, L, size=(par.K, 2))                  # posição dos corretores
    desordem, erro, moral, prejuizo = [], [], [], []

    for t in range(par.T):
        P = par.P if P_t is None else P_t(t)

        # --- percepção: desordem visível D e supervisão S de cada trabalhador
        D = (janela(waste, 1) - waste) / 8                     # fração de vizinhos com resíduo
        S = np.zeros((L, L))
        for x, y in pos:
            idx = np.ix_((x + np.arange(-par.r_s, par.r_s + 1)) % L,
                         (y + np.arange(-par.r_s, par.r_s + 1)) % L)
            S[idx] = 1

        # --- decisão do trabalhador (Eq. 1)
        z = par.b0 + par.bP * P + par.bD * D - par.bS * S - par.bM * m
        err = rng.random((L, L)) < 1 / (1 + np.exp(-z))
        waste = np.maximum(waste, err)

        # --- limpeza: rotineira em todo lugar, mais forte sob supervisão
        limpa = rng.random((L, L)) < np.where(S == 1, par.rho, par.rho0)
        waste = np.where(limpa, 0, waste)

        # --- evolução da moral
        m = np.clip(m + par.eta_S * S - par.eta_D * D + par.eta_R * (m_base - m), 0, 1)

        # --- movimento dos corretores
        if par.K > 0:
            if par.dirigido:
                alvo = janela(waste, par.r_s)
            for i in range(par.K):
                cand = [((pos[i, 0] + dx) % L, (pos[i, 1] + dy) % L)
                        for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                if par.dirigido:
                    pont = [alvo[c] + rng.random() * 0.5 for c in cand]  # desempate aleatório
                    pos[i] = cand[int(np.argmax(pont))]
                else:
                    pos[i] = cand[rng.integers(len(cand))]

        desordem.append(waste.mean())
        erro.append(err.mean())
        moral.append(m.mean())
        prejuizo.append(waste.sum())

    return dict(desordem=np.array(desordem), erro=np.array(erro),
                moral=np.array(moral), prejuizo=np.array(prejuizo),
                waste=waste, pos=pos, m=m)

def rodar(par, n=3, P_t=None):
    """Roda n sementes e devolve a matriz (n, T) da fração de células com resíduo."""
    return np.array([simular(replace(par, seed=s), P_t)["desordem"] for s in range(n)])


def final(par, n=3):
    return rodar(par, n)[:, -JANELA_FINAL:].mean()


def banda(ax, y, rotulo, **kw):
    m, s = y.mean(0), y.std(0)
    ax.plot(m, label=rotulo, **kw)
    ax.fill_between(range(len(m)), m - s, m + s, alpha=0.2, color=ax.lines[-1].get_color())


# ---------------------------------------------------------------- Figura 1: cenário base
def fig_cenario_base():
    runs = [simular(replace(BASE, seed=s)) for s in SEMENTES]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
    banda(ax[0], np.array([r["desordem"] for r in runs]), "desordem (células com resíduo)")
    banda(ax[0], np.array([r["erro"] for r in runs]), "taxa de erro por passo")
    ax[0].set(xlabel="passo de tempo", ylabel="fração", title="Cenário base (média ± desvio, 10 sementes)")
    ax[0].legend()
    r = runs[0]
    ax[1].imshow(r["waste"], cmap="Greys", vmin=0, vmax=1)
    ax[1].scatter(r["pos"][:, 1], r["pos"][:, 0], c="red", marker="*", s=90, label="corretores")
    ax[1].set(title="Estado final (preto = resíduo)", xticks=[], yticks=[])
    ax[1].legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig1_cenario_base.png"), dpi=200)
    print("Cenário base: desordem final =", round(np.mean([x["desordem"][-JANELA_FINAL:].mean() for x in runs]), 3))


# ---------------------------------------------------------------- Figura 2: valores extremos
def fig_extremos():
    casos = {
        "base": BASE,
        "sem corretores (K=0)": replace(BASE, K=0),
        "pressão mínima (P=0)": replace(BASE, P=0.0),
        "pressão máxima (P=1)": replace(BASE, P=1.0),
        "moral nula": replace(BASE, m0=0.0, m_sd=0.0),
        "moral máxima": replace(BASE, m0=1.0, m_sd=0.0),
    }
    fig, ax = plt.subplots(figsize=(7, 4))
    for nome, par in casos.items():
        banda(ax, rodar(par, 5), nome)
        print(f"Extremo {nome}: desordem final = {rodar(par, 5)[:, -JANELA_FINAL:].mean():.3f}")
    ax.set(xlabel="passo de tempo", ylabel="fração de células com resíduo", title="Valores extremos")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig2_extremos.png"), dpi=200)


# ---------------------------------------------------------------- Figura 3: mapa P x K
def fig_mapa_PK():
    Ps, Ks = np.linspace(0, 1, 11), np.arange(0, 13, 2)
    Z = np.array([[final(replace(BASE, P=P, K=K)) for P in Ps] for K in Ks])
    fig, ax = plt.subplots(figsize=(6.5, 4))
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="viridis_r", vmin=0, vmax=1,
                   extent=[Ps[0] - 0.05, Ps[-1] + 0.05, Ks[0] - 1, Ks[-1] + 1])
    ax.set(xlabel="pressão operacional P", ylabel="número de corretores K",
           title="Desordem final (fração de células com resíduo)")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig3_mapa_PK.png"), dpi=200)


# ---------------------------------------------------------------- Figura 4: sensibilidade
def fig_sensibilidade():
    varreduras = {
        "peso do contágio $\\beta_D$": ("bD", [1, 2, 3, 4, 5, 6]),
        "ganho de moral por supervisão $\\eta_S$": ("eta_S", [0.0, 0.01, 0.02, 0.04, 0.08]),
        "raio de supervisão $r_s$": ("r_s", [1, 2, 3, 4, 5]),
        "limpeza rotineira $\\rho_0$": ("rho0", [0.1, 0.2, 0.3, 0.4, 0.5]),
    }
    fig, axs = plt.subplots(1, 4, figsize=(13, 3.2), sharey=True)
    for ax, (titulo, (campo, valores)) in zip(axs, varreduras.items()):
        for dirigido, rot in ((True, "corretores dirigidos"), (False, "corretores aleatórios")):
            y = [final(replace(BASE, dirigido=dirigido, **{campo: v})) for v in valores]
            ax.plot(valores, y, "o-", label=rot)
        ax.set(xlabel=titulo)
    axs[0].set_ylabel("desordem final")
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig4_sensibilidade.png"), dpi=200)


# ---------------------------------------------------------------- Figura 5: choque de pressão
def fig_choque():
    def pulso(t):
        return 1.0 if 100 <= t < 150 else BASE.P
    fig, ax = plt.subplots(figsize=(7, 3.6))
    banda(ax, rodar(BASE, 5), "pressão constante")
    banda(ax, rodar(BASE, 5, pulso), "choque de pressão (P=1, passos 100-150)")
    ax.axvspan(100, 150, color="grey", alpha=0.15)
    ax.set(xlabel="passo de tempo", ylabel="fração de células com resíduo",
           title="Resposta a um choque temporário de pressão")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig5_choque_pressao.png"), dpi=200)


