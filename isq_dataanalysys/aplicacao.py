"""Inicialização da aplicação e identificação da instalação em uso."""
import argparse
from pathlib import Path
import sys

from . import __version__

# QApplication precisa sobreviver aos objetos gráficos, inclusive na finalização
# do pyqtgraph. Mantém o mesmo tempo de vida que tinha no iniciador original.
_aplicacao_qt = None


def diagnostico():
    return (
        f'ISQ DataAnalysys v{__version__}\n'
        f'Pacote: {Path(__file__).resolve().parent}\n'
        f'Python: {sys.executable}'
    )


def main(argv=None):
    global _aplicacao_qt
    parser = argparse.ArgumentParser(description='Análise de medições Lynx')
    parser.add_argument('--diagnostico', action='store_true', help='Mostra a versão e o código em uso, sem abrir janelas')
    args = parser.parse_args(argv)
    if args.diagnostico:
        print(diagnostico())
        return 0

    # Importar o pacote ou pedir o diagnóstico não inicializa Qt nem abre janelas.
    from PySide6.QtWidgets import QApplication
    from .interface.inicial import TelaInicial

    _aplicacao_qt = QApplication.instance() or QApplication([sys.argv[0]])
    app = _aplicacao_qt
    app.setApplicationName('ISQ DataAnalysys')
    app.setApplicationVersion(__version__)
    janela = TelaInicial()
    janela.show()

    return app.exec()
