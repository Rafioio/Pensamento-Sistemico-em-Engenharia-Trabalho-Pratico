"""Testes de validação para a persistência dos dados de simulação (ABM).

Valida:
1. Existência e integridade do diretório persistencia/.
2. Execução de simulações com múltiplas sementes (2 ou 3).
3. Criação de arquivos JSON estruturados seguindo o padrão de nomenclatura.
4. Presença obrigatória e ausência de valores nulos em:
   - Metadados: seed, parametros_iniciais, total_erros_criados, total_erros_eliminados.
   - Série temporal: moral_media, erros_ativos, pressao.
5. Capacidade de carregamento dos dados e conversão para DataFrame / análise estatística.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dataclasses import replace
from configs.params import Params
from configs.paths import PERSISTENCIA_DIR
from model.model import BASE, executar_simulacao
from model.persistencia import (
    carregar_para_dataframe,
    carregar_simulacao,
    validar_dados_simulacao,
)


def testar_persistencia_com_multiplas_sementes():
    """Valida a persistência gerando dados para 3 sementes distintas."""
    print("Iniciando validação de persistência...")

    # Garante diretório
    assert PERSISTENCIA_DIR.exists(), f"Diretório {PERSISTENCIA_DIR} deve existir."
    gitkeep = PERSISTENCIA_DIR / ".gitkeep"
    assert gitkeep.exists(), f"Arquivo {gitkeep} deve existir para manter o diretório versionado."

    # Usamos T=50 para um teste rápido e completo
    par_teste = replace(BASE, T=50)
    sementes_teste = [42, 123, 999]
    arquivos_criados = []

    for seed in sementes_teste:
        print(f"\n--- Testando execução para seed={seed} ---")
        resultado = executar_simulacao(
            par=par_teste,
            seed=seed,
            salvar=True,
            salvar_csv=True,
            diretorio=PERSISTENCIA_DIR,
        )

        caminho_json = resultado["caminho_arquivo"]
        assert caminho_json is not None, "O caminho do arquivo salvo não pode ser None."
        caminho_json = Path(caminho_json)
        assert caminho_json.is_file(), f"Arquivo JSON não foi encontrado no disco: {caminho_json}"
        assert f"seed_{seed}" in caminho_json.name, f"Nome do arquivo deve conter a seed: {caminho_json.name}"
        arquivos_criados.append(caminho_json)

        # 1. Carregar via função de persistência
        dados = carregar_simulacao(caminho_json)

        # 2. Validar estrutura e ausência de nulos
        valido, erros = validar_dados_simulacao(dados)
        assert valido, f"Falha na validação de dados para seed {seed}: {erros}"

        # 3. Validar valores específicos de metadados
        assert dados["seed"] == seed, f"Esperado seed={seed}, obtido {dados['seed']}"
        assert isinstance(dados["parametros_iniciais"], dict), "parametros_iniciais deve ser dict"
        assert dados["parametros_iniciais"]["T"] == 50, "Parametro T inicial incorreto"
        assert isinstance(dados["total_erros_criados"], (int, float)), "total_erros_criados deve ser numérico"
        assert isinstance(dados["total_erros_eliminados"], (int, float)), "total_erros_eliminados deve ser numérico"
        assert dados["total_erros_criados"] >= 0, "total_erros_criados deve ser >= 0"
        assert dados["total_erros_eliminados"] >= 0, "total_erros_eliminados deve ser >= 0"

        # 4. Validar série temporal
        serie = dados["serie_temporal"]
        assert len(serie) == 50, f"Série temporal deve ter 50 passos, obtido {len(serie)}"

        for t, tick in enumerate(serie):
            assert tick["passo"] == t, f"Passo esperado {t}, obtido {tick['passo']}"
            assert tick["moral_media"] is not None, f"moral_media nula no passo {t}"
            assert 0.0 <= tick["moral_media"] <= 1.0, f"moral_media fora do intervalo [0, 1]: {tick['moral_media']}"
            assert tick["erros_ativos"] is not None, f"erros_ativos nulo no passo {t}"
            assert tick["erros_ativos"] >= 0, f"erros_ativos negativo no passo {t}"
            assert tick["pressao"] is not None, f"pressao nula no passo {t}"
            assert tick["pressao"] == par_teste.P, f"pressao inconsistente com parâmetro no passo {t}"

        # 5. Validar carregamento com pandas / tabular
        metadados, df_ou_serie = carregar_para_dataframe(caminho_json)
        assert metadados["seed"] == seed
        assert len(df_ou_serie) == 50

        print(f"✓ Semente {seed} validada com sucesso! Arquivo: {caminho_json.name}")
        print(f"  - Total erros criados: {dados['total_erros_criados']}")
        print(f"  - Total erros eliminados: {dados['total_erros_eliminados']}")
        print(f"  - Moral média (passo 0 / final): {serie[0]['moral_media']:.4f} / {serie[-1]['moral_media']:.4f}")
        print(f"  - Erros ativos (passo 0 / final): {serie[0]['erros_ativos']} / {serie[-1]['erros_ativos']}")

    print("\n" + "=" * 60)
    print("TODOS OS TESTES DE PERSISTÊNCIA PASSARAM COM SUCESSO!")
    print(f"Total de simulações validadas: {len(arquivos_criados)}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    testar_persistencia_com_multiplas_sementes()
