import os
from dataclasses import replace
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from configs.params import Params
from configs.paths import *


BASE = Params()          # cenário base (valores em configs/params.py)
SEMENTES = range(10)     # repetições do cenário base
JANELA_FINAL = 50        # a "desordem final" é a média dos últimos passos

POLITICAS = (("aleatoria", "corretores aleatórios"),
             ("reativa", "corretores dirigidos à desordem"),
             ("cobertura", "corretores de cobertura"))
OFFS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def sig(x):
    return 1 / (1 + np.exp(-x))


def janela(a, r):
    """Soma de `a` na janela (2r+1)x(2r+1) em torno de cada célula, com borda toroidal."""
    out = np.zeros(a.shape)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            out += np.roll(np.roll(a, dx, axis=0), dy, axis=1)
    return out


def simular(par: Params, P_t=None):
    """Roda uma simulação do modelo do artigo. P_t(t) opcional faz a pressão variar no tempo.

    Os N_T primeiros agentes são trabalhadores e os K últimos são corretores.
    Retorna dict com séries temporais e o estado final."""
    rng = np.random.default_rng(par.seed)
    L, NT, K = par.L, par.N_T, par.K
    N = NT + K
    eh_corretor = np.arange(N) >= NT

    waste = (rng.random((L, L)) < par.init).astype(float)      # 1 = há resíduo
    celulas = rng.choice(L * L, N, replace=False)              # posições iniciais sem sobreposição
    pos = np.column_stack((celulas // L, celulas % L))
    ocupada = np.zeros((L, L), bool)
    ocupada[pos[:, 0], pos[:, 1]] = True

    # moral individual, fixa; probabilidade de correção (constante no tempo)
    M = np.clip(rng.normal(par.M_bar, par.M_sd, N), 0, 1)
    p_corr = np.where(eh_corretor, sig(par.cA + par.gA * M), sig(par.cT + par.gT * M))

    desordem, erro, prejuizo = [], [], []

    for t in range(par.T):
        P = par.P if P_t is None else P_t(t)
        xs, ys = pos[:, 0], pos[:, 1]

        # --- 1. percepção: D (vizinhança de Moore, sem a célula própria) e S (corretor a <= r_s)
        D = ((janela(waste, 1) - waste) / 8)[xs, ys]
        Sg = np.zeros((L, L))
        for x, y in pos[NT:]:
            idx = np.ix_((x + np.arange(-par.r_s, par.r_s + 1)) % L,
                         (y + np.arange(-par.r_s, par.r_s + 1)) % L)
            Sg[idx] = 1
        S = Sg[xs, ys]

        # --- 2. erro e 3. correção, com o estado do início do passo
        z = np.where(eh_corretor,
                     par.bA + par.bPA * P + par.bDA * D - par.bMA * M,
                     par.bT + par.bPT * P + par.bDT * D - par.bST * S - par.bMT * M)
        err = rng.random(N) < sig(z)
        corrige = rng.random(N) < p_corr
        w0 = waste[xs, ys]
        waste[xs, ys] = np.where(err, 1.0, np.where((w0 == 1) & corrige, 0.0, w0))

        # --- 4. movimento sequencial, em ordem aleatória
        alvo = janela(waste, par.r_s) if (K > 0 and par.politica == "reativa") else None
        for i in rng.permutation(N):
            x, y = pos[i]
            cand = [((x + dx) % L, (y + dy) % L) for dx, dy in OFFS]
            cand = [c for c in cand if c == (x, y) or not ocupada[c]]
            if len(cand) == 1:
                continue
            if (not eh_corretor[i] or par.politica == "aleatoria" or K < 2
                    or rng.random() < par.eps):
                novo = cand[rng.integers(len(cand))]
            else:
                if par.politica == "reativa":
                    pont = np.array([alvo[c] for c in cand])
                else:  # cobertura: maximiza a distância de Chebyshev ao corretor mais próximo
                    outros = np.delete(pos[NT:], i - NT, axis=0)
                    pont = []
                    for cx, cy in cand:
                        ddx = np.abs(outros[:, 0] - cx); ddx = np.minimum(ddx, L - ddx)
                        ddy = np.abs(outros[:, 1] - cy); ddy = np.minimum(ddy, L - ddy)
                        pont.append(np.maximum(ddx, ddy).min())
                    pont = np.array(pont)
                melhores = np.flatnonzero(pont == pont.max())
                novo = cand[rng.choice(melhores)]
            ocupada[x, y] = False
            ocupada[novo] = True
            pos[i] = novo

        desordem.append(waste.mean())
        erro.append(err[:NT].mean())
        prejuizo.append(waste.sum())

    return dict(desordem=np.array(desordem), erro=np.array(erro),
                prejuizo=np.array(prejuizo), waste=waste, pos=pos[NT:].copy(), M=M)

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
    banda(ax[0], np.array([r["erro"] for r in runs]), "taxa de erro dos trabalhadores")
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
        "moral nula": replace(BASE, M_bar=0.0, M_sd=0.0),
        "moral máxima": replace(BASE, M_bar=1.0, M_sd=0.0),
    }
    fig, ax = plt.subplots(figsize=(7, 4))
    for nome, par in casos.items():
        y = rodar(par, 5)
        banda(ax, y, nome)
        print(f"Extremo {nome}: desordem final = {y[:, -JANELA_FINAL:].mean():.3f}")
    ax.set(xlabel="passo de tempo", ylabel="fração de células com resíduo", title="Valores extremos")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig2_extremos.png"), dpi=200)


# ---------------------------------------------------------------- Figura 3: mapa P x K
def fig_mapa_PK():
    Ps, Ks = np.linspace(0, 1, 6), np.arange(0, 17, 4)
    Z = np.array([[final(replace(BASE, P=P, K=K)) for P in Ps] for K in Ks])
    fig, ax = plt.subplots(figsize=(6.5, 4))
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="viridis_r", vmin=0, vmax=1,
                   extent=[Ps[0] - 0.1, Ps[-1] + 0.1, Ks[0] - 2, Ks[-1] + 2])
    ax.set(xlabel="pressão operacional P", ylabel="número de corretores K",
           title="Desordem final (fração de células com resíduo)")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig3_mapa_PK.png"), dpi=200)


# ---------------------------------------------------------------- Figura 4: sensibilidade
def fig_sensibilidade():
    # cada varredura: (rótulo, campos alterados juntos, valores)
    varreduras = [
        ("peso do contágio $\\beta_D$", ("bDT", "bDA"), [0.0, 0.7, 1.4, 2.1, 2.8]),
        ("peso da supervisão $\\beta_S$", ("bST",), [0.0, 0.5, 1.0, 1.5, 2.0]),
        ("raio de supervisão $r_s$", ("r_s",), [1, 2, 3, 4, 5]),
        ("correção basal dos trabalhadores $c_T$", ("cT",), [-3.0, -2.25, -1.5, -0.75, 0.0]),
    ]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.2), sharey=True)
    for ax, (titulo, campos, valores) in zip(axs, varreduras):
        for pol, rot in POLITICAS:
            y = [final(replace(BASE, politica=pol, **{c: v for c in campos})) for v in valores]
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


if __name__ == "__main__":
    fig_cenario_base()
    fig_extremos()
    fig_mapa_PK()
    fig_sensibilidade()
    fig_choque()