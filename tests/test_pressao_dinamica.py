"""Testes unitários para a dinâmica de Pressão com atrasos temporais (delays).

Valida rigorosamente:
(i) A validação da restrição 0 < a < c < b (lançando ValueError caso contrário).
(ii) O disparo correto dos 3 eventos nos ticks c, c+a e c+b após a criação de um erro.
(iii) A recuperação do piso mínimo pressaoMin após h turnos consecutivos abaixo do piso.
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
from model.dinamicas import DinamicaPressao
from model.model import BASE, simular


def test_validacao_restricao_a_c_b():
    """Valida que a < c < b é verificado e lança ValueError quando violado."""
    print("[1] Testando validação da restrição 0 < a < c < b...")

    # Caso válido: 0 < 2 < 5 < 8
    dp_valido = DinamicaPressao(
        pressao=0.5, pressaoMin=0.1, a=2, c=5, b=8, p=0.1, q=0.05
    )
    assert dp_valido.a == 2 and dp_valido.c == 5 and dp_valido.b == 8

    # Casos inválidos que devem disparar ValueError:
    casos_invalidos = [
        (0, 5, 8, "a <= 0"),
        (5, 5, 8, "a == c"),
        (6, 5, 8, "a > c"),
        (2, 8, 8, "c == b"),
        (2, 9, 8, "c > b"),
        (-1, 5, 8, "a < 0"),
    ]

    for a, c, b, motivo in casos_invalidos:
        try:
            DinamicaPressao(pressao=0.5, pressaoMin=0.1, a=a, c=c, b=b, p=0.1, q=0.05)
            assert False, f"Deveria ter lançado ValueError para {motivo} (a={a}, c={c}, b={b})"
        except ValueError as e:
            assert "0 < a < c < b" in str(e)

    # Validação também através da classe Params
    try:
        Params(a=10, c=5, b=20)
        assert False, "Params deveria ter lançado ValueError quando a >= c"
    except ValueError as e:
        assert "0 < a < c < b" in str(e)

    print("✓ Validação 0 < a < c < b passou em todos os casos de borda!")


def test_disparo_tres_eventos_c_ca_cb():
    """Valida o disparo exato dos 3 eventos nos ticks c, c+a e c+b."""
    print("\n[2] Testando disparo dos 3 eventos nos ticks c, c+a e c+b...")

    p = 0.2    # magnitude aumento
    q = 0.1    # magnitude redução preventiva
    a = 2      # duracao do pico
    c = 5      # atraso adm
    b = 8      # delay da redução
    p0 = 1.0   # pressão inicial

    dp = DinamicaPressao(
        pressao=p0,
        pressaoMin=0.0,
        z=0.0,
        p=p,
        q=q,
        a=a,
        b=b,
        c=c,
        h=10,
        pressao_dinamica=True,
    )

    # Simula nascimento de 1 erro no tick 0
    dp.agendar_resposta_erro(1)

    # Verifica que a fila possui exatamente as 3 tuplas ordenadas
    assert len(dp.fila_eventos_pressao) == 3
    assert dp.fila_eventos_pressao[0] == (+p, c)          # (+0.2, 5)
    assert dp.fila_eventos_pressao[1] == (-p, c + a)      # (-0.2, 7)
    assert dp.fila_eventos_pressao[2] == (-q, c + b)      # (-0.1, 13)

    historico_pressao = [p0]

    # Executa os ciclos de 1 a 15
    for tick in range(1, 16):
        pressao_atual = dp.atualizar_ciclo()
        historico_pressao.append(round(pressao_atual, 6))

    # Análise passo a passo dos disparos:
    # Ticks 1 a 4: antes de c -> pressão deve permanecer p0 = 1.0
    for tick in range(1, c):
        assert np.isclose(historico_pressao[tick], 1.0), f"Tick {tick}: esperado 1.0, obtido {historico_pressao[tick]}"

    # Tick c (5): disparo de (+p) -> 1.0 + 0.2 = 1.2
    assert np.isclose(historico_pressao[c], 1.2), f"Tick c ({c}): esperado 1.2 (+p), obtido {historico_pressao[c]}"

    # Tick c+1 (6): continua no pico -> 1.2
    assert np.isclose(historico_pressao[c + 1], 1.2), f"Tick 6: esperado 1.2, obtido {historico_pressao[6]}"

    # Tick c+a (7): fim do pico (-p) -> 1.2 - 0.2 = 1.0
    assert np.isclose(historico_pressao[c + a], 1.0), f"Tick c+a ({c+a}): esperado 1.0 (-p), obtido {historico_pressao[c+a]}"

    # Ticks c+a+1 (8) até c+b-1 (12): pressão em 1.0
    for tick in range(c + a + 1, c + b):
        assert np.isclose(historico_pressao[tick], 1.0), f"Tick {tick}: esperado 1.0, obtido {historico_pressao[tick]}"

    # Tick c+b (13): efeito preventivo consolidado (-q) -> 1.0 - 0.1 = 0.9
    assert np.isclose(historico_pressao[c + b], 0.9), f"Tick c+b ({c+b}): esperado 0.9 (-q), obtido {historico_pressao[c+b]}"

    # Tick 14 em diante: fila esgotada, pressão permanece em 0.9
    assert np.isclose(historico_pressao[14], 0.9)
    assert len(dp.fila_eventos_pressao) == 0

    print("✓ Disparos ocorreram com exatidão matemática nos ticks c (5), c+a (7) e c+b (13)!")


def test_recuperacao_piso_pressao_minima():
    """Valida que quando pressao < pressaoMin por h turnos consecutivos, ela retorna ao piso."""
    print("\n[3] Testando recuperação do piso pressaoMin após h turnos...")

    pressaoMin = 0.5
    h = 3
    dp = DinamicaPressao(
        pressao=0.6,
        pressaoMin=pressaoMin,
        z=-0.1,  # Reduz 0.1 a cada ciclo
        p=0.05,
        q=0.02,
        a=2,
        c=5,
        b=8,
        h=h,
        pressao_dinamica=True,
    )

    # Ciclo 1: 0.6 - 0.1 = 0.5 (igual a pressaoMin, não é menor) -> turnos = 0
    p1 = dp.atualizar_ciclo()
    assert np.isclose(p1, 0.5)
    assert dp.turnos_abaixo_minimo == 0

    # Ciclo 2: 0.5 - 0.1 = 0.4 (< 0.5) -> turnos = 1
    p2 = dp.atualizar_ciclo()
    assert np.isclose(p2, 0.4)
    assert dp.turnos_abaixo_minimo == 1

    # Ciclo 3: 0.4 - 0.1 = 0.3 (< 0.5) -> turnos = 2
    p3 = dp.atualizar_ciclo()
    assert np.isclose(p3, 0.3)
    assert dp.turnos_abaixo_minimo == 2

    # Ciclo 4: 0.3 - 0.1 = 0.2 (< 0.5) -> turnos atingiria 3 (>= h=3) -> força retorno a pressaoMin (0.5)!
    p4 = dp.atualizar_ciclo()
    assert np.isclose(p4, pressaoMin), f"Esperado retorno para pressaoMin ({pressaoMin}), obtido {p4}"
    assert dp.turnos_abaixo_minimo == 0

    # Teste de reset se a pressão subir acima do piso antes de h turnos
    dp.pressao = 0.4  # abaixo do piso
    dp.turnos_abaixo_minimo = 2
    dp.z = +0.2       # agora sobe
    p5 = dp.atualizar_ciclo()  # 0.4 + 0.2 = 0.6 >= 0.5
    assert p5 >= pressaoMin
    assert dp.turnos_abaixo_minimo == 0, "Deveria ter zerado turnos_abaixo_minimo quando pressao >= pressaoMin"

    print("✓ Recuperação do piso mínimo e reset do contador testados com sucesso!")


def test_integracao_simular_pressao_dinamica():
    """Valida a integração completa da dinâmica de pressão no loop ABM."""
    print("\n[4] Testando integração da pressão dinâmica na simulação ABM...")

    from dataclasses import replace
    par = replace(
        BASE,
        T=40,
        pressao_dinamica=True,
        pressaoMin=0.2,
        p=0.08,
        q=0.03,
        a=2,
        c=4,
        b=7,
        z=0.0,
    )

    res = simular(par, salvar=False)
    serie_pressao = res["pressao"]

    assert len(serie_pressao) == 40
    # Verifica que todos os valores são numéricos e não nulos
    assert not np.isnan(serie_pressao).any()
    # Verifica que os parâmetros estão presentes no dicionário de metadados
    params = res["parametros_iniciais"]
    for campo in ["pressao_dinamica", "pressaoMin", "a", "b", "c", "p", "q", "z", "h"]:
        assert campo in params, f"Campo {campo} ausente nos parametros_iniciais"
        assert params[campo] is not None

    print(f"✓ Simulação com pressão dinâmica executada! Pressão inicial/final: {serie_pressao[0]:.4f} / {serie_pressao[-1]:.4f}")


def main():
    print("=" * 60)
    print(" SUITE DE TESTES: DINÂMICA DE PRESSÃO COM DELAYS")
    print("=" * 60)
    test_validacao_restricao_a_c_b()
    test_disparo_tres_eventos_c_ca_cb()
    test_recuperacao_piso_pressao_minima()
    test_integracao_simular_pressao_dinamica()
    print("\n" + "=" * 60)
    print(" TODOS OS TESTES DE PRESSÃO PASSARAM COM SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    main()
