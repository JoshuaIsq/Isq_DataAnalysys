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
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from isq_dataanalysys.processamento.integracao import integrar_relativo
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys import __version__ as VERSAO
from tests.apoio import ArquivoMixin


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

    def test_senoide_de_aceleracao_ate_deslocamento_com_solucao_discreta(self):
        # Soluções fechadas dos trapézios e das projeções polinomiais discretas.
        # Verifica a cadeia completa sem usar o próprio integrador como referência.
        x = np.linspace(-1, 1, 4001)
        t = x + 51
        h = x[1] - x[0]
        w = 2*np.pi*10
        amplitude_g = .02
        aceleracao = pd.DataFrame({7: amplitude_g*np.cos(w*x) + 3 + .4*x})
        c = h / (2*np.tan(w*h/2))
        v_esperada = amplitude_g*9806.65*(c*(np.sin(w*x) - np.sin(w*x[0])) - (x-x[0])/len(x))
        v = integrar_relativo(t, aceleracao, 'aceleracao')
        np.testing.assert_allclose(v[7], v_esperada, atol=1e-9)
        k = np.sum(x*np.sin(w*x)) / np.sum(x*x)
        d_esperado = amplitude_g*9806.65*c*(-c*(np.cos(w*x)-np.cos(w*x[0])) - k*(x*x-x[0]**2)/2)
        d = integrar_relativo(t, v, 'velocidade')
        np.testing.assert_allclose(d[7], d_esperado, atol=1e-9)
        self.assertEqual(v.iloc[0, 0], 0)
        self.assertEqual(d.iloc[0, 0], 0)

    def test_erro_numerico_e_grandeza_desconhecida(self):
        dados = pd.DataFrame({1: [1., 2., 4., 8.]})
        with self.assertRaises(ValueError):
            integrar_relativo([0, 1, 2, 3], dados, 'fft')
        with patch('isq_dataanalysys.processamento.integracao.np.linalg.lstsq', side_effect=np.linalg.LinAlgError):
            with self.assertRaisesRegex(ValueError, 'Não foi possível integrar'):
                integrar_relativo([0, 1, 2, 3], dados, 'aceleracao')
        with self.assertRaisesRegex(ValueError, 'Não foi possível integrar'):
            integrar_relativo([0, 1, 2, 3], pd.DataFrame({1: np.array([1, -1, 2, -2])*1e306}), 'aceleracao')

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
            if shiboken6.isValid(janela):
                janela.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
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

    def janela_aceleracao(self, canais=12):
        acm = TelaLynxAcelerometria()
        self.janelas.append(acm)
        acm.resize(1330, 625)
        acm.show()
        acm.importar_caminho(self.arquivo(['g']*canais))
        self.app.processEvents()
        return acm

    def verificar_botao_visivel(self, janela, botao):
        self.app.processEvents()
        self.assertTrue(botao.isVisible())
        self.assertTrue(botao.isEnabled())
        self.assertFalse(botao.visibleRegion().isEmpty())
        posicao = botao.mapTo(janela, QPoint(0, 0))
        self.assertTrue(janela.rect().contains(posicao))
        self.assertLessEqual(posicao.y() + botao.height(), janela.height())
        self.assertLessEqual(posicao.x() + botao.width(), janela.width())

    def test_botoes_visiveis_e_clicaveis_na_resolucao_da_captura(self):
        acm = self.janela_aceleracao()
        self.assertLessEqual(acm.width(), 1330)
        self.assertLessEqual(acm.height(), 625)
        self.assertIn(VERSAO, acm.windowTitle())
        self.assertIn(str(Path('interface') / 'acelerometria.py'), acm.rotulo_versao.toolTip())
        self.verificar_botao_visivel(acm, acm.botao_velocidade)
        QTest.mouseClick(acm.botao_velocidade, Qt.MouseButton.LeftButton)
        self.assertEqual(len(acm.janelas_resultados), 1)
        vel = acm.janelas_resultados[0]
        self.janelas.append(vel)
        vel.resize(1330, 625)
        self.verificar_botao_visivel(vel, vel.botao_deslocamento)
        self.assertEqual(len(vel.checkboxes_canais), 12)
        QTest.mouseClick(vel.botao_deslocamento, Qt.MouseButton.LeftButton)
        self.assertEqual(len(vel.janelas_resultados), 1)
        desp = vel.janelas_resultados[0]
        self.janelas.append(desp)
        self.verificar_botao_visivel(desp, desp.exportar)
        for janela in (acm, vel, desp):
            self.assertTrue(janela.isVisible())
            self.assertIsNone(janela.parent())

    def test_fechar_origem_preserva_resultados_e_libera_janelas_fechadas(self):
        acm = self.janela_aceleracao(3)
        vel = acm.gerar_velocidade()
        desp = vel.gerar_deslocamento()
        self.janelas.extend([vel, desp])
        copia = desp.df_sensores.copy()
        acm.close()
        shiboken6.delete(acm)
        self.app.processEvents()
        self.assertTrue(vel.isVisible())
        self.assertTrue(desp.isVisible())
        vel.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(shiboken6.isValid(vel))
        self.assertTrue(desp.isVisible())
        pd.testing.assert_frame_equal(desp.df_sensores, copia)

    def test_sem_selecao_na_velocidade_e_exportacoes_sem_curvas(self):
        acm = self.janela_aceleracao(3)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        for checkbox in vel.checkboxes_canais.values():
            checkbox.setChecked(False)
        with patch.object(QMessageBox, 'information') as aviso, patch.object(QFileDialog, 'getExistingDirectory') as pasta:
            vel.botao_deslocamento.click()
            vel.exportar_svg()
            vel.exportar_html()
            self.assertEqual(aviso.call_count, 3)
            pasta.assert_not_called()
        self.assertEqual(vel.janelas_resultados, [])

    def test_falha_de_calculo_nao_altera_origem_ou_abre_janela(self):
        acm = self.janela_aceleracao(3)
        original = acm.df_sensores.copy()
        with patch('isq_dataanalysys.interface.acelerometria.integrar_relativo', side_effect=ValueError('Sinal inválido')):
            acm.botao_velocidade.click()
        self.assertEqual(acm.janelas_resultados, [])
        pd.testing.assert_frame_equal(acm.df_sensores, original)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        copia_vel = vel.df_sensores.copy()
        with patch('isq_dataanalysys.interface.integracao.integrar_relativo', side_effect=ValueError('Sinal inválido')):
            vel.botao_deslocamento.click()
        self.assertEqual(vel.janelas_resultados, [])
        pd.testing.assert_frame_equal(vel.df_sensores, copia_vel)
        self.assertEqual(self.aviso.call_count, 2)

    def test_exportacoes_preservam_valores_unidades_e_referencia_mesmo_sem_csv(self):
        from matplotlib.figure import Figure
        from plotly.graph_objects import Figure as FiguraHtml
        acm = self.janela_aceleracao(3)
        vel = acm.gerar_velocidade()
        desp = vel.gerar_deslocamento()
        self.janelas.extend([vel, desp])
        # A exportação deve funcionar com o CSV removido e manter StartTime UTC.
        acm.caminho_atual.unlink()
        self.app.processEvents()
        for janela, unidade in ((vel, 'mm/s'), (desp, 'mm')):
            janela.checkboxes_canais[2].setChecked(False)
            janela.checkboxes_canais[3].setChecked(False)
            janela.graficos_eixos['X'].setXRange(.2, .8, padding=0)
            self.app.processEvents()
            salvar_svg = Figure.savefig
            salvar_html = FiguraHtml.write_html

            def verificar_svg(fig, *args, **kwargs):
                self.assertIn('início do intervalo', fig._suptitle.get_text())
                self.assertIn('= 0', fig._suptitle.get_text())
                self.assertIn(unidade, fig.axes[0].get_ylabel())
                self.assertEqual(sum(len(e.lines) for e in fig.axes), 1)
                np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(), janela.df_sensores[1])
                np.testing.assert_array_equal(fig.axes[0].lines[0].get_xdata(), janela.tempo)
                np.testing.assert_allclose(fig.axes[0].get_xlim(), [.2, .8])
                return salvar_svg(fig, *args, **kwargs)

            def verificar_html(fig, *args, **kwargs):
                self.assertIn('início do intervalo', fig.layout.title.text)
                self.assertIn('= 0', fig.layout.title.text)
                self.assertEqual(len(fig.data), 1)
                self.assertIn(unidade, fig.layout.yaxis.title.text)
                np.testing.assert_array_equal(fig.data[0].y, janela.df_sensores[1])
                self.assertEqual(fig.data[0].x[0], '2026-10-28T12:00:00.000000')
                self.assertEqual(fig.layout.xaxis.range[0], '2026-10-28T12:00:00.200000')
                return salvar_html(fig, *args, **kwargs)

            with patch.object(QFileDialog, 'getExistingDirectory', return_value=self.tmp.name), patch.object(QMessageBox, 'information'):
                with patch.object(Figure, 'savefig', verificar_svg), patch.object(FiguraHtml, 'write_html', verificar_html):
                    janela.exportar_svg()
                    janela.exportar_html()
        self.aviso.assert_not_called()
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.svg'))), 2)
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.html'))), 2)
