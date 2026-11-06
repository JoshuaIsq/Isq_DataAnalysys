"""Hora do CSV menos três horas na tela, no SVG e no HTML, sem alterar cálculos."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/isq-matplotlib")

from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from plotly.graph_objects import Figure as FiguraHtml
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from tests.apoio import ArquivoMixin
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.extensometria import TelaLynxExtensometria
from isq_dataanalysys.interface.eixo_temporal import EixoDataHora
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.leitores.metadados import ler_inicio_lynx
from isq_dataanalysys.processamento.tempo import datas_locais, ROTULO_DATA_HORA
from isq_dataanalysys.processamento.integracao import integrar_relativo


class MetadadosTests(ArquivoMixin, unittest.TestCase):
    def test_formatos_do_csv_incluindo_exemplo_da_imagem(self):
        casos = [
            ("28/10/2026 15:55", datetime(2026, 10, 28, 15, 55)),
            ("2026/10/28 15:55:12.345678", datetime(2026, 10, 28, 15, 55, 12, 345678)),
            ("28/10/2026 15:55:12,345", datetime(2026, 10, 28, 15, 55, 12, 345000)),
            ("2026-10-28T15:55:12", datetime(2026, 10, 28, 15, 55, 12)),
            ("28-10-2026 15:55:12", datetime(2026, 10, 28, 15, 55, 12)),
        ]
        for valor, esperado in casos:
            for etiqueta in ("StartTime UTC:", " StartTime: ", "start_time utc"):
                with self.subTest(valor=valor, etiqueta=etiqueta):
                    def alterar(linhas):
                        linhas[1][-2:] = [etiqueta, valor]
                    caminho = self.arquivo(["MPa"], alterar=alterar)
                    original = caminho.read_bytes()
                    self.assertEqual(ler_inicio_lynx(caminho), esperado)
                    self.assertEqual(caminho.read_bytes(), original)

    def test_metadata_em_codificacoes_windows_e_unicode(self):
        for encoding in ("cp1252", "utf-8-sig", "utf-16"):
            with self.subTest(encoding=encoding):
                caminho = self.arquivo(["µm/m"], encoding=encoding,
                                       alterar=lambda linhas: linhas[1].__setitem__(-1, "28/10/2026 15:55"))
                self.assertEqual(ler_inicio_lynx(caminho), datetime(2026, 10, 28, 15, 55))

    def test_virada_do_dia_ano_e_precisao_de_200_hz(self):
        segundos = np.array([0, .005, 1, 3 * 3600])
        copia = segundos.copy()
        esperado = np.array(["2025-12-31T22:00:00", "2025-12-31T22:00:00.005",
                             "2025-12-31T22:00:01", "2026-01-01T01:00:00"], dtype="datetime64[us]")
        np.testing.assert_array_equal(datas_locais(datetime(2026, 1, 1, 1), segundos), esperado)
        np.testing.assert_array_equal(segundos, copia)

    def test_conversao_independe_do_fuso_do_computador_e_da_estacao(self):
        codigo = (
            "from datetime import datetime; from isq_dataanalysys.processamento.tempo import datas_locais; "
            "print(datas_locais(datetime(2026,7,1,15,55),[0])[0])"
        )
        for fuso in ("UTC", "America/Sao_Paulo", "Europe/London", "Pacific/Auckland"):
            resultado = subprocess.run([sys.executable, "-c", codigo], env=dict(os.environ, TZ=fuso),
                                       capture_output=True, text=True, check=True)
            self.assertEqual(resultado.stdout.strip(), "2026-07-01T12:55:00.000000")

    def test_metadata_ausente_ou_invalida_nao_inventa_horario(self):
        for valor in ("", "31/02/2026 15:55", "sem data"):
            caminho = self.arquivo(["MPa"], alterar=lambda linhas: linhas[1].__setitem__(-1, valor))
            self.assertIsNone(ler_inicio_lynx(caminho))
        self.assertIsNone(ler_inicio_lynx(None))
        self.assertIsNone(ler_inicio_lynx(Path(self.tmp.name) / "ausente.csv"))


class InterfaceDataHoraTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas = []
        self.erros_qt = []
        self.addCleanup(lambda: self.assertEqual(self.erros_qt, []))
        patch("sys.excepthook", lambda tipo, erro, tb: self.erros_qt.append(str(erro))).start()
        self.aviso = patch.object(QMessageBox, "warning").start()
        patch.object(QMessageBox, "information").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            janela.close()
            janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def abrir(self, classe, caminho):
        janela = classe()
        self.janelas.append(janela)
        janela.show()
        self.assertTrue(janela.importar_caminho(caminho))
        self.app.processEvents()
        return janela

    def verificar_eixo(self, plot, esperado="28/10/2026 12:55:00"):
        eixo = plot.getAxis("bottom")
        self.assertIsInstance(eixo, EixoDataHora)
        self.assertEqual(eixo.labelText, ROTULO_DATA_HORA)
        self.assertEqual(eixo.tickStrings([0], 1, 1), [esperado])
        self.assertEqual(eixo.tickStrings([.005], 1, .005), [esperado + ".005"])

    def test_todas_as_telas_usam_a_mesma_referencia_sem_mudar_calculos(self):
        caminho = self.arquivo(["g"] * 3 + ["MPa"], alterar=lambda linhas: linhas[1].__setitem__(-1, "28/10/2026 15:55"))
        acm = self.abrir(TelaLynxAcelerometria, caminho)
        ext = self.abrir(TelaLynxExtensometria, caminho)
        tempo, original = acm.tempo.copy(), acm.df_original.copy(deep=True)
        acm.botao_velocidade.click()
        vel = acm.janelas_resultados[-1]
        self.janelas.append(vel)
        vel.botao_deslocamento.click()
        desp = vel.janelas_resultados[-1]
        self.janelas.append(desp)
        for janela in (acm, ext, vel, desp):
            for plot in janela.plots_para_exportar():
                self.verificar_eixo(plot)
            np.testing.assert_array_equal(janela.tempo, tempo)
        pd.testing.assert_frame_equal(acm.df_original, original)
        pd.testing.assert_frame_equal(vel.df_sensores, integrar_relativo(tempo, original, "aceleracao"))
        pd.testing.assert_frame_equal(desp.df_sensores, integrar_relativo(tempo, vel.df_sensores, "velocidade"))
        self.assertTrue((vel.df_sensores.iloc[0] == 0).all())
        self.assertTrue((desp.df_sensores.iloc[0] == 0).all())

    def test_exports_reais_svg_html_mantem_hora_local_zoom_e_snapshot(self):
        caminho = self.arquivo(["g"] * 3 + ["MPa"], alterar=lambda linhas: linhas[1].__setitem__(-1, "28/10/2026 15:55"))
        acm = self.abrir(TelaLynxAcelerometria, caminho)
        ext = self.abrir(TelaLynxExtensometria, caminho)
        vel = acm.gerar_velocidade()
        desp = vel.gerar_deslocamento()
        self.janelas.extend([vel, desp])
        caminho.unlink()  # A referência pertence à janela, não a uma releitura na exportação.
        for janela in (acm, ext, vel, desp):
            self.aviso.reset_mock()
            plots = janela.plots_para_exportar()
            for plot in plots:
                plot.setXRange(.2, .8, padding=0)
            self.app.processEvents()
            faixas = [plot.viewRange()[0] for plot in plots]
            salvar_svg, salvar_html = Figure.savefig, FiguraHtml.write_html
            chamadas = []

            def verificar_svg(figura, *args, **kwargs):
                for eixo, faixa in zip(figura.axes, faixas):
                    self.assertEqual(eixo.get_xlabel(), ROTULO_DATA_HORA)
                    esperado = mdates.date2num([datetime(2026, 10, 28, 12, 55) + timedelta(seconds=t) for t in faixa])
                    np.testing.assert_allclose(eixo.get_xlim(), esperado, rtol=0, atol=1e-10)
                    for linha in eixo.lines:
                        self.assertEqual(str(linha.get_xdata()[0]), "2026-10-28T12:55:00.000000")
                        self.assertEqual(len(linha.get_xdata()), 1000)
                chamadas.append("svg")
                return salvar_svg(figura, *args, **kwargs)

            def verificar_html(figura, *args, **kwargs):
                self.assertEqual(figura.layout.xaxis.type, "date")
                self.assertEqual(figura.layout.xaxis.title.text, ROTULO_DATA_HORA)
                self.assertEqual(list(figura.layout.xaxis.range), [
                    (datetime(2026, 10, 28, 12, 55) + timedelta(seconds=t)).isoformat(timespec="microseconds")
                    for t in faixas[0]])
                for curva in figura.data:
                    self.assertEqual(curva.x[0], "2026-10-28T12:55:00.000000")
                    self.assertEqual(len(curva.x), 1000)
                    np.testing.assert_array_equal(curva.customdata, janela.tempo)
                    self.assertIn(ROTULO_DATA_HORA, curva.hovertemplate)
                chamadas.append("html")
                return salvar_html(figura, *args, **kwargs)

            with patch.object(QFileDialog, "getExistingDirectory", return_value=self.tmp.name), \
                    patch.object(Figure, "savefig", verificar_svg), patch.object(FiguraHtml, "write_html", verificar_html):
                janela.exportar_svg()
                janela.exportar_html()
            self.aviso.assert_not_called()
            self.assertEqual(chamadas, ["svg", "html"])
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.svg"))), 4)
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.html"))), 4)

    def test_fft_permanece_em_hz_e_rms_retorna_a_data_local(self):
        acm = self.abrir(TelaLynxAcelerometria, self.arquivo(["g"] * 3))
        original = acm.df_sensores.copy(deep=True)
        acm.botao_fft.click()
        figura = criar_figura_html(acm.plots_para_exportar(), inicio=acm.inicio_arquivo)
        self.assertEqual(figura.layout.xaxis.type, "linear")
        self.assertEqual(figura.layout.xaxis.title.text, "Frequência (Hz)")
        self.assertEqual(figura.data[0].x[0], 0)
        self.assertIsNone(figura.data[0].customdata)
        acm.botao_rms.click()
        figura = criar_figura_html(acm.plots_para_exportar())
        self.assertEqual(figura.layout.xaxis.type, "date")
        self.assertEqual(figura.data[0].x[0], "2026-10-28T09:00:00.249500")
        pd.testing.assert_frame_equal(acm.df_sensores, original)

    def test_reimportar_sem_data_volta_a_segundos_e_dias_mudam_corretamente(self):
        caminho = self.arquivo(["g"] * 3, alterar=lambda linhas: linhas[1].__setitem__(-1, "01/01/2026 01:00:00"))
        acm = self.abrir(TelaLynxAcelerometria, caminho)
        self.verificar_eixo(acm.graficos_eixos["X"], "31/12/2025 22:00:00")
        outro = self.arquivo(["g"] * 3, alterar=lambda linhas: linhas[1].__setitem__(-1, ""))
        self.assertTrue(acm.importar_caminho(outro))
        for plot in acm.plots_para_exportar():
            self.assertEqual(plot.getAxis("bottom").labelUnits, "s")
            self.assertIsNone(plot.getAxis("bottom").inicio)
        figura = criar_figura_html(acm.plots_para_exportar())
        self.assertEqual(figura.layout.xaxis.type, "linear")
        np.testing.assert_array_equal(figura.data[0].x, acm.tempo)

    def test_svg_sem_metadata_e_fft_preservam_coordenadas_numericas(self):
        from isq_dataanalysys.exportacao.svg import salvar_svg
        caminho = self.arquivo(["g"] * 3, alterar=lambda linhas: linhas[1].__setitem__(-1, ""))
        acm = self.abrir(TelaLynxAcelerometria, caminho)
        salvar = Figure.savefig
        for modo in ("tempo", "fft"):
            if modo == "fft":
                acm.importar_caminho(self.arquivo(["g"] * 3))
                acm.botao_fft.click()
            plots = acm.plots_para_exportar()
            def verificar(figura, *args, **kwargs):
                for eixo, plot in zip(figura.axes, plots):
                    x, y = plot.listDataItems()[0].getOriginalDataset()
                    np.testing.assert_array_equal(eixo.lines[0].get_xdata(), x)
                    np.testing.assert_array_equal(eixo.lines[0].get_ydata(), y)
                    np.testing.assert_allclose(eixo.get_xlim(), plot.viewRange()[0])
                    self.assertEqual(eixo.get_xlabel(), "Frequência (Hz)" if modo == "fft" else "Tempo (s)")
                return salvar(figura, *args, **kwargs)
            with patch.object(Figure, "savefig", verificar):
                salvar_svg(plots, Path(self.tmp.name) / (modo + ".svg"), inicio=acm.inicio_arquivo)


if __name__ == "__main__":
    unittest.main()
