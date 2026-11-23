import os
from dataclasses import asdict, replace
from datetime import datetime
from typing import Optional, Union
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from configs.params import Params
from configs.paths import *
from model.dinamicas import DinamicaMoral, DinamicaPressao, inicializar_moral
from model.persistencia import salvar_simulacao, carregar_simulacao, validar_dados_simulacao




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


def simular(
    par: Params,
    P_t=None,
    salvar: bool = False,
    diretorio_persistencia: Optional[Union[str, Path]] = None,
    salvar_csv: bool = False,
):
    """Roda uma simulação do modelo do artigo. P_t(t) opcional faz a pressão variar no tempo.

    Os N_T primeiros agentes são trabalhadores e os K últimos são corretores.
    Coleta séries temporais completas e metadados requeridos:
    - Série temporal: moral_media, erros_ativos, pressao (e opcionais: desordem, taxa_erro, etc.)
    - Metadados: seed, parametros_iniciais, total_erros_criados, total_erros_eliminados.

    Retorna dict compatível com a interface original e enriquecido com os novos dados.
    Se salvar=True, persiste os resultados em JSON (e opcionalmente CSV) em persistencia/.
    """
    rng = np.random.default_rng(par.seed)
    L, NT, K = par.L, par.N_T, par.K
    N = NT + K
    eh_corretor = np.arange(N) >= NT

    waste = (rng.random((L, L)) < par.init).astype(float)      # 1 = há resíduo
    celulas = rng.choice(L * L, N, replace=False)              # posições iniciais sem sobreposição
    pos = np.column_stack((celulas // L, celulas % L))
    ocupada = np.zeros((L, L), bool)
    ocupada[pos[:, 0], pos[:, 1]] = True

    # moral individual e dinâmica
    if par.moral_dinamica:
        M = inicializar_moral(N, par.moral_inicial, par.M_sd, rng)
    else:
        M = np.clip(rng.normal(par.M_bar, par.M_sd, N), 0, 1)

    # Controladores das dinâmicas temporais com delays
    din_pressao = DinamicaPressao(
        pressao=float(par.P),
        pressaoMin=float(par.pressaoMin),
        z=float(par.z),
        p=float(par.p),
        q=float(par.q),
        a=int(par.a),
        b=int(par.b),
        c=int(par.c),
        h=int(par.h),
        pressao_dinamica=par.pressao_dinamica,
    )

    din_moral = DinamicaMoral(
        moral_inicial=float(par.moral_inicial),
        depreciacao=float(par.depreciacao),
        x=float(par.x),
        y=int(par.y),
        z_moral=float(par.z_moral),
        moral_dinamica=par.moral_dinamica,
        moral_media=float(np.mean(M)),
    )

    p_corr = np.where(eh_corretor, sig(par.cA + par.gA * M), sig(par.cT + par.gT * M))

    desordem, erro, prejuizo = [], [], []
    moral_media_serie, erros_ativos_serie, pressao_serie = [], [], []
    erros_criados_serie, erros_eliminados_serie = [], []

    total_erros_criados = 0
    total_erros_eliminados = 0

    for t in range(par.T):
        # Determina a pressão atuante neste passo
        if par.pressao_dinamica:
            P = din_pressao.pressao
        else:
            P = par.P if P_t is None else P_t(t)

        xs, ys = pos[:, 0], pos[:, 1]

        # Recalcula p_corr se a moral for dinâmica ao longo do tempo
        if par.moral_dinamica:
            p_corr = np.where(eh_corretor, sig(par.cA + par.gA * M), sig(par.cT + par.gT * M))

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

        # Contabilização de erros gerados e eliminados neste tick
        criados_passo = int(np.sum(err))
        eliminados_passo = int(np.sum((w0 == 1.0) & (~err) & corrige))
        total_erros_criados += criados_passo
        total_erros_eliminados += eliminados_passo

        # Gatilhos de eventos com atraso (delays):
        # 1. Quando novo erro nasce: agenda 3 eventos de resposta administrativa na fila de pressão
        if par.pressao_dinamica and criados_passo > 0:
            din_pressao.agendar_resposta_erro(criados_passo)

        # 2. Quando erro é eliminado: agenda novos CDs na fila de moral
        if par.moral_dinamica and eliminados_passo > 0:
            din_moral.agendar_cd(eliminados_passo)

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

        # Métricas do passo t (estado sob o qual os agentes atuaram neste tick)
        frac_desordem = float(waste.mean())
        taxa_erro = float(err[:NT].mean())
        num_erros_ativos = int(waste.sum())
        moral_atual = float(np.mean(M))
        pressao_atual = float(P)

        # Atualizações dinâmicas ao final do passo do loop (transição para o próximo tick)
        if par.pressao_dinamica:
            din_pressao.atualizar_ciclo()

        if par.moral_dinamica:
            din_moral.atualizar_ciclo(M)



        desordem.append(frac_desordem)
        erro.append(taxa_erro)
        prejuizo.append(num_erros_ativos)

        moral_media_serie.append(moral_atual)
        erros_ativos_serie.append(num_erros_ativos)
        pressao_serie.append(pressao_atual)
        erros_criados_serie.append(criados_passo)
        erros_eliminados_serie.append(eliminados_passo)

    # Construção da série temporal estruturada
    serie_temporal = [
        {
            "passo": t,
            "moral_media": moral_media_serie[t],
            "erros_ativos": erros_ativos_serie[t],
            "pressao": pressao_serie[t],
            "desordem": desordem[t],
            "taxa_erro_trabalhadores": erro[t],
            "erros_criados_passo": erros_criados_serie[t],
            "erros_eliminados_passo": erros_eliminados_serie[t],
        }
        for t in range(par.T)
    ]

    parametros_iniciais = par.to_dict() if hasattr(par, "to_dict") else asdict(par)
    dados_simulacao = {
        "seed": int(par.seed),
        "timestamp": datetime.now().isoformat(),
        "parametros_iniciais": parametros_iniciais,
        "total_erros_criados": int(total_erros_criados),
        "total_erros_eliminados": int(total_erros_eliminados),
        "resumo": {
            "passos_totais": int(par.T),
            "erros_ativos_final": int(erros_ativos_serie[-1]) if erros_ativos_serie else 0,
            "desordem_final": float(desordem[-1]) if desordem else 0.0,
            "desordem_media_janela_final": float(np.mean(desordem[-JANELA_FINAL:])) if desordem else 0.0,
            "moral_media_final": float(moral_media_serie[-1]) if moral_media_serie else 0.0,
        },
        "serie_temporal": serie_temporal,
    }

    caminho_arquivo = None
    if salvar:
        dir_saida = diretorio_persistencia if diretorio_persistencia is not None else PERSISTENCIA_DIR
        caminho_arquivo = salvar_simulacao(
            dados_simulacao,
            diretorio=dir_saida,
            salvar_csv=salvar_csv,
        )

    return dict(
        desordem=np.array(desordem),
        erro=np.array(erro),
        prejuizo=np.array(prejuizo),
        waste=waste,
        pos=pos[NT:].copy(),
        M=M,
        # Séries temporais adicionais
        moral_media=np.array(moral_media_serie),
        erros_ativos=np.array(erros_ativos_serie),
        pressao=np.array(pressao_serie),
        erros_criados=np.array(erros_criados_serie),
        erros_eliminados=np.array(erros_eliminados_serie),
        # Totais e metadados
        total_erros_criados=int(total_erros_criados),
        total_erros_eliminados=int(total_erros_eliminados),
        seed=int(par.seed),
        parametros_iniciais=parametros_iniciais,
        serie_temporal=serie_temporal,
        dados_completos=dados_simulacao,
        caminho_arquivo=caminho_arquivo,
        controlador_pressao=din_pressao,
        controlador_moral=din_moral,
    )



def executar_simulacao(
    par: Params = BASE,
    seed: Optional[int] = None,
    salvar: bool = True,
    salvar_csv: bool = False,
    diretorio: Optional[Union[str, Path]] = None,
    P_t=None,
):
    """Executa uma simulação isolada e opcionalmente persiste os dados gerados."""
    if seed is not None:
        par = replace(par, seed=seed)
    return simular(
        par,
        P_t=P_t,
        salvar=salvar,
        diretorio_persistencia=diretorio,
        salvar_csv=salvar_csv,
    )


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



# ---------------------------------------------------------------- Figura 6: limiar do contágio
def fig_limiar():
    """Desordem final em função do peso do contágio, partindo da grade limpa e da grade suja.
    Se as duas curvas se separassem, haveria dois equilíbrios (histerese)."""
    valores = [0.0, 1.0, 1.4, 2.0, 2.8, 3.5, 4.0, 4.5, 5.0, 6.0, 8.0]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for init, rot, mk in ((0.0, "início limpo (init = 0)", "o-"), (0.7, "início sujo (init = 0,7)", "s--")):
        y = [final(replace(BASE, bDT=v, bDA=v, init=init), 4) for v in valores]
        ax.plot(valores, y, mk, label=rot)
        print(f"Limiar init={init}: " + ", ".join(f"{v}->{d:.3f}" for v, d in zip(valores, y)))
    ax.axvline(BASE.bDT, color="grey", ls=":", lw=1)
    ax.set(xlabel="peso do contágio $\\beta_D$", ylabel="desordem final",
           title="Limiar do contágio da desordem")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, "fig6_limiar_contagio.png"), dpi=200)


if __name__ == "__main__":
    fig_cenario_base()
    fig_extremos()
    fig_mapa_PK()
    fig_sensibilidade()
    fig_choque()