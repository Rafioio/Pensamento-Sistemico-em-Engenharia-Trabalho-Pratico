import os
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.paths import OUTPUT_DIR
from model.model import fig_cenario_base, fig_choque, fig_extremos, fig_mapa_PK, fig_sensibilidade, fig_limiar

if __name__ == "__main__":
    for f in (fig_cenario_base, fig_extremos, fig_mapa_PK, fig_sensibilidade, fig_choque, fig_limiar):
        print("->", f.__name__)
        f()
    print("Figuras salvas em", os.path.abspath(OUTPUT_DIR))

