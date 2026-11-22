import os
from configs.paths import OUTPUT_DIR
from model.model import fig_cenario_base, fig_choque, fig_extremos, fig_mapa_PK, fig_sensibilidade

if __name__ == "__main__":
    for f in (fig_cenario_base, fig_extremos, fig_mapa_PK, fig_sensibilidade, fig_choque):
        print("->", f.__name__)
        f()
    print("Figuras salvas em", os.path.abspath(OUTPUT_DIR))
