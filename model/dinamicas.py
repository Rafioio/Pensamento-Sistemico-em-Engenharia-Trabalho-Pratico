"""Módulo de dinâmicas temporais com atrasos (delays) para Pressão e Moral.

Implementa a especificação lógica e matemática de:
1. Dinâmica de Pressão com atrasos administrativos e preventivos (pressão.txt).
2. Dinâmica de Moral individual e coletiva com maturação de CDs (moral.txt).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import numpy as np


def inicializar_moral(
    N: int,
    moral_inicial: float,
    sd: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Inicializa a moral de N agentes garantindo que a média seja exatamente moral_inicial.

    Aplica um ajuste de centralização nos desvios aleatórios em torno de moral_inicial.
    Se houver valores fora do intervalo [0.0, 1.0], ajusta proporcionalmente a escala
    dos desvios mantendo a média matematicamente exata no tick 0.
    """
    if N <= 0:
        return np.array([], dtype=float)
    if sd <= 0.0:
        return np.full(N, float(moral_inicial), dtype=float)

    # 1. Gera desvios gaussianos em torno de zero
    desvios = rng.normal(0.0, sd, N)
    desvios -= np.mean(desvios)  # Média exata de desvios = 0.0

    # 2. Ajusta escala se estourar limites [0.0, 1.0] para preservar a média
    max_pos = np.max(desvios)
    min_neg = np.min(desvios)
    escala = 1.0

    if moral_inicial + max_pos > 1.0 and max_pos > 0:
        escala = min(escala, (1.0 - moral_inicial) / max_pos)
    if moral_inicial + min_neg < 0.0 and min_neg < 0:
        escala = min(escala, moral_inicial / abs(min_neg))

    if escala < 1.0:
        desvios = desvios * escala * 0.999999
        desvios -= np.mean(desvios)

    M = moral_inicial + desvios
    return np.clip(M, 0.0, 1.0)


@dataclass
class DinamicaPressao:
    """Controlador da dinâmica de pressão com atrasos temporais (delays).

    Regras:
    - a < c < b (0 < duracao_aumento < atraso_adm < delay_reducao)
    - Cada erro criado gera 3 eventos: (+p, c), (-p, c+a), (-q, c+b)
    - A cada ciclo: delta_ciclo = z + eventos maturados; pressao += delta_ciclo
    - Se pressao < pressaoMin por h ciclos consecutivos, força retorno ao piso.
    """

    pressao: float
    pressaoMin: float
    z: float = 0.0
    p: float = 0.05
    q: float = 0.02
    a: int = 5
    b: int = 20
    c: int = 10
    h: int = 5
    pressao_dinamica: bool = True
    fila_eventos_pressao: List[Tuple[float, int]] = field(default_factory=list)
    turnos_abaixo_minimo: int = 0

    def __post_init__(self) -> None:
        if self.pressao_dinamica:
            if not (0 < self.a < self.c < self.b):
                raise ValueError(
                    f"Restrição obrigatória violada: deve ser 0 < a < c < b "
                    f"(obtido a={self.a}, c={self.c}, b={self.b})"
                )
            if self.p <= 0:
                raise ValueError(f"p (aumento_pressao) deve ser > 0, obtido {self.p}")
            if self.q <= 0:
                raise ValueError(f"q (reducao_pressao) deve ser > 0, obtido {self.q}")

    def agendar_resposta_erro(self, quantidade: int = 1) -> None:
        """Gatilho de evento: quando um novo erro nasce.

        Para cada erro criado no ciclo atual, agenda 3 eventos futuros:
        1. (+p, c)     -> início da medida administrativa (aumenta a pressão após c ticks)
        2. (-p, c + a) -> fim do pico da medida administrativa (reverte aumento p após a ticks)
        3. (-q, c + b) -> efeito preventivo consolidado (reduz a pressão em q após b ticks)
        """
        if not self.pressao_dinamica or quantidade <= 0:
            return

        for _ in range(quantidade):
            self.fila_eventos_pressao.append((+float(self.p), int(self.c)))
            self.fila_eventos_pressao.append((-float(self.p), int(self.c + self.a)))
            self.fila_eventos_pressao.append((-float(self.q), int(self.c + self.b)))

        # Mantém a fila ordenada pelo tempo restante (ticks)
        self.fila_eventos_pressao.sort(key=lambda item: item[1])

    def atualizar_ciclo(self) -> float:
        """Executa a atualização do ciclo (tick) exatamente na ordem especificada:

        1. Inicializa o delta do ciclo atual com a influência externa: delta_ciclo = z.
        2. Percorre todas as tuplas (delta, ticks) em fila_eventos_pressao:
           - Decrementa ticks em 1.
           - Para toda tupla em que ticks == 0: soma delta ao delta_ciclo e remove da fila.
        3. Atualiza o estoque de pressão: pressao += delta_ciclo.
        4. Verificação de piso mínimo (pressaoMin):
           - Se pressao < pressaoMin: incrementa turnos_abaixo_minimo += 1.
             Se turnos_abaixo_minimo >= h: pressao = pressaoMin e turnos_abaixo_minimo = 0.
           - Caso contrário: turnos_abaixo_minimo = 0.

        Retorna o novo valor de pressão.
        """
        if not self.pressao_dinamica:
            return self.pressao

        # 1. Influência externa
        delta_ciclo = float(self.z)

        # 2. Percorrer fila de eventos e decrementar
        nova_fila: List[Tuple[float, int]] = []
        for delta, ticks in self.fila_eventos_pressao:
            ticks_restantes = ticks - 1
            if ticks_restantes == 0:
                delta_ciclo += delta
            else:
                nova_fila.append((delta, ticks_restantes))
        self.fila_eventos_pressao = nova_fila

        # 3. Atualiza estoque de pressão
        self.pressao += delta_ciclo

        # 4. Verificação de piso mínimo
        if self.pressao < self.pressaoMin:
            self.turnos_abaixo_minimo += 1
            if self.turnos_abaixo_minimo >= self.h:
                self.pressao = float(self.pressaoMin)
                self.turnos_abaixo_minimo = 0
        else:
            self.turnos_abaixo_minimo = 0

        return self.pressao


