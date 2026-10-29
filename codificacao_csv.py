"""Reconhece CSV Unicode e usa Windows-1252 para exportações ANSI."""
import codecs


def detectar_codificacao_csv(caminho):
    with open(caminho, "rb") as arquivo:
        inicio = arquivo.read(4)
        if inicio.startswith(codecs.BOM_UTF8):
            return "utf-8-sig"
        if inicio.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            return "utf-16"

        # Valida o arquivo inteiro em blocos, inclusive sequências UTF-8 que
        # atravessem a fronteira de um bloco. Não substitui caracteres inválidos.
        arquivo.seek(0)
        decodificador = codecs.getincrementaldecoder("utf-8")()
        try:
            while bloco := arquivo.read(65536):
                decodificador.decode(bloco)
            decodificador.decode(b"", final=True)
        except UnicodeDecodeError:
            return "cp1252"
        return "utf-8"
