"""A navegação lateral troca controles sem recriar sinais ou alterar gráficos."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from PySide6.QtCore import QCoreApplication, QEvent, QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from tests.apoio import ArquivoMixin
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria


class LateralTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.tela = TelaLynxAcelerometria()
        self.tela.resize(1024, 768)
        self.tela.show()
        self.addCleanup(self.fechar)
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.addCleanup(patch.stopall)
        self.tela.importar_caminho(self.arquivo(['g'] * 6))
        self.app.processEvents()

    def fechar(self):
        self.tela.close()
        self.tela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def test_troca_painel_preserva_dados_filtros_e_geometria_dos_graficos(self):
        w = self.tela
        w.controle_passa_banda.campo_inferior.setValue(10)
        w.controle_passa_banda.campo_superior.setValue(100)
        w.controle_passa_banda.botao_aplicar.click()
        w.aplicar_intervalo_temporal((.2, .8))
        self.app.processEvents()
        dados = w.df_sensores.copy(deep=True)
        faixas = {e: p.viewRange() for e, p in w.graficos_eixos.items()}
        geometria = w.grafico.geometry()
        for _ in range(4):
            w.botao_aba_canais.click()
            self.app.processEvents()
            self.assertEqual(w.paginas_laterais.currentIndex(), 1)
            self.assertFalse(w.abrir.isVisible())
            self.assertTrue(w.checkboxes_eixos[(1, 'X')].isVisible())
            self.assertTrue(w.botao_aba_canais.isChecked())
            self.assertFalse(w.botao_aba_controles.isChecked())
            self.assertEqual(w.grafico.geometry(), geometria)
            w.botao_aba_controles.click()
            self.app.processEvents()
            self.assertEqual(w.paginas_laterais.currentIndex(), 0)
            self.assertTrue(w.abrir.isVisible())
            self.assertFalse(w.checkboxes_eixos[(1, 'X')].isVisible())
            self.assertEqual(w.grafico.geometry(), geometria)
        for eixo, plot in w.graficos_eixos.items():
            np.testing.assert_array_equal(plot.viewRange(), faixas[eixo])
        pd.testing.assert_frame_equal(w.df_sensores, dados)
        self.assertEqual(w.config_filtros, {'passa_banda': (10, 100)})
        self.aviso.assert_not_called()

    def test_canais_controlam_curvas_e_exportacao_nas_duas_paginas(self):
        w = self.tela
        w.botao_aba_canais.click()
        w.checkboxes_canais[2].setChecked(False)
        w.checkboxes_eixos[(1, 'Y')].setChecked(False)
        for botao in (w.botao_aba_canais, w.botao_aba_controles):
            botao.click()
            self.app.processEvents()
            _, dados, _, _ = w.dados_para_csv()
            self.assertEqual(list(dados.columns), [1, 3])
            self.assertFalse(w.curvas_lynx[(1, 'Y')].isVisible())
            self.assertFalse(w.curvas_lynx[(2, 'X')].isVisible())
        self.assertFalse(w.checkboxes_eixos[(1, 'Y')].isChecked())
        self.assertFalse(w.checkboxes_canais[2].isChecked())

    def test_campos_cabem_na_lateral_e_rolagem_alcanca_ultimos_botoes(self):
        w = self.tela
        campos = (w.controle_passa_banda.campo_inferior, w.controle_passa_banda.campo_superior,
                  w.controle_passa_banda.botao_aplicar, w.controle_passa_banda.botao_desativar,
                  w.controle_offset.campo, w.controle_offset.botao, w.campo_janela_rms,
                  w.botao_velocidade, w.campo_y_min, w.campo_y_max,
                  w.campo_tempo_inicio, w.campo_tempo_fim,
                  w.botao_aplicar_visualizacao, w.botao_ajustar)
        for largura, altura in ((1024, 768), (800, 600), (1330, 625)):
            w.resize(largura, altura)
            self.app.processEvents()
            for campo in campos:
                w.rolagem_controles.ensureWidgetVisible(campo)
                self.app.processEvents()
                viewport = w.rolagem_controles.viewport()
                origem = campo.mapTo(viewport, QPoint(0, 0))
                with self.subTest(tamanho=(largura, altura), campo=campo.objectName()):
                    self.assertGreaterEqual(origem.x(), 0)
                    self.assertLessEqual(origem.x() + campo.width(), viewport.width())
                    self.assertFalse(campo.visibleRegion().isEmpty())
            self.assertGreater(w.grafico.width(), largura * .5)
            self.assertGreater(w.grafico.height(), altura * .85)
