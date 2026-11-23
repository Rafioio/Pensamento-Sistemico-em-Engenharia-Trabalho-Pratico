from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "outputs"
TEST_DIR = ROOT_DIR / "tests"
CONFIG_DIR = ROOT_DIR / "configs"
MODEL_DIR = ROOT_DIR / "model"
UTILS_DIR = MODEL_DIR / "utils"
PERSISTENCIA_DIR = ROOT_DIR / "persistencia"
PERSISTENCE_DIR = PERSISTENCIA_DIR

# Garante que os diretórios necessários existam
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PERSISTENCIA_DIR.mkdir(parents=True, exist_ok=True)
