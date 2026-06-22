"""
watchdog.py — Monitora a pasta /entrada e processa arquivos automaticamente.

Requer: pip install watchdog schedule

Dois modos de operação:
    1. Modo evento  — reage imediatamente quando um arquivo é detectado na pasta
    2. Modo agendado — executa varredura completa em intervalos configuráveis
                       (útil para integração com Outlook ou pastas de rede)

Uso:
    python monitor.py              # inicia com config em beatrix.json
    python monitor.py --intervalo 30   # sobrescreve intervalo para 30 min
    python monitor.py --uma-vez        # processa a pasta e sai (sem loop)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("beatrix.watchdog")


# ── Dependências opcionais ────────────────────────────────────────────────────

def _importar_watchdog_lib():
    try:
        import importlib
        obs_mod = importlib.import_module('watchdog.observers')
        evt_mod = importlib.import_module('watchdog.events')
        return obs_mod.Observer, evt_mod.FileSystemEventHandler
    except (ImportError, AttributeError):
        return None, None

def _importar_schedule():
    try:
        import schedule
        return schedule
    except ImportError:
        return None


# ── Configuração ──────────────────────────────────────────────────────────────

BASE = Path(__file__).resolve().parent          # raiz do projeto

PASTAS = {
    "entrada":    BASE / "entrada",
    "saida":      BASE / "saida",
    "processado": BASE / "processado",
    "erro":       BASE / "erro",
}

CONFIG_PADRAO = {
    "intervalo_minutos": 15,          # para modo agendado
    "extensoes":         [".pdf", ".xml"],
    "modo":              "evento",    # "evento" | "agendado" | "ambos"
    "log_level":         "INFO",
    "outlook": {
        "ativo":            False,
        "pasta":            "Caixa de Entrada",
        "extensoes":        [".pdf", ".xml"],
        "palavras_assunto": [],
        "palavras_corpo":   [],
        "remetentes":       [],
        "marcar_como_lido": True,
        "apenas_nao_lidos": True,
        "tamanho_min_kb":   None,
        "tamanho_max_kb":   None,
    },
}


def _carregar_config() -> dict:
    cfg_path = BASE / "beatrix.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, encoding="utf-8") as f:
                dados = json.load(f)
            # Merge com padrão (padrão como base, arquivo sobrescreve)
            config = {**CONFIG_PADRAO, **dados}
            config["outlook"] = {**CONFIG_PADRAO["outlook"], **dados.get("outlook", {})}
            return config
        except Exception as e:
            log.warning(f"Erro ao ler beatrix.json ({e}). Usando configuração padrão.")
    return CONFIG_PADRAO.copy()


def _garantir_pastas():
    for pasta in PASTAS.values():
        pasta.mkdir(parents=True, exist_ok=True)


# ── Deduplicação PDF/XML da mesma nota ───────────────────────────────────────

def _agrupar_por_chave(pasta: Path, exts: set[str]) -> dict[str, list[Path]]:
    """
    Agrupa arquivos da pasta /entrada pela chave da nota fiscal.

    A chave é o stem do arquivo sem sufixos como '-nfe', '-cte', '-pdf', etc.
    Arquivos sem padrão reconhecível ficam num grupo próprio com chave = nome completo.

    Retorna dict { chave: [path1, path2, ...] }
    """
    import re
    grupos: dict[str, list[Path]] = {}
    # Remove sufixos descritivos comuns antes de comparar
    _sufixo = re.compile(r'[-_](nfe|nfce|cte|cteos|mdfe|bpe|nfse|xml|pdf)$', re.IGNORECASE)

    for arq in pasta.iterdir():
        if not arq.is_file():
            continue
        if arq.suffix.lower() not in exts:
            continue
        chave = _sufixo.sub('', arq.stem).strip()
        grupos.setdefault(chave, []).append(arq)

    return grupos


def _selecionar_arquivo(arquivos: list[Path]) -> list[Path]:
    """
    Dado um grupo de arquivos da mesma nota, retorna o subconjunto a processar.

    Regra: se o grupo contém PDF e XML referentes à mesma nota, prefere o PDF
    (já é o documento final) e descarta o XML — evita gerar dois arquivos de
    saída para a mesma nota.

    Se houver só um tipo, retorna todos os arquivos do grupo.
    """
    pdfs = [f for f in arquivos if f.suffix.lower() == ".pdf"]
    xmls = [f for f in arquivos if f.suffix.lower() == ".xml"]

    if pdfs and xmls:
        log.info(
            f"Deduplicação: grupo com PDF e XML detectado. "
            f"Preferindo PDF(s): {[p.name for p in pdfs]}. "
            f"XML(s) ignorado(s): {[x.name for x in xmls]}"
        )
        # Move os XMLs para /processado marcando como duplicata
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for xml in xmls:
            destino = PASTAS["processado"] / f"{ts}_dup_{xml.name}"
            try:
                shutil.move(str(xml), str(destino))
                log.info(f"XML duplicado movido para /processado: {xml.name}")
            except Exception as e:
                log.warning(f"Não foi possível mover XML duplicado {xml.name}: {e}")
        return pdfs

    return arquivos


# ── Motor de processamento ────────────────────────────────────────────────────

def _processar_arquivo(path: Path, config: dict) -> bool:
    """
    Delega o processamento ao pipeline principal (main.py).
    Move o arquivo para /processado ou /erro conforme o resultado.
    Retorna True se processou com sucesso.
    """
    ext = path.suffix.lower()
    if ext not in config.get("extensoes", [".pdf", ".xml"]):
        log.debug(f"Extensão ignorada: {path.name}")
        return False

    # Aguarda o arquivo terminar de ser escrito (evita processar arquivo parcial)
    _aguardar_arquivo_estavel(path)

    log.info(f"Processando: {path.name}")

    try:
        sys.path.insert(0, str(BASE))
        from modulos.pipeline import processar_arquivo

        cfg = config  # passa o config para obter empresas
        empresas = {k: v for k, v in cfg.get("empresas", {}).items()
                    if not k.startswith("_")} or None

        r = processar_arquivo(str(path), str(PASTAS["saida"]), empresas)
        operacao = r["operacao"]

        # Move original para /processado com timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino_proc = PASTAS["processado"] / f"{ts}_{path.name}"
        shutil.move(str(path), str(destino_proc))
        log.info(f"[OK] {path.name} → {r['nome']} ({operacao}) → /processado")
        return True

    except Exception as e:
        log.error(f"[ERRO] {path.name}: {type(e).__name__}: {e}")
        # Move para /erro com timestamp e arquivo de log
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino_erro = PASTAS["erro"] / f"{ts}_{path.name}"
        try:
            shutil.move(str(path), str(destino_erro))
            # Salva o erro em .txt ao lado do arquivo
            log_erro = destino_erro.with_suffix(".erro.txt")
            log_erro.write_text(
                f"Arquivo: {path.name}\n"
                f"Data: {datetime.now().isoformat()}\n"
                f"Erro: {type(e).__name__}: {e}\n",
                encoding="utf-8",
            )
        except Exception as mv_err:
            log.error(f"Erro ao mover para /erro: {mv_err}")
        return False


def _aguardar_arquivo_estavel(path: Path, tentativas: int = 10, intervalo: float = 0.5):
    """Espera o tamanho do arquivo estabilizar antes de processar."""
    tamanho_anterior = -1
    for _ in range(tentativas):
        try:
            tamanho_atual = path.stat().st_size
        except FileNotFoundError:
            time.sleep(intervalo)
            continue
        if tamanho_atual == tamanho_anterior and tamanho_atual > 0:
            return
        tamanho_anterior = tamanho_atual
        time.sleep(intervalo)


def _varrer_pasta(config: dict) -> tuple[int, int]:
    """
    Processa todos os arquivos pendentes em /entrada.

    Antes de processar individualmente, agrupa por nota fiscal para aplicar
    a deduplicação PDF/XML (quando a mesma nota chega em ambos os formatos,
    o PDF é preferido e o XML é descartado).

    Retorna (ok, erros).
    """
    ok = erros = 0
    exts = set(config.get("extensoes", [".pdf", ".xml"]))

    # Agrupa por chave de nota e aplica deduplicação
    grupos = _agrupar_por_chave(PASTAS["entrada"], exts)

    if not grupos:
        log.debug("Nenhum arquivo pendente em /entrada.")
        return 0, 0

    # Flatten após deduplicação
    arquivos_para_processar: list[Path] = []
    for arquivos in grupos.values():
        arquivos_para_processar.extend(_selecionar_arquivo(arquivos))

    if not arquivos_para_processar:
        return 0, 0

    log.info(f"Varrendo /entrada: {len(arquivos_para_processar)} arquivo(s) a processar.")
    for arq in arquivos_para_processar:
        if _processar_arquivo(arq, config):
            ok += 1
        else:
            erros += 1

    return ok, erros


# ── Integração com Outlook ────────────────────────────────────────────────────

def _baixar_outlook(config: dict):
    """Puxa anexos do Outlook para /entrada antes de varrer a pasta."""
    cfg_out = config.get("outlook", {})
    if not cfg_out.get("ativo", False):
        return

    try:
        from modulos.outlook_connector import OutlookConnector, FiltroEmail
    except ImportError as e:
        log.error(f"Outlook connector indisponível: {e}")
        return

    # Normaliza listas vazias para None onde o conector espera None = sem filtro
    remetentes      = cfg_out.get("remetentes", []) or None
    palavras_corpo  = cfg_out.get("palavras_corpo", []) or []
    palavras_assunto = cfg_out.get("palavras_assunto", []) or []
    tamanho_min     = cfg_out.get("tamanho_min_kb") or None
    tamanho_max     = cfg_out.get("tamanho_max_kb") or None

    try:
        conector = OutlookConnector(pasta_destino=str(PASTAS["entrada"]))
        filtro = FiltroEmail(
            extensoes        = cfg_out.get("extensoes", [".pdf", ".xml"]),
            palavras_assunto = palavras_assunto,
            palavras_corpo   = palavras_corpo,
            remetentes       = remetentes,
            pasta_outlook    = cfg_out.get("pasta", "Caixa de Entrada"),
            marcar_como_lido = cfg_out.get("marcar_como_lido", True),
            apenas_nao_lidos = cfg_out.get("apenas_nao_lidos", True),
            tamanho_min_kb   = tamanho_min,
            tamanho_max_kb   = tamanho_max,
        )
        resultado = conector.baixar_anexos(filtro)

        if resultado.total > 0 or resultado.erros:
            log.info(f"Outlook: {resultado.resumo()}")
        else:
            log.debug("Outlook: nenhum anexo novo.")
    except Exception as e:
        log.error(f"Erro ao acessar Outlook: {e}")


# ── Modo evento (watchdog real-time) ──────────────────────────────────────────

def _iniciar_modo_evento(config: dict):
    Observer, FileSystemEventHandler = _importar_watchdog_lib()
    if Observer is None:
        log.error("Biblioteca 'watchdog' não instalada. Execute: pip install watchdog")
        sys.exit(1)

    exts = set(config.get("extensoes", [".pdf", ".xml"]))

    class ManipuladorArquivo(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() in exts:
                # Pequena pausa para o SO terminar de gravar
                time.sleep(1)
                # Verifica deduplicação antes de processar o arquivo recém-chegado
                grupos = _agrupar_por_chave(PASTAS["entrada"], exts)
                chave = path.stem
                # Encontra o grupo que contém este arquivo
                for arquivos in grupos.values():
                    nomes = [a.name for a in arquivos]
                    if path.name in nomes:
                        selecionados = _selecionar_arquivo(arquivos)
                        # Só processa se este arquivo foi selecionado (não descartado)
                        if path in selecionados:
                            _processar_arquivo(path, config)
                        return
                # Fallback: processa diretamente se não achou no grupo
                _processar_arquivo(path, config)

    observer = Observer()
    observer.schedule(ManipuladorArquivo(), str(PASTAS["entrada"]), recursive=False)
    observer.start()
    log.info(f"Modo evento ativo — monitorando: {PASTAS['entrada']}")

    # FIX: no modo evento o Outlook também precisa ser consultado periodicamente.
    # Faz uma consulta inicial ao iniciar e depois a cada ciclo do loop principal.
    _baixar_outlook(config)

    return observer


# ── Modo agendado ─────────────────────────────────────────────────────────────

def _iniciar_modo_agendado(config: dict, intervalo_override: int = None):
    schedule = _importar_schedule()
    if schedule is None:
        log.error("Biblioteca 'schedule' não instalada. Execute: pip install schedule")
        sys.exit(1)

    intervalo = intervalo_override or config.get("intervalo_minutos", 15)

    def _ciclo():
        log.info(f"--- Ciclo agendado {datetime.now().strftime('%H:%M:%S')} ---")
        _baixar_outlook(config)
        ok, err = _varrer_pasta(config)
        log.info(f"Ciclo concluído: {ok} OK, {err} erro(s).")

    schedule.every(intervalo).minutes.do(_ciclo)
    log.info(f"Modo agendado ativo — intervalo: {intervalo} minuto(s).")

    # Roda uma vez imediatamente ao iniciar
    _ciclo()
    return schedule


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Beatrix Watchdog — monitora /entrada e processa documentos fiscais."
    )
    parser.add_argument(
        "--intervalo", type=int, default=None,
        help="Intervalo em minutos para modo agendado (sobrescreve beatrix.json)."
    )
    parser.add_argument(
        "--uma-vez", action="store_true",
        help="Processa /entrada uma única vez e sai (sem loop)."
    )
    parser.add_argument(
        "--modo", choices=["evento", "agendado", "ambos"], default=None,
        help="Modo de operação (sobrescreve beatrix.json)."
    )
    args = parser.parse_args()

    config = _carregar_config()
    if args.modo:
        config["modo"] = args.modo

    # Configura logging
    nivel = getattr(logging, config.get("log_level", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(BASE / "beatrix.log", encoding="utf-8"),
        ],
    )

    _garantir_pastas()
    log.info("=" * 50)
    log.info("Beatrix Watchdog iniciado.")
    log.info(f"Pastas: entrada={PASTAS['entrada']} | saida={PASTAS['saida']}")

    # Modo uma-vez
    if args.uma_vez:
        _baixar_outlook(config)
        ok, err = _varrer_pasta(config)
        log.info(f"Concluído: {ok} OK, {err} erro(s).")
        return

    # Modo contínuo
    modo = config.get("modo", "evento")
    observer = None
    sched = None

    if modo in ("evento", "ambos"):
        observer = _iniciar_modo_evento(config)

    if modo in ("agendado", "ambos"):
        sched = _iniciar_modo_agendado(config, args.intervalo)

    if observer is None and sched is None:
        log.error(f"Modo '{modo}' não reconhecido. Use: evento | agendado | ambos")
        sys.exit(1)

    # Captura Ctrl+C para encerramento limpo
    def _encerrar(sig, frame):
        log.info("Encerrando Beatrix Watchdog...")
        if observer:
            observer.stop()
            observer.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, _encerrar)
    signal.signal(signal.SIGTERM, _encerrar)

    # Loop principal
    # No modo evento, consulta o Outlook a cada intervalo configurado
    intervalo_outlook = config.get("intervalo_minutos", 15) * 60  # segundos
    ultimo_outlook = time.time()

    try:
        while True:
            if sched:
                sched.run_pending()

            # FIX: no modo evento puro, puxa Outlook periodicamente
            if observer and not sched:
                agora = time.time()
                if agora - ultimo_outlook >= intervalo_outlook:
                    _baixar_outlook(config)
                    ultimo_outlook = agora

            time.sleep(1)
    except KeyboardInterrupt:
        _encerrar(None, None)


if __name__ == "__main__":
    main()
