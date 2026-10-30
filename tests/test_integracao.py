"""Cálculos com solução conhecida e fluxo real de janelas/exportações."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/isq-matplotlib')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from integracao import integrar_relativo
from tela_lynx_acm import TelaLynxAcelerometria
from exportacao_html import criar_figura_html
from test_lynx import ArquivoMixin


class CalculoTests(unittest.TestCase):
    def test_integral_cubica_unidades_e_tendencias(self):
        x = np.linspace(-1, 1, 1001)
        tempo = x + 101
        h = x[1] - x[0]
        k = np.sum(x**4) / np.sum(x**2)
        # Integral trapezoidal exata de x³-k*x: inclui o erro conhecido h²/4.
        esperado = (x**4 - 1) / 4 + (h*h/4 - k/2) * (x*x - 1)
        for grandeza, tendencia, fator in (
            ('aceleracao', 7 + 3*x, 9806.65),
            ('velocidade', 7 + 3*x + 5*x*x, 1),
        ):
            dados = pd.DataFrame({4: x**3 + tendencia, 9: -2*x**3 + tendencia}, index=np.arange(1001)+20)
            original = dados.copy(deep=True)
            resultado = integrar_relativo(tempo, dados, grandeza)
            np.testing.assert_allclose(resultado[4], esperado*fator, atol=1e-9)
            np.testing.assert_allclose(resultado[9], -2*esperado*fator, atol=1e-9)
            self.assertEqual(resultado.iloc[0].tolist(), [0, 0])
            pd.testing.assert_frame_equal(dados, original)
            self.assertEqual(list(resultado), [4, 9])
            self.assertTrue(resultado.index.equals(dados.index))

    def test_tendencias_puras_sao_removidas(self):
        t = np.linspace(0, 2, 101)
        for tipo, valores in [('aceleracao', 3+4*t), ('velocidade', 5+2*t+7*t*t)]:
            np.testing.assert_allclose(integrar_relativo(t, pd.DataFrame({1: valores}), tipo), 0, atol=1e-9)

    def test_entradas_invalidas(self):
        for tempo, valores, tipo in [([0, 1], [1, 2], 'aceleracao'), ([0, 1, 2], [1, 2, 3], 'velocidade'),
                                     ([0, 0, 1], [1, 2, 3], 'aceleracao'),
                                     ([0, 1, 2], [1, np.nan, 3], 'aceleracao'),
                                     ([0, 1, 3], [1, 2, 3], 'aceleracao')]:
            with self.assertRaises(ValueError):
                integrar_relativo(tempo, pd.DataFrame({1: valores}), tipo)


class FluxoTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.addCleanup(patch.stopall)
        self.janelas = []
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            janela.close()
        self.app.processEvents()

    def test_fluxo_temporal_independente_em_fft_e_rms_e_exportacoes(self):
        for modo in ('fft', 'rms'):
            acm = TelaLynxAcelerometria()
            self.janelas.append(acm)
            acm.show()
            self.assertFalse(acm.botao_velocidade.isEnabled())
            acm.importar_caminho(self.arquivo(['g']*6, encoding='cp1252'))
            acm.aplicar_configuracao({'calibracao': 2, 'media_movel': 3})
            getattr(acm, 'botao_'+modo).click()
            acm.checkboxes_eixos[(1, 'Y')].setChecked(False)
            acm.checkboxes_canais[2].setChecked(False)
            original = acm.df_sensores.copy(deep=True)
            curvas = {k: tuple(np.array(v, copy=True) for v in c.getOriginalDataset()) for k, c in acm.curvas_lynx.items()}
            acm.botao_velocidade.click()
            vel = acm.janelas_resultados[-1]
            self.janelas.append(vel)
            self.assertTrue(acm.isVisible())
            self.assertTrue(vel.isVisible())
            self.assertEqual(list(vel.df_sensores), [1, 3])
            pd.testing.assert_frame_equal(vel.df_sensores, integrar_relativo(acm.tempo, original[[1, 3]], 'aceleracao'))
            self.assertFalse(np.shares_memory(acm.tempo, vel.tempo))
            vel.checkboxes_canais[3].setChecked(False)
            vel.botao_deslocamento.click()
            desp = vel.janelas_resultados[-1]
            self.janelas.append(desp)
            self.app.processEvents()
            self.assertTrue(vel.isVisible())
            self.assertTrue(desp.isVisible())
            pd.testing.assert_frame_equal(desp.df_sensores, integrar_relativo(vel.tempo, vel.df_sensores[[1]], 'velocidade'))
            pd.testing.assert_frame_equal(acm.df_sensores, original)
            for k, c in acm.curvas_lynx.items():
                for a, b in zip(c.getOriginalDataset(), curvas[k]):
                    np.testing.assert_array_equal(a, b)
            for janela, unidade in ((acm, 'g' if modo == 'fft' else 'mg'), (vel, 'mm/s'), (desp, 'mm')):
                self.assertEqual(janela.graficos_eixos['X'].getAxis('left').labelUnits, unidade)
                fig = criar_figura_html(list(janela.graficos_eixos.values()))
                if janela is not acm:
                    self.assertEqual(len(fig.data), 1)
                    self.assertIn('início do intervalo', janela.windowTitle())
                with tempfile.TemporaryDirectory() as pasta:
                    with patch.object(QFileDialog, 'getExistingDirectory', return_value=pasta), patch.object(QMessageBox, 'information'):
                        janela.exportar_svg()
                        janela.exportar_html()
                    svg = list(Path(pasta).glob('*.svg'))
                    html = list(Path(pasta).glob('*.html'))
                    self.assertEqual(len(svg), 1)
                    self.assertEqual(len(html), 1)
                    self.assertIn('<svg', svg[0].read_text())
                    self.assertIn('Canal 1', html[0].read_text())
                    if janela is not acm:
                        self.assertNotIn('Canal 3 —', html[0].read_text())
                        self.assertIn(unidade, fig.layout.yaxis.title.text)
            # Resultados continuam independentes após restaurar/reimportar a origem.
            snapshot = vel.df_sensores.copy()
            acm.restaurar_original()
            acm.importar_caminho(self.arquivo(['g']*3))
            pd.testing.assert_frame_equal(vel.df_sensores, snapshot)
            desp.close()
            self.assertTrue(vel.isVisible())
            vel.close()
            self.assertTrue(acm.isVisible())
        self.aviso.assert_not_called()

    def test_sem_canais_nao_abre_janela(self):
        acm = TelaLynxAcelerometria()
        self.janelas.append(acm)
        acm.importar_caminho(self.arquivo(['g']*3))
        acm.checkboxes_canais[1].setChecked(False)
        with patch.object(QMessageBox, 'information'):
            acm.botao_velocidade.click()
        self.assertEqual(acm.janelas_resultados, [])
