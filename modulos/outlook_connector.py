"""
outlook_connector.py — Integração com Microsoft Outlook via COM Automation.

Requer: pip install pywin32
Requer: Outlook instalado e aberto na máquina.

Uso básico:
    from modulos.outlook_connector import OutlookConnector, FiltroEmail

    conector = OutlookConnector(pasta_destino="entrada")
    filtro = FiltroEmail(
        extensoes=[".pdf", ".xml"],
        data_inicio="2024-01-01",
        data_fim="2024-03-31",
        palavras_assunto=["nota fiscal", "nf-e"],
        pasta_outlook="Caixa de Entrada",
    )
    baixados = conector.baixar_anexos(filtro)
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Constante COM para Inbox — independente do idioma do Outlook
_OL_FOLDER_INBOX = 6


# ── Dependência opcional (só Windows) ────────────────────────────────────────

def _importar_win32():
    try:
        import win32com.client
        return win32com.client
    except ImportError:
        raise ImportError(
            "pywin32 não encontrado. Instale com: pip install pywin32\n"
            "Este módulo funciona apenas no Windows com Outlook instalado."
        )


# ── Filtro de e-mails ─────────────────────────────────────────────────────────

@dataclass
class FiltroEmail:
    """
    Define os critérios de busca de e-mails no Outlook.

    Atributos:
        extensoes:          Lista de extensões permitidas, ex: [".pdf", ".xml"]
                            None = qualquer anexo.
        data_inicio:        Data inicial (str "YYYY-MM-DD" ou objeto date/datetime).
        data_fim:           Data final (str "YYYY-MM-DD" ou objeto date/datetime).
        palavras_assunto:   Palavras que devem aparecer no assunto (case-insensitive).
                            Lógica OR — basta UMA das palavras estar presente.
        palavras_corpo:     Idem, mas aplicado ao corpo do e-mail.
        remetentes:         Lista de endereços de e-mail permitidos.
                            None = qualquer remetente.
        pasta_outlook:      Nome da pasta do Outlook a varrer.
                            Suporta subpastas: "Caixa de Entrada/Fiscais".
                            Use "Caixa de Entrada" ou "Inbox" para a caixa principal
                            — ambos são resolvidos via GetDefaultFolder(6), que é
                            imune ao idioma configurado no Outlook.
        apenas_nao_lidos:   Se True, processa apenas e-mails não lidos.
        marcar_como_lido:   Se True, marca os e-mails processados como lidos.
        tamanho_min_kb:     Tamanho mínimo do anexo em KB (None = sem limite).
        tamanho_max_kb:     Tamanho máximo do anexo em KB (None = sem limite).
    """
    extensoes:         Optional[list[str]] = field(default_factory=lambda: [".pdf", ".xml"])
    data_inicio:       Optional[str | date | datetime] = None
    data_fim:          Optional[str | date | datetime] = None
    palavras_assunto:  list[str] = field(default_factory=list)
    palavras_corpo:    list[str] = field(default_factory=list)
    remetentes:        Optional[list[str]] = None
    pasta_outlook:     str = "Caixa de Entrada"
    apenas_nao_lidos:  bool = False
    marcar_como_lido:  bool = False
    tamanho_min_kb:    Optional[int] = None
    tamanho_max_kb:    Optional[int] = None
    mover_para:        str | None = None

    def _parse_data(self, v) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, date):
            return datetime(v.year, v.month, v.day)
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Formato de data não reconhecido: {v!r}")
        raise TypeError(f"Tipo inválido para data: {type(v)}")

    @property
    def dt_inicio(self) -> Optional[datetime]:
        return self._parse_data(self.data_inicio)

    @property
    def dt_fim(self) -> Optional[datetime]:
        dt = self._parse_data(self.data_fim)
        if dt:
            return dt.replace(hour=23, minute=59, second=59)
        return dt

    def extensoes_norm(self) -> Optional[set[str]]:
        if self.extensoes is None:
            return None
        return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in self.extensoes}


# ── Resultado de uma execução ─────────────────────────────────────────────────

@dataclass
class ResultadoBaixar:
    baixados:  list[str] = field(default_factory=list)   # caminhos dos arquivos salvos
    ignorados: int = 0
    erros:     list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.baixados)

    def resumo(self) -> str:
        return (
            f"Baixados: {self.total}  |  "
            f"Ignorados: {self.ignorados}  |  "
            f"Erros: {len(self.erros)}"
        )


# ── Resultado de movimentação ─────────────────────────────────────────────────

@dataclass
class ResultadoMover:
    movidos:   list[tuple[str, str]] = field(default_factory=list)  # (assunto, pasta_destino)
    ignorados: int = 0
    erros:     list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.movidos)

    def resumo(self) -> str:
        return (
            f"Movidos: {self.total}  |  "
            f"Ignorados: {self.ignorados}  |  "
            f"Erros: {len(self.erros)}"
        )


# ── Regras de movimentação ────────────────────────────────────────────────────

@dataclass
class RegraMovimento:
    """
    Define uma regra que mapeia e-mails para uma pasta de destino no Outlook.

    A regra avalia cada e-mail e retorna o caminho da pasta de destino
    (string no formato "Caixa de Entrada/Subpasta") ou None se não casar.

    Atributos:
        destino:          Caminho da pasta de destino no Outlook.
                          Ex: "Caixa de Entrada/Lojas/QC Matriz"
        remetentes:       Move o e-mail se o remetente estiver nesta lista.
                          Comparação case-insensitive, por sufixo ou exato.
        palavras_assunto: Move se o assunto contiver ao menos UMA das palavras (OR).
        palavras_corpo:   Move se o corpo contiver ao menos UMA das palavras (OR).
        remetentes_corpo: Move se o corpo contiver o endereço de e-mail de algum
                          dos remetentes desta lista (útil para e-mails encaminhados).

    Lógica: todas as condições definidas devem ser satisfeitas (AND entre grupos,
    OR dentro de cada grupo).
    """
    destino:           str
    remetentes:        list[str] = field(default_factory=list)
    palavras_assunto:  list[str] = field(default_factory=list)
    palavras_corpo:    list[str] = field(default_factory=list)
    remetentes_corpo:  list[str] = field(default_factory=list)

    def destinos_possiveis(self) -> list[str]:
        """Retorna os caminhos de pasta que esta regra pode usar."""
        return [self.destino]

    def avaliar(self, email) -> Optional[str]:
        """
        Avalia o e-mail contra a regra.
        Retorna o caminho de destino se casar, None caso contrário.
        """
        try:
            remetente = (email.SenderEmailAddress or "").lower().strip()
        except Exception:
            remetente = ""

        try:
            assunto = (email.Subject or "").upper()
        except Exception:
            assunto = ""

        # Corpo só é lido se necessário (operação cara no COM)
        _corpo: Optional[str] = None

        def corpo() -> str:
            nonlocal _corpo
            if _corpo is None:
                try:
                    _corpo = (email.Body or "").lower()
                except Exception:
                    _corpo = ""
            return _corpo

        # Remetente direto
        if self.remetentes:
            if not any(r.lower() in remetente for r in self.remetentes):
                return None

        # Assunto
        if self.palavras_assunto:
            if not any(p.upper() in assunto for p in self.palavras_assunto):
                return None

        # Corpo — palavras
        if self.palavras_corpo:
            if not any(p.lower() in corpo() for p in self.palavras_corpo):
                return None

        # Corpo — remetentes mencionados (útil para encaminhados)
        if self.remetentes_corpo:
            if not any(r.lower() in corpo() for r in self.remetentes_corpo):
                return None

        return self.destino


@dataclass
class RegraMovimentoPorRemetente(RegraMovimento):
    """
    Atalho para regras onde o destino é determinado pelo remetente.

    Recebe um dict {email_remetente: pasta_destino} e avalia o e-mail
    contra todos os pares de uma vez, incluindo busca no corpo do e-mail
    para capturar mensagens encaminhadas.

    Args:
        mapa:             Dict mapeando e-mail do remetente → pasta de destino.
                          Ex: {"loja2@empresa.com.br": "Caixa de Entrada/Lojas/QC Matriz"}
        buscar_no_corpo:  Se True (padrão), busca os endereços no corpo também,
                          útil para e-mails encaminhados onde o remetente real
                          aparece no texto mas não no campo From.
    """
    mapa:            dict[str, str] = field(default_factory=dict)
    buscar_no_corpo: bool = True

    # destino é ignorado nesta subclasse — cada entrada do mapa tem seu próprio destino
    destino: str = ""

    def destinos_possiveis(self) -> list[str]:
        return list(set(self.mapa.values()))

    def avaliar(self, email) -> Optional[str]:
        try:
            remetente = (email.SenderEmailAddress or "").lower().strip()
        except Exception:
            remetente = ""

        # 1. Remetente direto
        for email_loja, pasta in self.mapa.items():
            if email_loja.lower() == remetente:
                return pasta

        # 2. Busca no corpo (encaminhados)
        if self.buscar_no_corpo:
            try:
                corpo = (email.Body or "").lower()
            except Exception:
                corpo = ""
            for email_loja, pasta in self.mapa.items():
                if email_loja.lower() in corpo:
                    return pasta

        return None


# ── Conector principal ────────────────────────────────────────────────────────

# Nomes alternativos para a caixa de entrada em diferentes idiomas do Outlook
_NOMES_INBOX = frozenset({
    "caixa de entrada", "inbox", "entrada", "posteingang",
    "bandeja de entrada", "boîte de réception",
})


class OutlookConnector:
    """
    Acessa o Outlook via COM e baixa anexos de e-mails conforme o filtro.

    Args:
        pasta_destino: Pasta local onde os anexos serão salvos (ex: "entrada").
                       Criada automaticamente se não existir.
        conta:         Nome da conta do Outlook a usar.
                       None = primeira conta disponível.
    """

    def __init__(self, pasta_destino: str = "entrada", conta: Optional[str] = None):
        self.pasta_destino = Path(pasta_destino)
        self.pasta_destino.mkdir(parents=True, exist_ok=True)
        self._conta = conta
        self._outlook = None   # lazy init
        self._app = None

    # ── Conexão ───────────────────────────────────────────────────────────────

    def _conectar(self):
        if self._outlook is not None:
            return
        win32 = _importar_win32()
        try:
            self._app = win32.Dispatch("Outlook.Application")
            self._outlook = self._app.GetNamespace("MAPI")
            log.info("Conectado ao Outlook via COM.")
        except Exception as e:
            raise RuntimeError(
                f"Não foi possível conectar ao Outlook. "
                f"Verifique se o Outlook está aberto. Detalhe: {e}"
            )

    def _pasta_outlook(self, caminho: str):
        """
        Resolve a pasta do Outlook pelo nome.

        A caixa de entrada é sempre resolvida via GetDefaultFolder(6),
        que é independente do idioma configurado no Outlook (PT, EN, DE…).
        Subpastas são navegadas pelo nome a partir da inbox.

        Suporta o formato "Caixa de Entrada/Subpasta" ou simplesmente "Subpasta"
        quando a pasta raiz for identificada como a inbox.
        """
        self._conectar()

        partes = [p.strip() for p in caminho.split("/") if p.strip()]

        # Determina a pasta raiz
        if partes and partes[0].lower() in _NOMES_INBOX:
            # Usa GetDefaultFolder(6) — robusto, independe de idioma
            pasta_atual = self._outlook.GetDefaultFolder(_OL_FOLDER_INBOX)
            log.debug(f"Inbox resolvida via GetDefaultFolder(6): '{pasta_atual.Name}'")
            partes = partes[1:]  # remove a parte "Caixa de Entrada" do caminho
        else:
            # Pasta fora da inbox: navega a partir da conta
            if self._conta:
                raiz = None
                for acc in self._outlook.Folders:
                    if acc.Name.lower() == self._conta.lower():
                        raiz = acc
                        break
                if raiz is None:
                    raise ValueError(f"Conta '{self._conta}' não encontrada no Outlook.")
            else:
                raiz = self._outlook.Folders.Item(1)
            pasta_atual = raiz

        # Navega pelas subpastas restantes
        for parte in partes:
            encontrado = False
            for sub in pasta_atual.Folders:
                if sub.Name.lower() == parte.lower():
                    pasta_atual = sub
                    encontrado = True
                    break
            if not encontrado:
                disponiveis = [s.Name for s in pasta_atual.Folders]
                raise ValueError(
                    f"Subpasta '{parte}' não encontrada dentro de '{pasta_atual.Name}'. "
                    f"Subpastas disponíveis: {disponiveis}"
                )

        return pasta_atual

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _construir_restrict(self, filtro: FiltroEmail) -> str | None:
        """
        Monta a string de filtro MAPI para Items.Restrict() do Outlook.

        Retorna None quando nenhum Restrict deve ser aplicado — neste caso
        o chamador deve iterar Items diretamente, como a POC original faz.

        Só aplica Restrict para filtro de não-lidos, usando sintaxe MAPI
        simples ([Unread]) que é estável em todas as versões do Outlook.
        Evita sintaxe DASL (@SQL=...) que quebra a iteração em muitas
        configurações de Outlook/Windows.
        """
        if filtro.apenas_nao_lidos:
            return "[Unread] = True"
        # Sem filtro de leitura: não aplica Restrict
        # (iterar Items direto é mais confiável do que qualquer query DASL genérica)
        return None

    def _email_passa_filtro(self, email, filtro: FiltroEmail) -> tuple[bool, str]:
        """
        Verifica se o e-mail passa nos critérios do filtro.
        Retorna (True, "") ou (False, "motivo").
        """
        # Só processa itens de e-mail (ignora reuniões, etc.)
        try:
            classe = email.Class
        except Exception:
            return False, "item não é e-mail"
        if classe != 43:  # 43 = olMail
            return False, "não é e-mail"

        # Não lidos (dupla checagem — o Restrict já filtrou, mas garante)
        if filtro.apenas_nao_lidos and email.UnRead is False:
            return False, "já lido"

        # Data
        try:
            dt_recebido = email.ReceivedTime
            if hasattr(dt_recebido, 'replace'):
                dt_recebido = dt_recebido.replace(tzinfo=None)
        except Exception:
            dt_recebido = None

        if dt_recebido:
            if filtro.dt_inicio and dt_recebido < filtro.dt_inicio:
                return False, "anterior ao período"
            if filtro.dt_fim and dt_recebido > filtro.dt_fim:
                return False, "posterior ao período"

        # Remetente
        if filtro.remetentes:
            try:
                rem = (email.SenderEmailAddress or "").lower()
            except Exception:
                rem = ""
            if not any(r.lower() in rem for r in filtro.remetentes):
                return False, "remetente não autorizado"

        # Palavras no assunto
        if filtro.palavras_assunto:
            try:
                assunto = (email.Subject or "").upper()
            except Exception:
                assunto = ""
            if not any(p.upper() in assunto for p in filtro.palavras_assunto):
                return False, "assunto não bate"

        # Palavras no corpo
        if filtro.palavras_corpo:
            try:
                corpo = (email.Body or "").upper()
            except Exception:
                corpo = ""
            if not any(p.upper() in corpo for p in filtro.palavras_corpo):
                return False, "corpo não bate"

        return True, ""

    def _anexo_passa_filtro(self, anexo, filtro: FiltroEmail) -> tuple[bool, str]:
        """Verifica se o anexo específico deve ser baixado."""
        nome = getattr(anexo, "FileName", "") or ""
        ext  = Path(nome).suffix.lower()

        # Extensão
        exts = filtro.extensoes_norm()
        if exts is not None and ext not in exts:
            return False, f"extensão '{ext}' ignorada"

        # Tamanho
        try:
            tamanho_kb = anexo.Size / 1024
        except Exception:
            tamanho_kb = 0

        if filtro.tamanho_min_kb and tamanho_kb < filtro.tamanho_min_kb:
            return False, f"muito pequeno ({tamanho_kb:.0f} KB)"
        if filtro.tamanho_max_kb and tamanho_kb > filtro.tamanho_max_kb:
            return False, f"muito grande ({tamanho_kb:.0f} KB)"

        return True, ""

    # ── Nome de arquivo único ─────────────────────────────────────────────────

    def _nome_unico(self, nome_original: str) -> Path:
        """Garante que não vai sobrescrever um arquivo já existente."""
        destino = self.pasta_destino / nome_original
        if not destino.exists():
            return destino
        stem = Path(nome_original).stem
        sufx = Path(nome_original).suffix
        i = 1
        while True:
            destino = self.pasta_destino / f"{stem}_{i}{sufx}"
            if not destino.exists():
                return destino
            i += 1

    # ── Download principal ────────────────────────────────────────────────────

    def baixar_anexos(self, filtro: FiltroEmail) -> ResultadoBaixar:
        """
        Varre a pasta do Outlook e baixa os anexos que passarem no filtro.

        Usa Items.Restrict() para pré-filtrar no lado do Outlook (obrigatório
        para que a iteração funcione corretamente via win32com).

        Returns:
            ResultadoBaixar com a lista de arquivos salvos e estatísticas.
        """
        resultado = ResultadoBaixar()

        try:
            pasta = self._pasta_outlook(filtro.pasta_outlook)
        except (ValueError, RuntimeError) as e:
            resultado.erros.append(str(e))
            log.error(str(e))
            return resultado

        try:
            itens = pasta.Items
            filtro_restrict = self._construir_restrict(filtro)
            if filtro_restrict is not None:
                # Só aplica Restrict quando necessário (ex: apenas_nao_lidos)
                # Restrict com query desnecessária quebra a iteração em várias
                # versões do Outlook — iterar Items direto é o comportamento mais robusto
                itens = itens.Restrict(filtro_restrict)
            itens.Sort("[ReceivedTime]", True)
        except Exception as e:
            resultado.erros.append(f"Erro ao listar e-mails: {e}")
            log.error(f"Erro ao listar e-mails: {e}")
            return resultado

        log.info(f"Varrendo '{filtro.pasta_outlook}' (Restrict aplicado).")

        for email in itens:
            try:
                passa, motivo = self._email_passa_filtro(email, filtro)
                if not passa:
                    resultado.ignorados += 1
                    log.debug(f"E-mail ignorado: {motivo}")
                    continue

                try:
                    assunto = email.Subject or "(sem assunto)"
                except Exception:
                    assunto = "(sem assunto)"

                log.debug(f"Processando: '{assunto}'")

                anexos = email.Attachments
                email_teve_anexo_valido = False

                for i in range(1, anexos.Count + 1):
                    anexo = anexos.Item(i)
                    passa_anx, motivo_anx = self._anexo_passa_filtro(anexo, filtro)
                    if not passa_anx:
                        log.debug(f"Anexo ignorado ({anexo.FileName}): {motivo_anx}")
                        continue

                    caminho = self._nome_unico(anexo.FileName)
                    try:
                        anexo.SaveAsFile(str(caminho))
                        resultado.baixados.append(str(caminho))
                        email_teve_anexo_valido = True
                        log.info(f"Baixado: {caminho.name}  ←  '{assunto}'")
                    except Exception as e:
                        msg = f"Erro ao salvar '{anexo.FileName}': {e}"
                        resultado.erros.append(msg)
                        log.error(msg)
                        
                

                if email_teve_anexo_valido:

                    # Marca como lido
                    if filtro.marcar_como_lido:
                        try:
                            email.UnRead = False
                            email.Save()
                        except Exception:
                            pass

                    # Move para outra pasta se configurado
                    if filtro.mover_para:
                        try:
                            pasta_destino = self._pasta_outlook(
                                filtro.mover_para
                            )

                            email.Move(pasta_destino)

                            log.info(
                                f"E-mail movido para '{filtro.mover_para}' ← '{assunto}'"
                            )

                        except Exception as e:
                            msg = (
                                f"Erro ao mover e-mail para "
                                f"'{filtro.mover_para}': {e}"
                            )

                            resultado.erros.append(msg)
                            log.error(msg)

            except Exception as e:
                resultado.erros.append(f"Erro ao processar e-mail: {e}")
                log.error(f"Erro ao processar e-mail: {e}")

        log.info(resultado.resumo())
        return resultado

    # ── Utilitários ───────────────────────────────────────────────────────────

    def listar_pastas(self, raiz: Optional[str] = None) -> list[str]:
        """
        Lista as pastas disponíveis no Outlook.
        Útil para descobrir o nome exato da pasta antes de configurar o filtro.
        """
        self._conectar()

        def _percorrer(pasta, prefixo=""):
            nomes = [prefixo + pasta.Name]
            for sub in pasta.Folders:
                nomes.extend(_percorrer(sub, prefixo + pasta.Name + "/"))
            return nomes

        if raiz:
            try:
                pasta_raiz = self._pasta_outlook(raiz)
                return _percorrer(pasta_raiz)
            except ValueError:
                return []

        # Usa GetDefaultFolder para a inbox como ponto de partida confiável
        inbox = self._outlook.GetDefaultFolder(_OL_FOLDER_INBOX)
        return _percorrer(inbox)

    def contas_disponiveis(self) -> list[str]:
        """Lista as contas configuradas no Outlook."""
        self._conectar()
        return [acc.Name for acc in self._outlook.Folders]

    def mover_emails(
        self,
        regras: list["RegraMovimento"],
        filtro: Optional[FiltroEmail] = None,
    ) -> "ResultadoMover":
        """
        Percorre a pasta configurada no filtro e move cada e-mail para a pasta
        de destino definida pela primeira regra que casar.

        Args:
            regras:  Lista de RegraMovimento, avaliadas em ordem. A primeira que
                     retornar um destino não-None vence.
            filtro:  FiltroEmail com a pasta de origem e critérios opcionais.
                     Se None, usa a Caixa de Entrada sem filtro de data/assunto.

        Returns:
            ResultadoMover com contadores e lista de erros.
        """
        if filtro is None:
            filtro = FiltroEmail(extensoes=None)

        resultado = ResultadoMover()

        try:
            pasta_origem = self._pasta_outlook(filtro.pasta_outlook)
        except (ValueError, RuntimeError) as e:
            resultado.erros.append(str(e))
            log.error(str(e))
            return resultado

        # Resolve as pastas de destino de todas as regras de uma vez
        # para evitar falhar no meio da execução
        pastas_destino: dict[str, object] = {}
        for regra in regras:
            for destino in regra.destinos_possiveis():
                if destino not in pastas_destino:
                    try:
                        pastas_destino[destino] = self._pasta_outlook(destino)
                    except (ValueError, RuntimeError) as e:
                        resultado.erros.append(f"Pasta de destino não encontrada: {destino} — {e}")
                        log.error(f"Pasta de destino não encontrada: {destino} — {e}")
                        return resultado

        try:
            itens = pasta_origem.Items
            filtro_restrict = self._construir_restrict(filtro)
            if filtro_restrict is not None:
                itens = itens.Restrict(filtro_restrict)
            itens.Sort("[ReceivedTime]", True)
        except Exception as e:
            resultado.erros.append(f"Erro ao listar e-mails: {e}")
            log.error(f"Erro ao listar e-mails: {e}")
            return resultado

        # Coleta numa lista antes de iterar para evitar problemas ao mover
        # (mover durante a iteração do COM pode pular ou repetir itens)
        emails_para_processar = list(itens)

        log.info(f"Avaliando {len(emails_para_processar)} e-mail(s) para mover.")

        for email in emails_para_processar:
            try:
                # Verifica filtros básicos (data, remetente, assunto)
                if filtro:
                    passa, motivo = self._email_passa_filtro(email, filtro)
                    if not passa:
                        resultado.ignorados += 1
                        log.debug(f"Ignorado ({motivo}): {email.Subject!r}")
                        continue

                # Avalia regras em ordem — primeira que casar vence
                destino_caminho = None
                for regra in regras:
                    destino_caminho = regra.avaliar(email)
                    if destino_caminho is not None:
                        break

                if destino_caminho is None:
                    resultado.ignorados += 1
                    log.debug(f"Nenhuma regra casou: {email.Subject!r}")
                    continue

                pasta_destino_obj = pastas_destino[destino_caminho]
                assunto = email.Subject or "(sem assunto)"
                email.Move(pasta_destino_obj)
                resultado.movidos.append((assunto, destino_caminho))
                log.info(f"Movido → {destino_caminho!r}: {assunto!r}")

            except Exception as e:
                msg = f"Erro ao processar e-mail: {e}"
                resultado.erros.append(msg)
                log.error(msg)

        log.info(resultado.resumo())
        return resultado