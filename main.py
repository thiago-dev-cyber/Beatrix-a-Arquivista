"""
Beatrix — Arquivista de Documentos Fiscais
==========================================

Renomeia e organiza PDFs e XMLs fiscais no padrão:
    TIPO NUMERO EMISSOR.pdf

Opcionalmente puxa anexos diretamente do Outlook antes de processar.

────────────────────────────────────────────────────────────────────────────────
USO RÁPIDO
────────────────────────────────────────────────────────────────────────────────

1. Coloque arquivos manualmente em /entrada  →  python main.py
2. Puxar do Outlook e processar             →  python main.py --outlook
3. Só puxar do Outlook, sem processar       →  python main.py --outlook --so-baixar
4. Ver pastas disponíveis no Outlook        →  python main.py --listar-pastas
5. Processar arquivo específico             →  python main.py --arquivo nota.pdf

────────────────────────────────────────────────────────────────────────────────
CONFIGURAÇÃO  (beatrix.json)
────────────────────────────────────────────────────────────────────────────────

Copie beatrix_example.json para beatrix.json e edite conforme necessário.

Campos principais:

  empresas              Mapeia CNPJ (só dígitos) → nome da pasta de saída.
                        Ex: {"02891270000165": "Matriz", "03432634000101": "Filial"}
                        Se omitido, todos os arquivos vão para /saida/ diretamente.

  outlook.ativo         true  = puxa Outlook ao rodar  python main.py --outlook
                        false = ignora o Outlook (padrão)

  outlook.pasta         Pasta do Outlook a varrer.
                        "Caixa de Entrada"           → inbox principal
                        "Caixa de Entrada/Fiscais"   → subpasta Fiscais dentro da inbox

  outlook.extensoes     Quais anexos baixar. Padrão: [".pdf", ".xml"]

  outlook.palavras_assunto
                        Filtra e-mails pelo assunto (OR, case-insensitive).
                        Ex: ["nota fiscal", "nf-e", "danfe"]
                        [] ou omitido = sem filtro de assunto

  outlook.remetentes    Filtra por remetente.
                        Ex: ["fiscal@fornecedor.com.br"]
                        [] ou omitido = qualquer remetente

  outlook.apenas_nao_lidos
                        true  = processa só e-mails não lidos (padrão)
                        false = processa todos

  outlook.marcar_como_lido
                        true  = marca como lido após baixar os anexos

  outlook.tamanho_min_kb / tamanho_max_kb
                        Faixa de tamanho dos anexos em KB.
                        Útil para descartar imagens de assinatura (min: 5)
                        ou arquivos absurdamente grandes (max: 20480 = 20 MB).

────────────────────────────────────────────────────────────────────────────────
ESTRUTURA DE PASTAS
────────────────────────────────────────────────────────────────────────────────

  /entrada      Arquivos a processar (manual ou via --outlook)
  /saida        Arquivos renomeados/gerados
  /saida/<empresa>   Quando empresas estão mapeadas no beatrix.json

────────────────────────────────────────────────────────────────────────────────
EXEMPLOS DE SAÍDA
────────────────────────────────────────────────────────────────────────────────

  entrada: 12345.pdf
  saída:   NF-e 000001234 Acme Comercio Ltda.pdf

  entrada: nfe_12345.xml
  saída:   NF-e 000001234 Acme Comercio Ltda.pdf   (PDF gerado a partir do XML)

────────────────────────────────────────────────────────────────────────────────
DEDUPLICAÇÃO PDF / XML
────────────────────────────────────────────────────────────────────────────────

Se a mesma nota chegar em PDF e XML (ex: o fornecedor mandou os dois), o Beatrix
prefere o PDF — que já é o documento final — e descarta o XML automaticamente,
evitando gerar dois arquivos para a mesma nota.

────────────────────────────────────────────────────────────────────────────────
PROCESSAMENTO AUTOMÁTICO CONTÍNUO
────────────────────────────────────────────────────────────────────────────────

Para monitoramento em tempo real ou agendado, use o monitor.py:

    python monitor.py                  # modo configurado no beatrix.json
    python monitor.py --modo agendado  # varredura a cada N minutos
    python monitor.py --uma-vez        # processa e sai

O monitor.py também integra o Outlook automaticamente quando outlook.ativo = true.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
from pathlib import Path

from modulos.utils import garantir_pasta
from modulos.pipeline import processar_arquivo

log = logging.getLogger("beatrix.main")

BASE    = Path(__file__).resolve().parent
ENTRADA = BASE / "entrada"
SAIDA   = BASE / "saida"


# ── Config ────────────────────────────────────────────────────────────────────

def _carregar_config() -> dict:
    cfg_path = BASE / "beatrix.json"
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"Erro ao ler beatrix.json: {e}")
        return {}


def _empresas(cfg: dict) -> dict:
    return {k: v for k, v in cfg.get("empresas", {}).items()
            if not k.startswith("_")}


# ── Deduplicação PDF/XML ──────────────────────────────────────────────────────

def _agrupar_por_chave(pasta: Path, exts: set[str]) -> dict[str, list[Path]]:
    _sufixo = re.compile(r'[-_](nfe|nfce|cte|cteos|mdfe|bpe|nfse|xml|pdf)$', re.IGNORECASE)
    grupos: dict[str, list[Path]] = {}
    for arq in pasta.iterdir():
        if not arq.is_file() or arq.suffix.lower() not in exts:
            continue
        chave = _sufixo.sub('', arq.stem).strip()
        grupos.setdefault(chave, []).append(arq)
    return grupos


def _selecionar_arquivos(arquivos: list[Path]) -> list[Path]:
    """Se o grupo tiver PDF e XML da mesma nota, prefere o PDF e descarta o XML."""
    pdfs = [f for f in arquivos if f.suffix.lower() == ".pdf"]
    xmls = [f for f in arquivos if f.suffix.lower() == ".xml"]
    if pdfs and xmls:
        for xml in xmls:
            descartado = ENTRADA / f"_dup_{xml.name}"
            try:
                shutil.move(str(xml), str(descartado))
                log.info(f"Deduplicação: XML descartado em favor do PDF → {xml.name}")
            except Exception:
                pass
        return pdfs
    return arquivos


def _listar_entrada() -> list[Path]:
    exts = {".pdf", ".xml"}
    grupos = _agrupar_por_chave(ENTRADA, exts)
    resultado: list[Path] = []
    for arquivos in grupos.values():
        resultado.extend(_selecionar_arquivos(arquivos))
    return resultado


# ── Outlook ───────────────────────────────────────────────────────────────────

def _puxar_outlook(cfg: dict):
    """Baixa anexos do Outlook para /entrada conforme configurado no beatrix.json."""
    cfg_out = cfg.get("outlook", {})
    if not cfg_out.get("ativo", False):
        print("[OUTLOOK] outlook.ativo = false no beatrix.json. Pulando.")
        print("          Para ativar, defina \"ativo\": true na seção outlook.")
        return

    try:
        from modulos.outlook_connector import OutlookConnector, FiltroEmail
    except ImportError as e:
        print(f"[ERRO] Outlook connector indisponível: {e}")
        print("       Instale com: pip install pywin32")
        return

    print(f"[OUTLOOK] Conectando ao Outlook...")
    print(f"          Pasta : {cfg_out.get('pasta', 'Caixa de Entrada')}")

    conector = OutlookConnector(pasta_destino=str(ENTRADA))
    filtro = FiltroEmail(
        extensoes        = cfg_out.get("extensoes", [".pdf", ".xml"]),
        palavras_assunto = cfg_out.get("palavras_assunto", []) or [],
        palavras_corpo   = cfg_out.get("palavras_corpo",   []) or [],
        remetentes       = cfg_out.get("remetentes",       []) or None,
        pasta_outlook    = cfg_out.get("pasta", "Caixa de Entrada"),
        marcar_como_lido = cfg_out.get("marcar_como_lido", True),
        apenas_nao_lidos = cfg_out.get("apenas_nao_lidos", True),
        tamanho_min_kb   = cfg_out.get("tamanho_min_kb")   or None,
        tamanho_max_kb   = cfg_out.get("tamanho_max_kb")   or None,
        mover_para       = "Caixa de Entrada/Notas",
    )

    try:
        resultado = conector.baixar_anexos(filtro)
    except Exception as e:
        print(f"[ERRO] Falha ao acessar Outlook: {e}")
        return

    print(f"[OUTLOOK] {resultado.resumo()}")
    for caminho in resultado.baixados:
        print(f"          [+] {Path(caminho).name}")
    for erro in resultado.erros:
        print(f"          [!] {erro}")


def _listar_pastas_outlook(cfg: dict):
    """Imprime as pastas disponíveis no Outlook — útil para configurar beatrix.json."""
    try:
        from modulos.outlook_connector import OutlookConnector
    except ImportError as e:
        print(f"[ERRO] {e}")
        return

    conector = OutlookConnector(pasta_destino=str(ENTRADA))
    try:
        pastas = conector.listar_pastas()
        print("\nPastas disponíveis no Outlook:")
        print("─" * 40)
        for p in pastas:
            print(f"  {p}")
        print("\nCopie o caminho desejado para outlook.pasta no beatrix.json.")
    except Exception as e:
        print(f"[ERRO] {e}")


# ── Processamento ─────────────────────────────────────────────────────────────

def _processar_pasta(cfg: dict):
    empresas = _empresas(cfg)
    if empresas:
        print(f"[INFO] {len(empresas)} empresa(s) mapeada(s) — separando por CNPJ.")

    arquivos = _listar_entrada()
    if not arquivos:
        print("[INFO] Nenhum arquivo em /entrada.")
        return

    ok = err = 0
    for path in arquivos:
        try:
            r = processar_arquivo(str(path), str(SAIDA), empresas or None)
            destino_rel = Path(r["destino"]).relative_to(BASE)
            print(f"[OK] {path.name} → {destino_rel}  ({r['operacao']})")
            ok += 1
        except ValueError as e:
            print(f"[IGNORADO] {path.name}: {e}")
            err += 1
        except Exception as e:
            print(f"[ERRO] {path.name}: {type(e).__name__}: {e}")
            err += 1

    print(f"\n{'─'*50}")
    print(f"Concluído: {ok} processado(s), {err} com problema.")
    print(f"Saída em:  {SAIDA}")


def _processar_arquivo_unico(caminho: str, cfg: dict):
    path = Path(caminho).resolve()
    if not path.exists():
        print(f"[ERRO] Arquivo não encontrado: {caminho}")
        return

    empresas = _empresas(cfg)
    try:
        r = processar_arquivo(str(path), str(SAIDA), empresas or None)
        print(f"[OK] {path.name} → {r['nome']}  ({r['operacao']})")
        print(f"     Salvo em: {r['destino']}")
    except ValueError as e:
        print(f"[IGNORADO] {path.name}: {e}")
    except Exception as e:
        print(f"[ERRO] {path.name}: {type(e).__name__}: {e}")


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Beatrix — Arquivista de Documentos Fiscais",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python main.py                          # processa /entrada\n"
            "  python main.py --outlook                # puxar Outlook + processar\n"
            "  python main.py --outlook --so-baixar    # só baixar do Outlook\n"
            "  python main.py --listar-pastas          # ver pastas do Outlook\n"
            "  python main.py --arquivo nota.pdf       # processar arquivo específico\n"
        ),
    )
    parser.add_argument(
        "--outlook", action="store_true",
        help="Puxa anexos do Outlook para /entrada antes de processar.",
    )
    parser.add_argument(
        "--so-baixar", action="store_true",
        help="Combinado com --outlook: só baixa os anexos, não processa.",
    )
    parser.add_argument(
        "--listar-pastas", action="store_true",
        help="Lista as pastas disponíveis no Outlook e sai.",
    )
    parser.add_argument(
        "--arquivo", metavar="CAMINHO",
        help="Processa um arquivo específico em vez de toda a pasta /entrada.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    garantir_pasta(str(ENTRADA))
    garantir_pasta(str(SAIDA))

    cfg = _carregar_config()

    # ── Listar pastas do Outlook
    if args.listar_pastas:
        _listar_pastas_outlook(cfg)
        return

    # ── Arquivo único
    if args.arquivo:
        _processar_arquivo_unico(args.arquivo, cfg)
        return

    # ── Fluxo principal
    if args.outlook:
        _puxar_outlook(cfg)
        if args.so_baixar:
            return

    _processar_pasta(cfg)


if __name__ == "__main__":
    main()
