from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class Params:
    """Parâmetros do modelo (valores base da Tabela de parâmetros do artigo)."""
    # ambiente e agentes
    L: int = 30              # lado da grade (toroidal)
    N_T: int = 120           # nº de trabalhadores
    K: int = 8               # nº de corretores
    r_s: int = 3             # raio de supervisão (distância de Chebyshev)
    T: int = 600             # passos de tempo
    seed: int = 0
    init: float = 0.0        # fração inicial de células com resíduo

    # pressão e moral (exógenas e constantes em cada execução)
    P: float = 0.5
    M_bar: float = 0.5       # moral média
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

    def to_dict(self) -> Dict[str, Any]:
        """Converte os parâmetros para dicionário serializável."""
        return asdict(self)
