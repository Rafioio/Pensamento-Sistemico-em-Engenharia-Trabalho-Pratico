"""Módulo de persistência e validação para dados das simulações (ABM).

Gerencia a serialização em JSON estruturado e CSV, verificação de integridade,
metadados de execução e carregamento para análise com pandas ou Python nativo.
"""

from __future__ import annotations
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from configs.paths import PERSISTENCIA_DIR


class NumpyJSONEncoder(json.JSONEncoder):
    """Codificador JSON customizado para tipos do NumPy e Path."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def converter_tipos_numpy(obj: Any) -> Any:
    """Converte recursivamente tipos NumPy para tipos primitivos de Python."""
    if isinstance(obj, dict):
        return {k: converter_tipos_numpy(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [converter_tipos_numpy(v) for v in obj]
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [converter_tipos_numpy(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


CAMPOS_METADADOS_OBRIGATORIOS = [
    "seed",
    "parametros_iniciais",
    "total_erros_criados",
    "total_erros_eliminados",
]

CAMPOS_SERIE_TEMPORAL_OBRIGATORIOS = [
    "moral_media",
    "erros_ativos",
    "pressao",
]


def validar_dados_simulacao(dados: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Valida se a estrutura de dados da simulação cumpre todos os requisitos obrigatórios.

    Verifica a presença e ausência de nulos em:
    - Metadados: seed, parametros_iniciais, total_erros_criados, total_erros_eliminados.
    - Série temporal: moral_media, erros_ativos, pressao (para cada passo).

    Retorna (valido: bool, erros: List[str]).
    """
    erros = []

    if not isinstance(dados, dict):
        return False, ["Os dados da simulação devem ser um dicionário."]

    # 1. Validação dos metadados obrigatórios
    for campo in CAMPOS_METADADOS_OBRIGATORIOS:
        if campo not in dados:
            erros.append(f"Campo obrigatório ausente nos metadados: '{campo}'.")
        elif dados[campo] is None:
            erros.append(f"Campo obrigatório com valor nulo (None): '{campo}'.")

    # Validação de parametros_iniciais
    parametros = dados.get("parametros_iniciais")
    if parametros is not None and not isinstance(parametros, dict):
        erros.append("O campo 'parametros_iniciais' deve ser um dicionário.")

    # 2. Validação da série temporal
    serie = dados.get("serie_temporal")
    if serie is None:
        erros.append("Campo obrigatório ausente: 'serie_temporal'.")
    elif not isinstance(serie, list):
        erros.append("O campo 'serie_temporal' deve ser uma lista de passos.")
    elif len(serie) == 0:
        erros.append("A 'serie_temporal' não pode estar vazia.")
    else:
        # Verificar cada passo da série temporal
        for i, passo in enumerate(serie):
            if not isinstance(passo, dict):
                erros.append(f"O passo {i} na série temporal não é um dicionário.")
                break
            for campo in CAMPOS_SERIE_TEMPORAL_OBRIGATORIOS:
                if campo not in passo:
                    erros.append(f"Passo {i}: campo obrigatório '{campo}' ausente.")
                elif passo[campo] is None:
                    erros.append(f"Passo {i}: campo obrigatório '{campo}' possui valor nulo (None).")

    return (len(erros) == 0), erros


def salvar_simulacao(
    dados: Dict[str, Any],
    diretorio: Optional[Union[str, Path]] = None,
    prefixo: str = "sim",
    timestamp: Optional[str] = None,
    salvar_csv: bool = False,
    validar: bool = True,
) -> Path:
    """Salva os dados de uma simulação no diretório de persistência.

    Salva em formato JSON estruturado com nome:
        `sim_<timestamp>_seed_<seed>.json`
    Opcionalmente também salva o par CSV para a série temporal.

    Retorna o Path do arquivo JSON gerado.
    """
    if diretorio is None:
        diretorio = PERSISTENCIA_DIR
    caminho_dir = Path(diretorio)
    caminho_dir.mkdir(parents=True, exist_ok=True)

    dados_limpos = converter_tipos_numpy(dados)

    if validar:
        valido, erros_validacao = validar_dados_simulacao(dados_limpos)
        if not valido:
            raise ValueError(f"Dados da simulação inválidos para persistência: {erros_validacao}")

    seed = dados_limpos.get("seed", 0)
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Nome padronizado: sim_<timestamp>_seed_<seed>.json
    nome_base = f"{prefixo}_{timestamp}_seed_{seed}"
    arquivo_json = caminho_dir / f"{nome_base}.json"

    # Salva JSON estruturado
    with open(arquivo_json, "w", encoding="utf-8") as f:
        json.dump(dados_limpos, f, indent=2, ensure_ascii=False, cls=NumpyJSONEncoder)

    # Opcional: salvar par CSV com a série temporal
    if salvar_csv and "serie_temporal" in dados_limpos and dados_limpos["serie_temporal"]:
        arquivo_csv = caminho_dir / f"{nome_base}_serie.csv"
        serie = dados_limpos["serie_temporal"]
        campos = list(serie[0].keys())
        with open(arquivo_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(serie)

    return arquivo_json


def carregar_simulacao(caminho_ou_nome: Union[str, Path]) -> Dict[str, Any]:
    """Carrega os dados de uma simulação a partir de um arquivo JSON.

    Pode receber o caminho absoluto/relativo ou apenas o nome do arquivo se
    estiver em PERSISTENCIA_DIR.
    """
    caminho = Path(caminho_ou_nome)
    if not caminho.is_file() and not caminho.is_absolute():
        caminho = PERSISTENCIA_DIR / caminho_ou_nome

    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de simulação não encontrado: {caminho}")

    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return dados


def listar_simulacoes(diretorio: Optional[Union[str, Path]] = None) -> List[Path]:
    """Lista todos os arquivos JSON de simulação salvos no diretório de persistência."""
    if diretorio is None:
        diretorio = PERSISTENCIA_DIR
    caminho_dir = Path(diretorio)
    if not caminho_dir.exists():
        return []
    return sorted(list(caminho_dir.glob("sim_*.json")), key=lambda p: p.stat().st_mtime)


def carregar_para_dataframe(dados_ou_caminho: Union[str, Path, Dict[str, Any]]) -> Tuple[Dict[str, Any], Any]:
    """Carrega os dados e converte a série temporal em DataFrame do pandas.

    Se o pandas não estiver instalado, devolve a série temporal como lista de dicionários.
    Retorna uma tupla (metadados: dict, serie_temporal: DataFrame ou List[dict]).
    """
    if isinstance(dados_ou_caminho, (str, Path)):
        dados = carregar_simulacao(dados_ou_caminho)
    else:
        dados = dados_ou_caminho

    metadados = {
        "seed": dados.get("seed"),
        "timestamp": dados.get("timestamp"),
        "total_erros_criados": dados.get("total_erros_criados"),
        "total_erros_eliminados": dados.get("total_erros_eliminados"),
        "parametros_iniciais": dados.get("parametros_iniciais", {}),
        "resumo": dados.get("resumo", {}),
    }

    serie = dados.get("serie_temporal", [])

    try:
        import pandas as pd
        df = pd.DataFrame(serie)
        return metadados, df
    except ImportError:
        return metadados, serie
