"""Script CLI para execução de simulações com persistência de dados.

Permite rodar simulações do modelo com uma ou múltiplas sementes aleatórias,
configurar parâmetros via linha de comando e persistir os resultados em formato
JSON estruturado (e opcionalmente CSV) no diretório `persistencia/`.
"""

from __future__ import annotations
import argparse
import sys
from dataclasses import replace
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.params import Params
from configs.paths import PERSISTENCIA_DIR
from model.model import BASE, executar_simulacao


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa simulações do modelo ABM e persiste dados e séries temporais."
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[0, 1, 2],
        help="Sementes aleatórias para execução das simulações (padrão: 0 1 2).",
    )
    parser.add_argument(
        "--passos",
        type=int,
        default=None,
        help="Número de passos de tempo T (padrão: valor do cenário base = 600).",
    )
    parser.add_argument(
        "--pressao",
        type=float,
        default=None,
        help="Nível de pressão operacional P (padrão: valor base = 0.5).",
    )
    parser.add_argument(
        "--corretores",
        type=int,
        default=None,
        help="Número de corretores K (padrão: valor base = 8).",
    )
    parser.add_argument(
        "--politica",
        type=str,
        choices=["aleatoria", "reativa", "cobertura"],
        default=None,
        help="Política de movimento dos corretores.",
    )
    parser.add_argument(
        "--salvar-csv",
        action="store_true",
        help="Se informado, também salva um arquivo CSV com a série temporal por execução.",
    )
    parser.add_argument(
        "--sem-salvar",
        action="store_true",
        help="Executa sem salvar em disco (apenas para teste de performance).",
    )
    parser.add_argument(
        "--dir-saida",
        type=str,
        default=None,
        help=f"Diretório de persistência customizado (padrão: {PERSISTENCIA_DIR}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Prepara parâmetros base
    par = BASE
    alteracoes = {}
    if args.passos is not None:
        alteracoes["T"] = args.passos
    if args.pressao is not None:
        alteracoes["P"] = args.pressao
    if args.corretores is not None:
        alteracoes["K"] = args.corretores
    if args.politica is not None:
        alteracoes["politica"] = args.politica

    if alteracoes:
        par = replace(par, **alteracoes)

    salvar = not args.sem_salvar
    dir_saida = Path(args.dir_saida) if args.dir_saida else PERSISTENCIA_DIR

    print("=" * 65)
    print(" INICIALIZANDO SIMULAÇÕES ABM - PENSAMENTO SISTÊMICO")
    print("=" * 65)
    print(f"Diretório de persistência: {dir_saida.resolve()}")
    print(f"Sementes a executar: {args.seeds}")
    print(f"Passos (T): {par.T} | Pressão (P): {par.P} | Corretores (K): {par.K}")
    print(f"Política: {par.politica} | Salvar CSV: {args.salvar_csv}")
    print("-" * 65)

    arquivos_gerados = []
    for s in args.seeds:
        print(f"\n[+] Executando simulação com semente seed={s} (T={par.T})...")
        res = executar_simulacao(
            par=par,
            seed=s,
            salvar=salvar,
            salvar_csv=args.salvar_csv,
            diretorio=dir_saida,
        )

        criados = res["total_erros_criados"]
        eliminados = res["total_erros_eliminados"]
        desordem_fim = res["dados_completos"]["resumo"]["desordem_final"]
        erros_ativos_fim = res["dados_completos"]["resumo"]["erros_ativos_final"]
        caminho = res.get("caminho_arquivo")

        print(f"    - Erros criados no total    : {criados}")
        print(f"    - Erros eliminados no total : {eliminados}")
        print(f"    - Erros ativos finais       : {erros_ativos_fim}")
        print(f"    - Desordem final            : {desordem_fim:.4f}")
        if caminho:
            print(f"    - Arquivo JSON salvo        : {caminho}")
            arquivos_gerados.append(caminho)

    print("\n" + "=" * 65)
    print(f" Concluído! Total de {len(arquivos_gerados)} arquivos persistidos.")
    print("=" * 65)


if __name__ == "__main__":
    main()
