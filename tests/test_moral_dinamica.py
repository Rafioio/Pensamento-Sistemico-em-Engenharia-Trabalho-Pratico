"""Testes unitários para a dinâmica de Moral (individual e média) com atrasos temporais (delays).

Valida rigorosamente:
(i) Se a média inicial gerada aleatoriamente é exatamente igual a moral_inicial.
(ii) Se a eliminação de um erro só aumenta a moral exatamente y ticks depois.
(iii) Se o delta líquido do turno é repassado corretamente para a moral individual de cada agente.
(iv) Integração com o loop ABM simular() e persistência dos dados.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from configs.params import Params
from model.dinamicas import DinamicaMoral, inicializar_moral
from model.model import BASE, simular


def test_media_inicial_exata():
    """Valida que a inicialização aleatória dos agentes tem média exatamente igual a moral_inicial."""
    print("[1] Testando se a média inicial gerada é exatamente igual a moral_inicial...")

    N = 128
    rng = np.random.default_rng(42)

    for alvo in [0.2, 0.35, 0.5, 0.65, 0.8]:
        M = inicializar_moral(N, moral_inicial=alvo, sd=0.25, rng=rng)
        assert len(M) == N
        assert (M >= 0.0).all() and (M <= 1.0).all(), "Valores de moral devem estar em [0.0, 1.0]"
        # Precisão de ponto flutuante estrita
        assert np.isclose(np.mean(M), alvo, atol=1e-12), (
            f"Esperado média {alvo}, obtido {np.mean(M)}"
        )

    # Teste com diferentes seeds
    for seed in [1, 10, 99, 1234]:
        rng_s = np.random.default_rng(seed)
        M_s = inicializar_moral(200, moral_inicial=0.5, sd=0.3, rng=rng_s)
        assert np.isclose(np.mean(M_s), 0.5, atol=1e-12)

    print("✓ Média inicial gerada aleatoriamente é exatamente igual a moral_inicial para todas as sementes e alvos!")


def test_aumento_moral_exatamente_y_ticks_depois():
    """Valida que a eliminação de um erro só aumenta a moral exatamente y ticks depois."""
    print("\n[2] Testando aumento de moral exatamente y ticks após eliminação de erro...")

    x = 0.05   # impacto do CD
    y = 4      # atraso em ticks (tempo_moral)
    m0 = 0.5   # moral inicial

    dm = DinamicaMoral(
        moral_inicial=m0,
        depreciacao=0.0,
        x=x,
        y=y,
        z_moral=0.0,
        moral_dinamica=True,
        moral_media=m0,
    )

    M = np.full(20, m0, dtype=float)

    # No tick 0, 1 erro é eliminado -> agenda 1 CD
    dm.agendar_cd(1)
    assert len(dm.fila_cds) == 1
    assert dm.fila_cds[0]["tempo_restante"] == y
    assert dm.fila_cds[0]["impacto"] == x

    historico_media = [m0]

    # Executa ciclos 1 a 6
    for tick in range(1, 7):
        nova_media, _ = dm.atualizar_ciclo(M)
        historico_media.append(round(nova_media, 6))

    # Ticks 1 a 3 (antes de y=4): moral média deve permanecer m0 = 0.5
    for tick in range(1, y):
        assert np.isclose(historico_media[tick], 0.5), (
            f"Tick {tick}: moral média mudou prematuramente para {historico_media[tick]}"
        )

    # Tick y (4): CD matura! Aumento de +x = +0.05 -> moral vai a 0.55
    assert np.isclose(historico_media[y], 0.55), (
        f"Tick y ({y}): esperado aumento de moral para 0.55 (+x), obtido {historico_media[y]}"
    )
    assert len(dm.fila_cds) == 0, "Fila de CDs deveria estar vazia após maturação"

    # Ticks 5 e 6: sem novos CDs, moral permanece 0.55
    assert np.isclose(historico_media[5], 0.55)
    assert np.isclose(historico_media[6], 0.55)

    print(f"✓ Erro eliminado aumentou a moral exatamente no tick y={y}!")


def test_propagacao_delta_liquido_para_agentes():
    """Valida se o delta líquido do turno é repassado corretamente para cada agente individual."""
    print("\n[3] Testando propagação do delta líquido para moral individual dos agentes...")

    dm = DinamicaMoral(
        moral_inicial=0.5,
        depreciacao=0.02,
        x=0.05,
        y=10,
        z_moral=0.01,
        moral_dinamica=True,
    )

    # Agentes com morais heterogêneas
    M_inicial = np.array([0.20, 0.40, 0.60, 0.80], dtype=float)
    M = M_inicial.copy()

    media_antes = float(np.mean(M))
    assert np.isclose(media_antes, 0.5)

    # Turno 1 sem CDs maturando: delta esperado = -depreciacao + z_moral = -0.02 + 0.01 = -0.01
    nova_media, delta = dm.atualizar_ciclo(M)
    assert np.isclose(delta, -0.01)
    assert np.isclose(nova_media, 0.49)

    # Verifica se cada agente teve exatamente delta somado à sua moral individual
    esperado_M1 = M_inicial - 0.01
    assert np.allclose(M, esperado_M1), f"Moral individual incorreta: {M} vs esperado {esperado_M1}"
    assert np.isclose(np.mean(M), nova_media), "A média de M deve ser idêntica a nova_moral_media"

    # Turno 2 com maturação de CD (+x = +0.05):
    # delta esperado = +0.05 - 0.02 + 0.01 = +0.04
    dm.fila_cds.append({"impacto": 0.05, "tempo_restante": 1})
    M_antes_t2 = M.copy()
    nova_media2, delta2 = dm.atualizar_ciclo(M)

    assert np.isclose(delta2, +0.04)
    assert np.isclose(nova_media2, 0.53)
    assert np.allclose(M, M_antes_t2 + 0.04)
    assert np.isclose(np.mean(M), nova_media2)

    print("✓ Delta líquido do turno foi repassado perfeitamente para todos os agentes individuais!")


def test_integracao_simular_moral_dinamica():
    """Valida a integração da dinâmica de moral no loop de simulação ABM."""
    print("\n[4] Testando integração da moral dinâmica na simulação ABM...")

    from dataclasses import replace
    par = replace(
        BASE,
        T=40,
        moral_dinamica=True,
        moral_inicial=0.6,
        depreciacao=0.005,
        x=0.02,
        y=5,
        z_moral=0.0,
    )

    res = simular(par, salvar=False)
    serie_moral = res["moral_media"]

    assert len(serie_moral) == 40
    # Tick 0 deve iniciar com a moral_inicial
    assert np.isclose(serie_moral[0], 0.6, atol=1e-12)

    # Verifica parâmetros salvos nos metadados
    params = res["parametros_iniciais"]
    for campo in ["moral_dinamica", "moral_inicial", "depreciacao", "x", "y", "z_moral"]:
        assert campo in params, f"Campo {campo} ausente em parametros_iniciais"
        assert params[campo] is not None

    print(f"✓ Simulação com moral dinâmica executada! Moral inicial/final: {serie_moral[0]:.4f} / {serie_moral[-1]:.4f}")


def main():
    print("=" * 60)
    print(" SUITE DE TESTES: DINÂMICA DE MORAL COM DELAYS")
    print("=" * 60)
    test_media_inicial_exata()
    test_aumento_moral_exatamente_y_ticks_depois()
    test_propagacao_delta_liquido_para_agentes()
    test_integracao_simular_moral_dinamica()
    print("\n" + "=" * 60)
    print(" TODOS OS TESTES DE MORAL PASSARAM COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
