"""Deslocamentos em mm: leitura de CSV misto, tratamentos, janela e exportações."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/isq-matplotlib")

from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from plotly.graph_objects import Figure as FiguraHtml
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QInputDialog

from tests.apoio import ArquivoMixin
from isq_dataanalysys import __version__
from isq_dataanalysys.leitores.regua import ler_lynx_regua
from isq_dataanalysys.leitores.lynx import LinhaFinalIncompleta
from isq_dataanalysys.interface.inicial import TelaInicial
from isq_dataanalysys.interface.regua import TelaLynxReguaPotenciometrica


def canal_16(linhas):
    linhas[2][16] = "1,06E+02"
    linhas[3][16] = "-1,95E+02"
    for linha in linhas[5:]:
        linha[16] = "-7,11E+00"


class LeituraReguaTests(ArquivoMixin, unittest.TestCase):
    def test_canal_16_da_imagem_preserva_mm_negativos_e_arquivo(self):
        caminho = self.arquivo(["g"] * 6 + ["µm/m"] * 7 + ["MPa"] * 2 + ["mm"],
                               nomes=[f"Channel {n}" for n in range(1, 17)], alterar=canal_16)
        original = caminho.read_bytes()
        tempo, dados, mapa, info = ler_lynx_regua(caminho)
        self.assertEqual(list(dados), [16])
        self.assertEqual(mapa, {16: "Channel 16"})
        self.assertEqual(info["unidades"], {16: "mm"})
        self.assertEqual(len(info["ignorados"]), 15)
        np.testing.assert_array_equal(dados[16], np.full(1000, -7.11))
        self.assertAlmostEqual(info["fs"], 1000)
        self.assertIn("constante", info["qualidade"][16])
        self.assertEqual(len(tempo), len(dados))
        self.assertEqual(caminho.read_bytes(), original)

    def test_unidades_e_nomes_repetidos_em_posicoes_arbitrarias(self):
        _, dados, mapa, info = ler_lynx_regua(self.arquivo(
            ["mm/m", " MM ", "g", "µm/m", "m m", "MPa", "mm"],
            ["Deformação", "Régua", "Aceleração", "Extensão", "Régua", "Tensão", ""],
        ))
        self.assertEqual(list(dados), [2, 5, 7])
        self.assertEqual(mapa, {2: "Régua", 5: "Régua", 7: "Canal 7 (sem nome)"})
        self.assertEqual(info["unidades"], {2: "mm", 5: "mm", 7: "mm"})

    def test_codificacoes_e_qualquer_quantidade_de_canais(self):
        for encoding in ("cp1252", "utf-8", "utf-8-sig", "utf-16"):
            for quantidade in (1, 2, 17):
                with self.subTest(encoding=encoding, quantidade=quantidade):
                    caminho = self.arquivo(["mm"] * quantidade, ["Régua posição"] * quantidade, encoding=encoding)
                    original = caminho.read_bytes()
                    _, dados, mapa, _ = ler_lynx_regua(caminho)
                    self.assertEqual(len(dados.columns), quantidade)
                    self.assertEqual(mapa[quantidade], "Régua posição")
                    self.assertEqual(caminho.read_bytes(), original)

    def test_sem_mm_nao_confunde_deformacao_com_deslocamento(self):
        with self.assertRaisesRegex(ValueError, "Nenhum canal compatível"):
            ler_lynx_regua(self.arquivo(["g", "MPa", "µm/m", "mm/m", "V"]))

    def test_dados_invalidos_em_outra_medicao_nao_impedem_regua(self):
        def alterar(linhas):
            linhas[8][1] = "inválido"
            linhas[2][1] = "sem limite"
        _, dados, _, _ = ler_lynx_regua(self.arquivo(["g", "mm"], alterar=alterar))
        self.assertEqual(list(dados), [2])
        for valor in ("", "inválido", "inf"):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                ler_lynx_regua(self.arquivo(["mm"], alterar=lambda l: l[8].__setitem__(1, valor)))

    def test_ultima_linha_exige_confirmacao_e_preserva_csv(self):
        caminho = self.arquivo(["g", "mm"], alterar=lambda l: l[-1].__setitem__(2, ""))
        original = caminho.read_bytes()
        with self.assertRaises(LinhaFinalIncompleta):
            ler_lynx_regua(caminho)
        tempo, dados, _, info = ler_lynx_regua(caminho, ignorar_ultima_incompleta=True)
        self.assertEqual(len(tempo), 999)
        self.assertEqual(len(dados), 999)
        self.assertEqual(info["linhas_ignoradas"], 1)
        self.assertEqual(caminho.read_bytes(), original)


class InterfaceReguaTests(ArquivoMixin, unittest.TestCase):
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
        self.informacao = patch.object(QMessageBox, "information").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            janela.close()
            janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def janela(self, caminho=None):
        janela = TelaLynxReguaPotenciometrica()
        self.janelas.append(janela)
        janela.show()
        if caminho is not None:
            self.assertTrue(janela.importar_caminho(caminho))
        self.app.processEvents()
        return janela

    def test_menu_lynx_abre_janelas_independentes_e_reutiliza_a_regua(self):
        inicial = TelaInicial()
        self.janelas.append(inicial)
        inicial.show()
        acao = next(a for a in inicial.botao_lynx.menu().actions() if a.text() == "Régua potenciométrica")
        acao.trigger()
        regua = inicial.janela_regua
        self.janelas.append(regua)
        self.assertIsInstance(regua, TelaLynxReguaPotenciometrica)
        self.assertTrue(regua.isVisible())
        self.assertIn(__version__, regua.windowTitle())
        regua.importar_caminho(self.arquivo(["mm"]))
        original = regua.df_sensores.copy(deep=True)
        regua.close()
        acao.trigger()
        self.assertIs(inicial.janela_regua, regua)
        self.assertTrue(regua.isVisible())
        pd.testing.assert_frame_equal(regua.df_sensores, original)
        inicial.abrir_acelerometria()
        inicial.abrir_extensometria()
        self.janelas.extend([inicial.janela_acelerometria, inicial.janela_extensometria])
        self.assertEqual(len({id(inicial.janela_acelerometria), id(inicial.janela_extensometria), id(regua)}), 3)

    def test_canal_16_plota_mm_e_avisa_as_outras_unidades(self):
        caminho = self.arquivo(["g"] * 6 + ["µm/m"] * 7 + ["MPa"] * 2 + ["mm"], alterar=canal_16)
        janela = self.janela(caminho)
        self.assertEqual(list(janela.curvas_regua), [16])
        self.assertEqual(list(janela.checkboxes_canais), [16])
        self.assertEqual(janela.grafico.getAxis("left").labelUnits, "mm")
        np.testing.assert_array_equal(janela.curvas_regua[16].getOriginalDataset()[1], np.full(1000, -7.11))
        self.assertIn("Canal 7", self.aviso.call_args.args[2])
        self.assertIn("Régua potenciométrica", self.aviso.call_args.args[2])
        self.assertIn("constante", janela.rotulo_arquivo.text())
        self.assertEqual(janela.grafico.getAxis("bottom").tickStrings([0], 1, 1), ["28/10/2026 09:00:00"])

    def test_tratamentos_pelos_botoes_e_restauracao_preservam_original(self):
        def alterar(linhas):
            for linha in linhas[5:]:
                linha[1] = "-7,11"
            linhas[505][1] = "42,89"
        caminho = self.arquivo(["mm"], alterar=alterar)
        janela = self.janela(caminho)
        original = janela.df_original.copy(deep=True)
        arquivo = caminho.read_bytes()
        janela.controle_calibração.campo.setValue(2)
        janela.controle_calibração.botao.click()
        pd.testing.assert_frame_equal(janela.df_sensores, original * 2)
        janela.controle_offset.campo.setValue(10)
        janela.controle_offset.botao.click()
        np.testing.assert_allclose(janela.df_sensores[1].iloc[:10], 0, atol=1e-12)
        self.assertAlmostEqual(janela.df_sensores[1].iloc[500], 100)
        janela.controle_outliers.campo.setValue(3)
        janela.controle_outliers.botao.click()
        np.testing.assert_allclose(janela.df_sensores[1], 0, atol=1e-12)
        self.assertEqual(janela.info_processamento["substituicoes"], {1: 1})
        for controle, valor in ((janela.controle_passa_alta, 5), (janela.controle_passa_baixa, 100),
                                (janela.controle_media_movel, 5)):
            controle.campo.setValue(valor)
            controle.botao.click()
        np.testing.assert_allclose(janela.df_sensores[1], 0, atol=1e-10)
        self.assertEqual(janela.grafico.getAxis("left").labelUnits, "mm")
        self.assertEqual(janela.df_sensores.shape, original.shape)
        self.assertEqual(janela.config_filtros["passa_alta"], 5)
        self.assertEqual(janela.config_filtros["passa_baixa"], 100)
        self.assertEqual(janela.config_filtros["media_movel"], 5)
        janela.botao_restaurar.click()
        self.assertEqual(janela.config_filtros, {})
        pd.testing.assert_frame_equal(janela.df_sensores, original)
        self.assertEqual(caminho.read_bytes(), arquivo)
        self.aviso.assert_not_called()

    def test_parametro_invalido_e_arquivo_sem_mm_preservam_estado(self):
        janela = self.janela(self.arquivo(["mm"]))
        original = janela.df_sensores.copy(deep=True)
        caminho, inicio = janela.caminho_atual, janela.inicio_arquivo
        janela.controle_passa_baixa.campo.setValue(500)
        janela.controle_passa_baixa.botao.click()
        self.aviso.assert_called_once()
        self.assertEqual(janela.config_filtros, {})
        with self.assertRaisesRegex(ValueError, "Nenhum canal compatível"):
            janela.importar_caminho(self.arquivo(["mm/m", "g"]))
        self.assertEqual(janela.caminho_atual, caminho)
        self.assertEqual(janela.inicio_arquivo, inicio)
        pd.testing.assert_frame_equal(janela.df_sensores, original)

    def test_reimportacao_limpa_curvas_filtros_e_canais_antigos(self):
        janela = self.janela(self.arquivo(["mm", "MPa", "mm"]))
        janela.aplicar_configuracao({"calibracao": 2})
        janela.checkboxes_canais[3].setChecked(False)
        janela.importar_caminho(self.arquivo(["g", "mm"]))
        self.assertEqual(list(janela.curvas_regua), [2])
        self.assertEqual(list(janela.checkboxes_canais), [2])
        self.assertTrue(janela.curvas_regua[2].isVisible())
        self.assertEqual(janela.config_filtros, {})
        pd.testing.assert_frame_equal(janela.df_sensores, janela.df_original)

    def test_cancelar_e_confirmar_ultima_linha_na_interface(self):
        janela = self.janela(self.arquivo(["mm"]))
        anterior = janela.caminho_atual
        incompleto = self.arquivo(["mm"], alterar=lambda l: l[-1].__setitem__(1, ""))
        original = incompleto.read_bytes()
        with patch.object(QFileDialog, "getOpenFileName", return_value=(str(incompleto), "")):
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
                janela.abrir.click()
                self.assertEqual(janela.caminho_atual, anterior)
            with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                janela.abrir.click()
                self.assertEqual(len(janela.tempo), 999)
        self.assertEqual(incompleto.read_bytes(), original)

    def test_selecao_escala_horario_e_exportacoes_reais_em_mm(self):
        janela = self.janela(self.arquivo(["mm", "mm"]))
        janela.checkboxes_canais[2].setChecked(False)
        janela.controle_calibração.campo.setValue(2)
        janela.controle_calibração.botao.click()
        for campo, valor in ((janela.campo_y_min, -10), (janela.campo_y_max, 10),
                             (janela.campo_tempo_inicio, .2), (janela.campo_tempo_fim, .8)):
            campo.setValue(valor)
        janela.botao_aplicar_visualizacao.click()
        np.testing.assert_allclose(janela.grafico.viewRange(), [[.2, .8], [-10, 10]])
        fonte = janela.df_sensores.copy(deep=True)
        janela.caminho_atual.unlink()
        svg_original, html_original = Figure.savefig, FiguraHtml.write_html
        chamadas = []
        def verificar_svg(figura, *args, **kwargs):
            eixo = figura.axes[0]
            self.assertIn("mm", eixo.get_ylabel())
            self.assertEqual(len(eixo.lines), 1)
            self.assertIn("Canal 1", eixo.lines[0].get_label())
            np.testing.assert_array_equal(eixo.lines[0].get_ydata(), fonte[1])
            self.assertEqual(str(eixo.lines[0].get_xdata()[0]), "2026-10-28T09:00:00.000000")
            np.testing.assert_allclose(eixo.get_ylim(), [-10, 10])
            np.testing.assert_allclose(eixo.get_xlim(), mdates.date2num([
                datetime(2026, 10, 28, 9, 0, 0, 200000), datetime(2026, 10, 28, 9, 0, 0, 800000)]), rtol=0, atol=1e-10)
            chamadas.append("svg")
            return svg_original(figura, *args, **kwargs)
        def verificar_html(figura, *args, **kwargs):
            self.assertEqual(len(figura.data), 1)
            self.assertIn("mm", figura.layout.yaxis.title.text)
            self.assertEqual(figura.data[0].x[0], "2026-10-28T09:00:00.000000")
            self.assertEqual(figura.layout.xaxis.range[0], "2026-10-28T09:00:00.200000")
            np.testing.assert_array_equal(figura.data[0].y, fonte[1])
            chamadas.append("html")
            return html_original(figura, *args, **kwargs)
        with patch.object(QFileDialog, "getExistingDirectory", return_value=self.tmp.name), \
                patch.object(Figure, "savefig", verificar_svg), patch.object(FiguraHtml, "write_html", verificar_html):
            janela.exportar_svg()
            janela.exportar_html()
        self.assertEqual(chamadas, ["svg", "html"])
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.svg"))), 1)
        html = list(Path(self.tmp.name).glob("*.html"))
        self.assertEqual(len(html), 1)
        self.assertNotIn("Canal 2 —", html[0].read_text())
        janela.checkboxes_canais[1].setChecked(False)
        with patch.object(QFileDialog, "getExistingDirectory") as escolher:
            janela.exportar_html()
            janela.exportar_svg()
            escolher.assert_not_called()
        self.aviso.assert_not_called()

    def test_escala_invalida_e_referencia_manual_na_regua(self):
        janela = self.janela(self.arquivo(["mm"], alterar=lambda l: l[1].__setitem__(-1, "sem data")))
        original = janela.df_sensores.copy(deep=True)
        antes = janela.grafico.viewRange()
        janela.campo_y_min.setValue(5)
        janela.campo_y_max.setValue(1)
        self.assertFalse(janela.aplicar_visualizacao())
        np.testing.assert_allclose(janela.grafico.viewRange(), antes)
        with patch.object(QInputDialog, "getText", return_value=("27/10/2026 14:45", True)):
            janela.painel_referencia.botao_definir.click()
        self.assertEqual(janela.grafico.getAxis("bottom").tickStrings([0], 1, 1), ["27/10/2026 11:45:00"])
        pd.testing.assert_frame_equal(janela.df_sensores, original)


if __name__ == "__main__":
    unittest.main()
