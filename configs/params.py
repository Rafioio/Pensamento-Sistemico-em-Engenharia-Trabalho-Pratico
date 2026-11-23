from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class Params:
    """Parâmetros do modelo (valores base da Tabela de parâmetros do artigo e dinâmicas com delay)."""
    # ambiente e agentes
    L: int = 30              # lado da grade (toroidal)
    N_T: int = 120           # nº de trabalhadores
    K: int = 8               # nº de corretores
    r_s: int = 3             # raio de supervisão (distância de Chebyshev)
    T: int = 600             # passos de tempo
    seed: int = 0
    init: float = 0.0        # fração inicial de células com resíduo

    # pressão e moral (exógenas e constantes em cada execução quando dinâmica está desativada)
    P: float = 0.5
    M_bar: float = 0.5       # moral média basal
    M_sd: float = 0.25       # dispersão da moral entre agentes

    # probabilidade de erro: sigma(b + bP*P + bD*D - bS*S - bM*M)
    bT: float = -2.0         # intercepto, trabalhadores
    bA: float = -3.0         # intercepto, corretores
    bPT: float = 1.2
    bPA: float = 0.6
    bDT: float = 1.4
    bDA: float = 1.4
    bST: float = 1.0         # supervisão (só trabalhadores)
    bMT: float = 2.0
    bMA: float = 2.0

    # probabilidade de correção: sigma(c + gamma*M)
    cT: float = -1.5
    cA: float = 1.0
    gT: float = 3.0
    gA: float = 2.0

    # movimento dos corretores: "aleatoria", "reativa" ou "cobertura"
    politica: str = "aleatoria"
    eps: float = 0.1         # prob. de ignorar a política e andar ao acaso

    # Dinâmica de Pressão com atrasos temporais (delays)
    pressao_dinamica: bool = False
    pressaoMin: float = 0.1  # piso basal de pressão operacional
    z: float = 0.0           # influência externa contínua por ciclo
    p: float = 0.05          # magnitude do aumento temporário (aumento_pressao > 0)
    q: float = 0.02          # magnitude da redução consolidada (reducao_pressao > 0)
    a: int = 5               # duração em ticks do pico de pressão (duracao_aumento)
    b: int = 20              # atraso em ticks para a redução ocorrer (delay_reducao)
    c: int = 10              # atraso em ticks até início da medida (atraso_adm)
    h: int = 5               # turnos consecutivos abaixo de pressaoMin para forçar retorno

    # Dinâmica de Moral com atrasos temporais (delays)
    moral_dinamica: bool = False
    moral_inicial: float = 0.5   # valor alvo da média inicial
    depreciacao: float = 0.0     # queda natural constante por ciclo (>= 0)
    x: float = 0.01              # ganho na moral média por CD (impacto_cd > 0)
    y: int = 10                  # atraso em ticks para efeito do CD (tempo_moral > 0)
    z_moral: float = 0.0         # influência externa contínua sobre a moral

    def __post_init__(self):
        # Validação obrigatória da dinâmica de pressão: 0 < a < c < b
        if not (0 < self.a < self.c < self.b):
            raise ValueError(
                f"Restrição obrigatória violada: deve ser 0 < a < c < b (obtido a={self.a}, c={self.c}, b={self.b})"
            )
        if self.p <= 0:
            raise ValueError(f"p (aumento_pressao) deve ser > 0, obtido {self.p}")
        if self.q <= 0:
            raise ValueError(f"q (reducao_pressao) deve ser > 0, obtido {self.q}")

        # Validação dos parâmetros de moral
        if self.depreciacao < 0:
            raise ValueError(f"depreciacao deve ser >= 0, obtido {self.depreciacao}")
        if self.x <= 0:
            raise ValueError(f"x (impacto_cd) deve ser > 0, obtido {self.x}")
        if self.y <= 0:
            raise ValueError(f"y (tempo_moral) deve ser > 0, obtido {self.y}")

        # Sincroniza moral_inicial e M_bar se um deles foi alterado
        if self.moral_inicial != 0.5 and self.M_bar == 0.5:
            self.M_bar = self.moral_inicial
        elif self.M_bar != 0.5 and self.moral_inicial == 0.5:
            self.moral_inicial = self.M_bar

    def to_dict(self) -> Dict[str, Any]:
        """Converte os parâmetros para dicionário serializável."""
        return asdict(self)

