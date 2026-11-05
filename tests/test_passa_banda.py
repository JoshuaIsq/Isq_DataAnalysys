"""Passa-banda: resposta conhecida, validação e aplicação pelos botões reais."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.extensometria import TelaLynxExtensometria
from isq_dataanalysys.interface.passa_banda import DialogoPassaBanda
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.processamento.sinais import Processamento
from tests.apoio import ArquivoMixin


class CalculoPassaBandaTests(unittest.TestCase):
    def test_preserva_faixa_rejeita_extremos_e_nao_muda_original(self):
        fs = 400
        tempo = np.arange(fs * 20) / fs
        sinal = 2 + sum(np.sin(2 * np.pi * f * tempo) for f in (2, 30, 120))
        original = pd.DataFrame({4: sinal, 9: -2 * sinal}, index=np.arange(len(tempo)) + 10)
        copia = original.copy(deep=True)
        resultado, info = Processamento.aplicar(tempo, original, {"passa_banda": (10, 70)})
        # Projeções em seno/cosseno, longe dos transientes das extremidades.
        trecho = slice(5 * fs, -5 * fs)
        for frequencia, esperado, tolerancia in ((2, 0, .001), (30, 1, .001), (120, 0, .001)):
            amplitude = 2 * abs(np.mean(
                resultado[4].to_numpy()[trecho] * np.exp(-2j * np.pi * frequencia * tempo[trecho])
            ))
            self.assertAlmostEqual(amplitude, esperado, delta=tolerancia)
        self.assertAlmostEqual(resultado[4].iloc[trecho].mean(), 0, delta=1e-8)
        np.testing.assert_allclose(resultado[9], -2 * resultado[4], atol=1e-12)
        pd.testing.assert_frame_equal(original, copia)
        self.assertTrue(resultado.index.equals(original.index))
        self.assertEqual(list(resultado.columns), [4, 9])
        self.assertEqual(resultado.shape, original.shape)
        self.assertEqual(info["fs"], fs)

    def test_cortes_invalidos_incluindo_nyquist(self):
        tempo = np.arange(200) / 200
        original = pd.DataFrame({1: np.sin(2 * np.pi * 20 * tempo)})
        for cortes in ((0, 40), (-1, 40), (40, 40), (50, 10), (10, 100),
                       (10, 400), (np.nan, 40), (10, np.inf), (10,), (10, 20, 30),
                       None, "errado", ("errado", 40)):
            with self.subTest(cortes=cortes), self.assertRaisesRegex(ValueError, "Passa-banda"):
                Processamento.aplicar(tempo, original, {"passa_banda": cortes})

    def test_arquivo_curto_e_amostragem_irregular(self):
        with self.assertRaisesRegex(ValueError, "Arquivo curto"):
            Processamento.passa_banda(pd.DataFrame({1: np.zeros(27)}), 10, 40, 200)
        tempo = np.arange(100) / 200
        tempo[40] += .001
        with self.assertRaisesRegex(ValueError, "Amostragem irregular"):
            Processamento.aplicar(tempo, pd.DataFrame({1: np.zeros(100)}), {"passa_banda": (10, 40)})

    def test_passa_banda_nao_aciona_filtros_individuais(self):
        tempo = np.arange(1000) / 1000
        original = pd.DataFrame({1: np.sin(2 * np.pi * 50 * tempo)})
        with patch.object(Processamento, "passa_alta", wraps=Processamento.passa_alta) as alta, \
                patch.object(Processamento, "passa_baixa", wraps=Processamento.passa_baixa) as baixa:
            Processamento.aplicar(tempo, original, {"passa_banda": (30, 100)})
            alta.assert_not_called()
            baixa.assert_not_called()
            Processamento.aplicar(tempo, original, {
                "passa_banda": (30, 100), "passa_alta": 40, "passa_baixa": 80,
            })
            alta.assert_called_once()
            baixa.assert_called_once()


class InterfacePassaBandaTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.aviso = patch.object(QMessageBox, "warning").start()
        self.addCleanup(patch.stopall)
        self.janelas = []
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in self.janelas:
            janela.close()
            janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def criar_tela(self):
        tela = TelaLynxAcelerometria()
        self.janelas.append(tela)
        self.assertFalse(tela.botao_passa_banda.isEnabled())
        self.assertTrue(tela.importar_caminho(self.arquivo(["g"] * 6)))
        tela.resize(1330, 625)
        tela.show()
        self.app.processEvents()
        return tela

    def dialogo(self, tela, acao):
        erros = []

        def interagir():
            dialogo = self.app.activeModalWidget()
            try:
                self.assertIsInstance(dialogo, DialogoPassaBanda)
                acao(dialogo)
            except BaseException as erro:
                erros.append(erro)
            finally:
                if dialogo is not None and dialogo.isVisible():
                    dialogo.reject()

        self.assertTrue(tela.botao_passa_banda.isEnabled())
        QTimer.singleShot(0, interagir)
        tela.botao_passa_banda.click()
        if erros:
            raise erros[0]

    def aplicar(self, tela, inferior=30, superior=100):
        def preencher(dialogo):
            dialogo.campo_inferior.setValue(inferior)
            dialogo.campo_superior.setValue(superior)
            dialogo.botao_aplicar.click()
        self.dialogo(tela, preencher)

    def test_aplicar_so_a_banda_e_reaplicar_sem_acumular(self):
        tela = self.criar_tela()
        original = tela.df_original.copy(deep=True)
        # Valores digitados nos outros campos, sem clicar Aplicar, não são usados.
        tela.controle_passa_alta.campo.setValue(40)
        tela.controle_passa_baixa.campo.setValue(80)
        self.aplicar(tela)
        self.assertEqual(tela.config_filtros, {"passa_banda": (30, 100)})
        self.assertIn("Passa-banda: 30–100 Hz", tela.rotulo_ativos.text())
        primeiro = tela.df_sensores.copy(deep=True)
        self.assertFalse(np.allclose(primeiro, original))
        self.aplicar(tela)
        pd.testing.assert_frame_equal(tela.df_sensores, primeiro)
        pd.testing.assert_frame_equal(tela.df_original, original)
        self.assertTrue(tela.botao_passa_banda.isVisible())
        self.assertFalse(tela.botao_passa_banda.visibleRegion().isEmpty())
        self.aviso.assert_not_called()

    def test_cancelar_e_parametros_invalidos_preservam_estado(self):
        tela = self.criar_tela()
        self.aplicar(tela)
        dados = tela.df_sensores.copy(deep=True)

        def cancelar(dialogo):
            self.assertEqual(dialogo.cortes(), (30, 100))
            dialogo.campo_inferior.setValue(60)
            dialogo.botao_cancelar.click()
        self.dialogo(tela, cancelar)
        self.aplicar(tela, 100, 20)
        self.aviso.assert_called_once()
        self.assertEqual(tela.config_filtros, {"passa_banda": (30, 100)})
        pd.testing.assert_frame_equal(tela.df_sensores, dados)

    def test_filtros_explicitos_e_desativacao_apenas_da_banda(self):
        tela = self.criar_tela()
        tela.controle_calibração.campo.setValue(2)
        tela.controle_calibração.botao.click()
        tela.controle_passa_alta.campo.setValue(40)
        tela.controle_passa_alta.botao.click()
        anteriores = tela.df_sensores.copy(deep=True)
        self.aplicar(tela)
        self.assertEqual(tela.config_filtros, {
            "calibracao": 2, "passa_alta": 40, "passa_banda": (30, 100),
        })
        tela.controle_passa_baixa.campo.setValue(80)
        tela.controle_passa_baixa.botao.click()
        self.assertEqual(tela.config_filtros["passa_banda"], (30, 100))
        self.assertEqual(tela.config_filtros["passa_baixa"], 80)
        esperado, _ = Processamento.aplicar(tela.tempo, tela.df_original, {
            "calibracao": 2, "passa_alta": 40, "passa_baixa": 80,
        })
        self.dialogo(tela, lambda d: d.botao_desativar.click())
        self.assertNotIn("passa_banda", tela.config_filtros)
        pd.testing.assert_frame_equal(tela.df_sensores, esperado)
        self.assertFalse(np.allclose(tela.df_sensores, anteriores))
        self.aviso.assert_not_called()

    def test_restaurar_e_reimportar_limpam_banda(self):
        tela = self.criar_tela()
        self.aplicar(tela)
        tela.botao_rms.click()
        tela.botao_restaurar.click()
        self.assertEqual(tela.config_filtros, {})
        self.assertEqual(tela.botao_passa_banda.text(), "Passa-banda…")
        self.assertFalse(tela.botao_rms.isChecked())
        pd.testing.assert_frame_equal(tela.df_sensores, tela.df_original)
        self.aplicar(tela)
        tela.importar_caminho(self.arquivo(["g"] * 3))
        self.assertEqual(tela.config_filtros, {})
        self.assertEqual(tela.rotulo_ativos.text(), "Tratamentos ativos: nenhum")
        pd.testing.assert_frame_equal(tela.df_sensores, tela.df_original)
        self.aviso.assert_not_called()

    def test_rms_fft_e_exportacao_usam_o_sinal_filtrado(self):
        tela = self.criar_tela()
        # A faixa exclui os 50 Hz do CSV sintético.
        self.aplicar(tela, 150, 250)
        tratado = tela.df_sensores.copy(deep=True)
        np.testing.assert_array_equal(tela.curvas_lynx[(1, "X")].getOriginalDataset()[1], tratado[1])
        figura = criar_figura_html(list(tela.graficos_eixos.values()))
        np.testing.assert_array_equal(figura.data[0].y, tratado[1])
        tela.botao_rms.click()
        self.assertLess(tela.curvas_lynx[(1, "X")].getOriginalDataset()[1].max(), 10)
        self.assertEqual(tela.graficos_eixos["X"].getAxis("left").labelUnits, "mg")
        tela.botao_fft.click()
        x, y = tela.curvas_lynx[(1, "X")].getOriginalDataset()
        self.assertLess(y[np.argmin(abs(x - 50))], .01)
        pd.testing.assert_frame_equal(tela.df_sensores, tratado)
        self.aviso.assert_not_called()

    def test_extensometria_mantem_controles_sem_passa_banda(self):
        tela = TelaLynxExtensometria()
        self.janelas.append(tela)
        self.assertIsNone(tela.findChild(QPushButton, "passa_banda"))
        self.assertIn("passa_alta", tela.controles_filtros)
        self.assertIn("passa_baixa", tela.controles_filtros)


if __name__ == "__main__":
    unittest.main()
