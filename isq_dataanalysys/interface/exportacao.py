"""Diálogos de exportação compartilhados pelas telas de medição e resultados."""
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import QFileDialog, QMessageBox
import pyqtgraph as pg
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.exportacao.svg import salvar_svg
from isq_dataanalysys.leitores.metadados import ler_inicio_lynx


class ExportacaoGraficos:
    """Requer grafico, df_sensores e os serviços de uma QMainWindow."""

    def exportar_svg(self):
        if getattr(self, "df_sensores", None) is None:
            QMessageBox.information(
                self,
                "Exportação",
                "Abra um arquivo primeiro."
            )
            return

        # Extensometria: um gráfico.
        # Acelerometria: os três gráficos dos eixos.
        if isinstance(self.grafico, pg.PlotWidget):
            plots = [self.grafico.getPlotItem()]
        else:
            plots = list(self.graficos_eixos.values())

        # Exporta somente as curvas que estão selecionadas.
        selecionadas = [
            [
                curva
                for curva in plot.listDataItems()
                if curva.isVisible()
            ]
            for plot in plots
        ]

        if not any(selecionadas):
            QMessageBox.information(
                self,
                "Exportação",
                "Selecione pelo menos um canal."
            )
            return

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta para salvar o SVG"
        )

        if not pasta:
            return

        nome = (
            f"grafico_{datetime.now():%Y%m%d_%H%M%S_%f}.svg"
        )
        caminho = Path(pasta) / nome

        try:
            salvar_svg(plots, caminho, descricao=getattr(self, "descricao_exportacao", ""), titulo=self.windowTitle())
        except Exception as erro:
            QMessageBox.warning(self, "Falha ao exportar SVG", str(erro))
            return

        self.statusBar().showMessage(f"SVG salvo em: {caminho}")

        QMessageBox.information(self, "Exportação concluída", f"Arquivo salvo em:\n{caminho}")


    def exportar_html(self):
        if getattr(self, "df_sensores", None) is None:
            QMessageBox.information(
                self,
                "Exportação",
                "Abra um arquivo primeiro.",
            )
            return

        # Extensometria: um gráfico.
        # Acelerometria: os três gráficos dos eixos.
        if isinstance(self.grafico, pg.PlotWidget):
            plots = [self.grafico.getPlotItem()]
        else:
            plots = list(self.graficos_eixos.values())

        tem_selecao = any(
            curva.isVisible()
            for plot in plots
            for curva in plot.listDataItems()
        )

        if not tem_selecao:
            QMessageBox.information(
                self,
                "Exportação",
                "Selecione pelo menos um canal.",
            )
            return

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta para salvar o HTML interativo",
        )

        if not pasta:
            return

        nome = f"grafico_{datetime.now():%Y%m%d_%H%M%S_%f}.html"
        caminho = Path(pasta) / nome

        try:
            if hasattr(self, "inicio_exportacao"):
                inicio = self.inicio_exportacao
            else:
                inicio = ler_inicio_lynx(getattr(self, "caminho_atual", None))

            figura = criar_figura_html(
                plots,
                inicio=inicio,
                titulo=self.windowTitle(),
                descricao=getattr(self, "descricao_exportacao", ""),
            )

            figura.write_html(
                str(caminho),
                include_plotlyjs=True,
                full_html=True,
                auto_open=False,
                config={
                    "scrollZoom": True,
                    "displaylogo": False,
                    "responsive": True,
                },
            )

        except Exception as erro:
            QMessageBox.warning(
                self,
                "Falha ao exportar HTML",
                str(erro),
            )
            return

        self.statusBar().showMessage(
            f"HTML salvo em: {caminho}"
        )

        QMessageBox.information(
            self,
            "Exportação concluída",
            f"Arquivo salvo em:\n{caminho}\n\n"
            "Abra esse arquivo no navegador para consultar "
            "os valores passando o mouse sobre as curvas.",
        )