@dataclass
class DinamicaMoral:
    """Controlador da dinâmica de moral com atrasos temporais (delays).

    Regras:
    - Cada erro eliminado gera 1 CD com {"impacto": x, "tempo_restante": y}.
    - A cada ciclo:
      1. nova_moral_media = moral_media
      2. Decrementa CDs; se tempo_restante == 0, soma impacto à nova_moral_media e remove.
      3. nova_moral_media -= depreciacao
      4. nova_moral_media += z_moral
      5. delta_moral = nova_moral_media - moral_media; propaga delta para todos os agentes.
    """

    moral_inicial: float = 0.5
    depreciacao: float = 0.0
    x: float = 0.01
    y: int = 10
    z_moral: float = 0.0
    moral_dinamica: bool = True
    moral_media: float = 0.5
    fila_cds: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.moral_dinamica:
            if self.depreciacao < 0:
                raise ValueError(f"depreciacao deve ser >= 0, obtido {self.depreciacao}")
            if self.x <= 0:
                raise ValueError(f"x (impacto_cd) deve ser > 0, obtido {self.x}")
            if self.y <= 0:
                raise ValueError(f"y (tempo_moral) deve ser > 0, obtido {self.y}")

    def agendar_cd(self, quantidade: int = 1) -> None:
        """Gatilho de evento: quando um erro é eliminado/corrigido.

        Instancia novos CDs na fila com impacto=x e tempo_restante=y.
        """
        if not self.moral_dinamica or quantidade <= 0:
            return

        for _ in range(quantidade):
            self.fila_cds.append({
                "impacto": float(self.x),
                "tempo_restante": int(self.y),
            })

    def atualizar_ciclo(self, M: np.ndarray) -> Tuple[float, float]:
        """Executa a atualização do ciclo (tick) exatamente na ordem especificada:

        1. Calcule a moral_media atual da população e inicialize nova_moral_media = moral_media.
        2. Processamento da Fila de CDs:
           - Percorre todos os itens em fila_cds e decremente tempo_restante em 1.
           - Para todo CD em que tempo_restante == 0: soma impacto à nova_moral_media e remove da fila.
        3. Depreciação Natural: nova_moral_media -= depreciacao.
        4. Influência Externa: nova_moral_media += z_moral.
        5. Propagação para os Agentes Individuais:
           - delta_moral = nova_moral_media - moral_media.
           - Some delta_moral à moral individual de todos os agentes (M += delta_moral).
           - Atualize moral_media = nova_moral_media.

        Retorna tupla (nova_moral_media: float, delta_moral: float).
        """
        if not self.moral_dinamica:
            return float(np.mean(M)), 0.0

        # 1. Média atual
        moral_media = float(np.mean(M))
        nova_moral_media = moral_media

        # 2. Processamento da fila de CDs
        nova_fila: List[Dict[str, Any]] = []
        for cd in self.fila_cds:
            tempo = cd["tempo_restante"] - 1
            if tempo == 0:
                nova_moral_media += cd["impacto"]
            else:
                nova_fila.append({"impacto": cd["impacto"], "tempo_restante": tempo})
        self.fila_cds = nova_fila

        # 3. Depreciação Natural
        nova_moral_media -= self.depreciacao

        # 4. Influência Externa
        nova_moral_media += self.z_moral

        # 5. Propagação para os Agentes Individuais
        delta_moral = nova_moral_media - moral_media
        M += delta_moral
        self.moral_media = nova_moral_media

        return nova_moral_media, delta_moral
