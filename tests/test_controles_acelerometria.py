"""Controles simplificados, escala comum e recorte sem alterar as medições."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from tests.apoio import ArquivoMixin
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.extensometria import TelaLynxExtensometria
from isq_dataanalysys.exportacao.html import criar_figura_html


class ControlesTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas = []
        self.aviso = patch.object(QMessageBox, "warning").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            janela.close()
            janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def abrir(self, longa=False):
        def alongar(linhas):
            linhas[0][-1] = "0.2Hz"
            for i, linha in enumerate(linhas[5:]):
                linha[0] = str(i * 5)
        acm = TelaLynxAcelerometria()
        self.janelas.append(acm)
        acm.resize(1330, 800)
        acm.show()
        acm.importar_caminho(self.arquivo(["g"] * 3, alterar=alongar if longa else None))
        self.app.processEvents()
        return acm

    def test_so_offset_e_banda_na_acelerometria_outros_filtros_preservados_na_ext(self):
        acm = self.abrir()
        self.assertEqual(set(acm.controles_filtros), {"offset"})
        self.assertFalse(hasattr(acm, "campo_janela_outliers"))
        for atributo in ("controle_outliers", "controle_calibração", "controle_media_movel",
                         "controle_passa_alta", "controle_passa_baixa"):
            self.assertFalse(hasattr(acm, atributo))
        for campo in (acm.controle_passa_banda.campo_inferior,
                      acm.controle_passa_banda.campo_superior):
            self.assertTrue(campo.isVisible())
            self.assertTrue(campo.isEnabled())
        ext = TelaLynxExtensometria()
        self.janelas.append(ext)
        self.assertEqual(set(ext.controles_filtros),
                         {"offset", "outliers", "calibracao", "media_movel", "passa_alta", "passa_baixa"})

    def test_escala_e_40_a_60_minutos_em_todos_eixos_html_e_csv(self):
        acm = self.abrir(longa=True)
        original = acm.df_sensores.copy(deep=True)
        acm.campo_y_min.setValue(-4)
        acm.campo_y_max.setValue(6)
        acm.campo_tempo_inicio.setValue(40)
        acm.campo_tempo_fim.setValue(60)
        acm.botao_aplicar_visualizacao.click()
        self.app.processEvents()
        for plot in acm.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange(), [[2400, 3600], [-4, 6]], atol=1e-9)
        tempo, dados, _, metadata = acm.dados_para_csv()
        np.testing.assert_array_equal(tempo, np.arange(2400, 3601, 5))
        pd.testing.assert_frame_equal(dados, original.iloc[480:721].reset_index(drop=True))
        self.assertEqual(metadata["intervalo_avaliacao_s"], [2400, 3600])
        figura = criar_figura_html(acm.plots_para_exportar())
        for i in ("", "2", "3"):
            self.assertEqual(list(figura.layout["yaxis" + i].range), [-4, 6])
            self.assertEqual(list(figura.layout["xaxis" + i].range),
                             ["2026-10-28T09:40:00.000000", "2026-10-28T10:00:00.000000"])
        pd.testing.assert_frame_equal(acm.df_sensores, original)
        self.aviso.assert_not_called()

    def test_limites_invalidos_preservam_vista_e_tempos_limitados_ao_csv(self):
        acm = self.abrir(longa=True)
        anterior = acm.graficos_eixos["X"].viewRange()
        acm.campo_tempo_inicio.setValue(-1)
        acm.campo_tempo_fim.setValue(10000)
        self.assertEqual(acm.campo_tempo_inicio.value(), 0)
        self.assertEqual(acm.segundos_do_campo(acm.campo_tempo_fim), 4995)
        acm.campo_y_min.setValue(1)
        acm.campo_y_max.setValue(1)
        self.assertFalse(acm.aplicar_visualizacao())
        acm.campo_y_max.setValue(2)
        acm.campo_tempo_inicio.setValue(60)
        acm.campo_tempo_fim.setValue(40)
        self.assertFalse(acm.aplicar_visualizacao())
        np.testing.assert_array_equal(acm.graficos_eixos["X"].viewRange(), anterior)
        self.assertIsNone(acm.intervalo_exportacao())
        self.assertEqual(self.aviso.call_count, 2)

    def test_reaplicar_escala_nao_exclui_amostra_por_arredondamento_em_minutos(self):
        acm = self.abrir()
        acm.aplicar_intervalo_temporal((.2, .8))
        acm.campo_y_min.setValue(-10)
        acm.campo_y_max.setValue(10)
        acm.botao_aplicar_visualizacao.click()
        self.assertEqual(acm.intervalo_exportacao(), (.2, .8))
        tempo, dados, _, _ = acm.dados_para_csv()
        self.assertEqual((tempo[0], tempo[-1], len(dados)), (.2, .8, 601))
        self.aviso.assert_not_called()

    def test_ajuste_automatico_usa_canais_selecionados_e_restaura_intervalo(self):
        acm = self.abrir()
        acm.aplicar_intervalo_temporal((.2, .8))
        acm.checkboxes_eixos[(1, "Y")].setChecked(False)
        acm.checkboxes_eixos[(1, "Z")].setChecked(False)
        acm.botao_ajustar.click()
        for plot in acm.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange(), [[0, .999], [-1.1, 1.1]], atol=1e-9)
        self.assertIsNone(acm.intervalo_exportacao())
        acm.checkboxes_eixos[(1, "X")].setChecked(False)
        acm.botao_ajustar.click()
        self.aviso.assert_not_called()

    def test_escala_por_modo_rms_log_e_retorno_do_fft(self):
        acm = self.abrir()
        acm.aplicar_intervalo_temporal((.2, .8))
        acm.campo_y_min.setValue(-2)
        acm.campo_y_max.setValue(4)
        self.assertTrue(acm.aplicar_visualizacao())
        intervalo = acm.intervalo_exportacao()
        acm.botao_rms.click()
        acm.checkbox_log_rms.setChecked(True)
        acm.campo_y_min.setValue(1)
        acm.campo_y_max.setValue(10000)
        acm.botao_aplicar_visualizacao.click()
        for plot in acm.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange()[1], [0, 4])
        acm.campo_y_min.setValue(0)
        self.assertFalse(acm.aplicar_visualizacao())
        acm.botao_fft.click()
        self.assertFalse(acm.campo_tempo_inicio.isEnabled())
        self.assertTrue(acm.campo_y_min.isEnabled())
        self.assertIsNone(acm.intervalo_exportacao())
        acm.botao_fft.click()
        self.assertEqual(acm.intervalo_exportacao(), intervalo)
        for plot in acm.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange(), [intervalo, [-2, 4]])
        self.assertEqual(acm.campo_y_min.suffix(), " g")
        self.assertEqual(self.aviso.call_count, 1)

    def test_extensometria_sem_botoes_horario_e_falha_sem_sugerir_botao_ausente(self):
        ext = TelaLynxExtensometria()
        self.janelas.append(ext)
        ext.importar_caminho(self.arquivo(["µm/m"], alterar=lambda l: l[1].__setitem__(-1, "sem data")))
        self.assertEqual(ext.painel_referencia.findChildren(QPushButton), [])
        self.assertEqual(ext.painel_referencia.rotulo.text(), "Data/hora não reconhecida; eixo em segundos.")
        self.assertIsNone(ext.inicio_arquivo)
        self.assertEqual(ext.grafico.getAxis("bottom").labelUnits, "s")
        self.assertEqual(ext.painel_referencia.rotulo.toolTip(), "")
