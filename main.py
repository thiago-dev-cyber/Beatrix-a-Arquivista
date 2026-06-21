"""
Beatrix — Arquivista de Documentos Fiscais

Renomeia e organiza PDFs e XMLs fiscais no padrão:
    TIPO NUMERO EMISSOR.pdf

Com separação por empresa quando beatrix.json contém o mapa de CNPJs.

Uso:
    Coloque arquivos na pasta /entrada
    Execute:  python main.py
    Resultado em /saida  (ou /saida/<empresa>/ se configurado)
"""
import json
import os

from modulos.utils import garantir_pasta
from modulos.pipeline import processar_arquivo

BASE    = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(BASE, "entrada")
SAIDA   = os.path.join(BASE, "saida")

garantir_pasta(ENTRADA)
garantir_pasta(SAIDA)


def _carregar_empresas() -> dict:
    cfg_path = os.path.join(BASE, "beatrix.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        return {k: v for k, v in cfg.get("empresas", {}).items()
                if not k.startswith("_")}
    except Exception:
        return {}


def main():
    empresas = _carregar_empresas()
    if empresas:
        print(f"[INFO] {len(empresas)} empresa(s) mapeada(s) — separando por CNPJ.")

    arquivos = [f for f in os.listdir(ENTRADA)
                if os.path.isfile(os.path.join(ENTRADA, f))]

    if not arquivos:
        print("[INFO] Nenhum arquivo em /entrada.")
        return

    ok = err = 0
    for nome in arquivos:
        path = os.path.join(ENTRADA, nome)
        try:
            r = processar_arquivo(path, SAIDA, empresas or None)
            destino_rel = os.path.relpath(r["destino"], BASE)
            print(f"[OK] {nome} → {destino_rel}  ({r['operacao']})")
            ok += 1
        except ValueError as e:
            print(f"[IGNORADO] {nome}: {e}")
            err += 1
        except Exception as e:
            print(f"[ERRO] {nome}: {type(e).__name__}: {e}")
            err += 1

    print(f"\n{'─'*50}")
    print(f"Concluído: {ok} processado(s), {err} com erro.")
    print(f"Saída em: {SAIDA}")


if __name__ == "__main__":
    main()