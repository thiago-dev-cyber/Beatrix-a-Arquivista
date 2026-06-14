from abc import ABC, abstractmethod


class Extrator(ABC):
    """
    Classe base para extratores de documentos fiscais.

    A Beatrix utiliza essa classe como contrato para todos os tipos de
    documentos suportados (NF-e, NFC-e, CT-e, etc).

    O fluxo padrão é:

        1. Receber texto bruto extraído de um PDF
        2. Cada extrator calcula um score de compatibilidade
        3. O extrator com maior score é selecionado
        4. O método `extrair()` retorna os dados estruturados
        5. Os dados são enviados para o manifesto (indexação)

    ------------------------------------------------------------------------

    Responsabilidades da classe base:
        - Definir o fluxo padrão de extração (Template Method)
        - Padronizar o formato de saída
        - Forçar implementação dos métodos específicos

    Responsabilidades das subclasses:
        - Calcular score de compatibilidade com o texto
        - Extrair campos específicos do documento
        - Definir regras de parsing por tipo de nota

    ------------------------------------------------------------------------

    Atributos esperados no retorno de `extrair()`:

        {
            "tipo": str,     # Tipo do documento (NFCE, NFE, CTE...)
            "numero": str,   # Número da nota fiscal
            "chave": str,    # Chave de acesso (44 dígitos)
            "emissor": str   # Nome do emitente
        }
    """

    @property
    @abstractmethod
    def tipo(self) -> str:
        """
        Identificador fixo do tipo de documento.

        Exemplo:
            "NFCE", "NFE", "CTE"
        """
        pass


    @abstractmethod
    def score(self, texto: str) -> float:
        """
        Calcula o nível de confiança de que este extrator
        é o mais adequado para o texto fornecido.

        Retorna:
            float entre 0.0 e 1.0

        Interpretação:
            0.0 → não é esse tipo de documento
            1.0 → certeza absoluta

        O sistema usa esse valor para selecionar o melhor extrator
        entre todos os disponíveis.
        """
        pass


    def extrair(self, texto: str) -> dict:
        """
        Executa o processo completo de extração de dados estruturados.

        Este método segue o padrão Template Method:
        a estrutura é fixa, mas os detalhes são implementados pelas subclasses.

        Retorna:
            dict com os campos padronizados do documento
        """
        return {
            "tipo": self.tipo,
            "numero": self.extrair_numero(texto),
            "chave": self.extrair_chave(texto),
            "emissor": self.extrair_emissor(texto),
        }


    @abstractmethod
    def extrair_numero(self, texto: str) -> str:
        """
        Extrai o número da nota fiscal a partir do texto bruto.
        """
        pass


    @abstractmethod
    def extrair_chave(self, texto: str) -> str:
        """
        Extrai a chave de acesso (44 dígitos) do documento.
        """
        pass


    @abstractmethod
    def extrair_emissor(self, texto: str) -> str:
        """
        Extrai o nome do emissor (empresa responsável pela emissão).
        """
        pass