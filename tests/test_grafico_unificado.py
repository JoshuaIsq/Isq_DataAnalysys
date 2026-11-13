"""Agrupamento dos resultados e snapshots com seleção independente."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.grafico_unificado import abrir_grafico_unificado, CORES_EIXOS
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.exportacao.csv_tratado import salvar_csv_tratado, ler_csv_tratado
from tests.apoio import ArquivoMixin


class GraficoUnificadoTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas = []
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar)
        self.a = TelaLynxAcelerometria()
        self.janelas.append(self.a)
        self.a.show()
        self.a.importar_caminho(self.arquivo(['g']*6,
            ['ACC 1 - Z','ACC 2 - X','ACC 1 - Y','ACC 2 - Z','ACC 1 - X','ACC 2 - Y']))

    def fechar(self):
        for w in reversed(self.janelas):
            if shiboken6.isValid(w):
                w.close()
                if not w.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose): w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.janelas.clear()

    def resultados(self):
        self.a.botao_converter.click()
        v = self.a.gerar_velocidade()
        d = v.gerar_deslocamento()
        self.janelas.extend([v,d])
        return v,d

    def test_velocidade_posicao_por_sensor_e_rgb_preservam_identificacao(self):
        for w in self.resultados():
            self.assertEqual(len(w.graficos_eixos), 2)
            for canal, info in w.canais.items():
                curva = w.curvas[canal]
                self.assertIn(curva, w.graficos_eixos[info['sensor_id']].listDataItems())
                self.assertEqual(curva.opts['pen'].color().name(), CORES_EIXOS[info['eixo']])
                np.testing.assert_array_equal(curva.getOriginalDataset()[1], w.df_sensores[canal])
            self.assertEqual({c:w.canais[c]['sensor_id'] for c in w.canais}, {1:1,2:2,3:1,4:2,5:1,6:2})

    def test_unificado_tres_telas_selecao_independente_csv_e_fechamento(self):
        v,d = self.resultados()
        d.controle_passa_banda.campo_inferior.setValue(1)
        d.controle_passa_banda.campo_superior.setValue(30)
        d.aplicar_passa_banda()
        for origem in (self.a,v,d):
            copia = origem.df_sensores.copy(deep=True)
            origem.botao_unificado.click()
            w = origem.janelas_resultados[-1]
            self.janelas.append(w)
            self.assertEqual(len(w.graficos_eixos), 1)
            self.assertEqual(len(w.curvas), 6)
            self.assertTrue(all(c.isChecked() for c in w.checkboxes_canais.values()))
            w.selecionar_todos(False)
            self.assertFalse(any(c.isVisible() for c in w.curvas.values()))
            w.checkboxes_canais[3].setChecked(True)
            w.painel_intervalo.definir_intervalo_segundos(.2,.8)
            tempo,dados,canais,meta = w.dados_para_csv()
            self.assertEqual(list(dados), [3])
            np.testing.assert_array_equal(dados[3], copia.loc[(origem.tempo>=.2)&(origem.tempo<=.8),3])
            destino = self.arquivo(['g']*3).with_name('unificado.csv')
            salvar_csv_tratado(destino,tempo,dados,canais,inicio_csv=w.inicio_exportacao,metadados=meta)
            pd.testing.assert_frame_equal(ler_csv_tratado(destino).dados, dados)
            figura = criar_figura_html(w.plots_para_exportar())
            self.assertEqual(len(figura.data),1)
            self.assertEqual(figura.layout.xaxis.type,'date')
            pd.testing.assert_frame_equal(origem.df_sensores,copia)
            self.assertTrue(all(c.isVisible() for c in (origem.curvas_lynx if origem is self.a else origem.curvas).values()))
            origem.close()
            self.app.processEvents()
            self.assertTrue(w.isVisible())
        self.aviso.assert_not_called()

    def test_espectros_rms_e_curvas_ocultas_incluidos_sem_recalcular(self):
        a = self.a
        a.checkboxes_eixos[(1,'X')].setChecked(False)
        for modo, unidade in (('fft','g'),('psd','g²/Hz'),('rms','mg')):
            getattr(a,'botao_'+modo).click()
            if modo == 'rms': a.checkbox_log_rms.setChecked(True)
            w = abrir_grafico_unificado(a)
            self.janelas.append(w)
            self.assertEqual(len(w.curvas),6)
            for (sensor,eixo), curva in a.curvas_lynx.items():
                canal = a.sensores_lynx[sensor-1][eixo]
                np.testing.assert_array_equal(w.df_sensores[canal], getattr(curva,'dados_csv',curva.getOriginalDataset()[1]))
                self.assertEqual(w.canais[canal]['unidade'],unidade)
                self.assertTrue(w.checkboxes_canais[canal].isChecked())
            self.assertEqual(w.painel_intervalo.isHidden(), modo!='rms')
            if modo!='rms':
                self.assertEqual(w.graficos_eixos[0].getAxis('bottom').labelUnits,'Hz')
                with self.assertRaisesRegex(ValueError,'FFT/PSD'): w.dados_para_csv()
            copia = w.df_sensores.copy()
            a.restaurar_original()
            pd.testing.assert_frame_equal(w.df_sensores,copia)
        self.aviso.assert_not_called()
