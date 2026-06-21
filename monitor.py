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
        "marcar_como_lido": True,
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
    """Processa todos os arquivos pendentes em /entrada. Retorna (ok, erros)."""
    ok = erros = 0
    exts = set(config.get("extensoes", [".pdf", ".xml"]))

    arquivos = [
        f for f in PASTAS["entrada"].iterdir()
        if f.is_file() and f.suffix.lower() in exts
    ]

    if not arquivos:
        log.debug("Nenhum arquivo pendente em /entrada.")
        return 0, 0

    log.info(f"Varrendo /entrada: {len(arquivos)} arquivo(s) encontrado(s).")
    for arq in arquivos:
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

    try:
        conector = OutlookConnector(pasta_destino=str(PASTAS["entrada"]))
        filtro = FiltroEmail(
            extensoes=cfg_out.get("extensoes", [".pdf", ".xml"]),
            palavras_assunto=cfg_out.get("palavras_assunto", []),
            pasta_outlook=cfg_out.get("pasta", "Caixa de Entrada"),
            marcar_como_lido=cfg_out.get("marcar_como_lido", True),
            apenas_nao_lidos=True,
        )
        resultado = conector.baixar_anexos(filtro)
        if resultado.total > 0:
            log.info(f"Outlook: {resultado.resumo()}")
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
                _processar_arquivo(path, config)

    observer = Observer()
    observer.schedule(ManipuladorArquivo(), str(PASTAS["entrada"]), recursive=False)
    observer.start()
    log.info(f"Modo evento ativo — monitorando: {PASTAS['entrada']}")
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
    try:
        while True:
            if sched:
                sched.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        _encerrar(None, None)


if __name__ == "__main__":
    main()