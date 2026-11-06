"""Metadados temporais dos CSVs Lynx."""
import csv
from datetime import datetime
import re
from .codificacao import detectar_codificacao_csv


def ler_inicio_lynx(caminho):
    """Lê a data/hora original do cabeçalho, sem aplicar o ajuste de exibição."""
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
                    etiqueta = re.sub(r"[\W_]+", "", texto).casefold()
                    if etiqueta in ("starttime", "starttimeutc"):
                        valor = linha[indice + 1].strip().replace("T", " ").replace(",", ".")
                        for data in ("%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                            for hora in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
                                try:
                                    return datetime.strptime(valor, data + " " + hora)
                                except ValueError:
                                    continue

    except (OSError, UnicodeError):
        pass

    return None
