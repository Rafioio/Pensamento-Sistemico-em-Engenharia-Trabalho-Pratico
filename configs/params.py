from dataclasses import dataclass

@dataclass
class Params:
    L: int = 30            # lado da grade (toroidal)
    K: int = 5             # nº de corretores
    r_s: int = 3           # raio de supervisão (distância de Chebyshev)
    P: float = 0.65        # pressão operacional, em [0, 1]
    b0: float = -3.0       # propensão basal ao erro (complexidade/esquecimento)
    bP: float = 3.0        # peso da pressão
    bD: float = 4.0        # peso do contágio (desordem visível)
    bS: float = 2.0        # peso da supervisão
    bM: float = 3.0        # peso da moral
    eta_S: float = 0.02    # ganho de moral por estar supervisionado
    eta_D: float = 0.02    # perda de moral por ver desordem
    eta_R: float = 0.02    # retorno da moral ao valor pessoal (valores de cada um)
    rho0: float = 0.30     # limpeza rotineira (prob. por passo, qualquer célula)
    rho: float = 0.5       # limpeza pelos corretores (prob. por passo, no raio r_s)
    m0: float = 0.5        # moral inicial média
    m_sd: float = 0.2      # dispersão da moral inicial (heterogeneidade)
    dirigido: bool = True  # corretores vão à desordem (True) ou andam ao acaso (False)
    T: int = 300           # nº de passos
    seed: int = 0
