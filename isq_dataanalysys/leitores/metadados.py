"""Metadados temporais dos CSVs Lynx."""
import csv
from datetime import datetime
from .codificacao import detectar_codificacao_csv


def ler_inicio_lynx(caminho):
    """Lê o início da gravação em UTC, quando disponível."""
    if not caminho:
        return None

    try:
        with open(
            caminho,
            encoding=detectar_codificacao_csv(caminho),
        ) as arquivo:
            leitor = csv.reader(arquivo, delimiter=";")

            for _ in range(5):
                linha = next(leitor, [])

                for indice, texto in enumerate(linha[:-1]):
                    if "starttime utc" in texto.lower():
                        valor = linha[indice + 1].strip()

                        for formato in (
                            "%Y/%m/%d %H:%M:%S",
                            "%Y/%m/%d %H:%M:%S.%f",
                        ):
                            try:
                                return datetime.strptime(valor, formato)
                            except ValueError:
                                continue

    except (OSError, UnicodeError):
        pass

    return None
