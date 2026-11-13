"""Conversão explícita, espectros e filtro independente da posição na interface."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidget
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.exportacao.csv_tratado import salvar_csv_tratado, ler_csv_tratado
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.processamento.sinais import Processamento
from tests.apoio import ArquivoMixin


class FluxoCinematicaTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.info = patch.object(QMessageBox, 'information').start()
        self.addCleanup(patch.stopall)
        self.janelas = []
        self.addCleanup(self.fechar)
        self.a = TelaLynxAcelerometria()
        self.janelas.append(self.a)
        self.a.show()
        self.assertTrue(self.a.importar_caminho(self.arquivo(['g']*3)))

    def fechar(self):
        for w in reversed(self.janelas):
            if shiboken6.isValid(w):
                w.close()
                if not w.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose): w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.janelas.clear()

    def resultados(self):
        self.a.aplicar_configuracao({'passa_banda': (1,30)})
        self.a.botao_converter.click()
        v = self.a.gerar_velocidade()
        d = v.gerar_deslocamento()
        self.janelas.extend([v,d])
        self.app.processEvents()
        return v,d

    def test_conversao_uma_vez_fft_e_psd_continuam_em_g_reset_importacao(self):
        a = self.a
        self.assertFalse(a.botao_velocidade.isEnabled())
        self.assertIsNone(a.gerar_velocidade())
        self.info.assert_called_once()
        a.aplicar_configuracao({'passa_banda': (1,30)})
        original = a.df_original.copy()
        filtrado = a.df_tratado_g.copy()
        a.aplicar_intervalo_temporal((.2,.8))
        a.botao_converter.click()
        np.testing.assert_allclose(a.df_sensores, filtrado*9810)
        for modo, unidade, funcao in (('fft','g',Processamento.fft_ac), ('psd','g²/Hz',Processamento.psd_ac)):
            getattr(a, 'botao_'+modo).click()
            self.assertFalse(a.campo_tempo_inicio.isEnabled())
            self.assertEqual(a.graficos_eixos['X'].getAxis('left').labelUnits, unidade)
            f, dados, _ = funcao(a.tempo, filtrado)
            for (n,eixo), curva in a.curvas_lynx.items():
                canal = a.sensores_lynx[n-1][eixo]
                x,y = curva.getOriginalDataset()
                np.testing.assert_array_equal(x,f)
                np.testing.assert_allclose(y,dados[canal])
            figura = criar_figura_html(a.plots_para_exportar(), inicio=a.inicio_arquivo)
            self.assertNotEqual(figura.layout.xaxis.type, 'date')
            with self.assertRaisesRegex(ValueError,'FFT/PSD'): a.dados_para_csv()
        a.botao_psd.click()
        self.assertEqual(a.intervalo_exportacao(), (.2,.8))
        self.assertEqual(a.graficos_eixos['X'].getAxis('left').labelUnits, 'mm/s²')
        a.aplicar_configuracao({'passa_banda':(1,30)})
        np.testing.assert_allclose(a.df_sensores, filtrado*9810)
        pd.testing.assert_frame_equal(a.df_original, original)
        a.restaurar_original()
        self.assertFalse(a.botao_converter.isChecked())
        self.assertFalse(a.botao_velocidade.isEnabled())
        pd.testing.assert_frame_equal(a.df_sensores, original)
        a.botao_converter.click()
        a.importar_caminho(self.arquivo(['g']*3))
        self.assertFalse(a.botao_converter.isChecked())
        self.assertFalse(a.botao_velocidade.isEnabled())
        self.aviso.assert_not_called()

    def test_passa_banda_posicao_reaplicavel_reversivel_e_csv_fiel(self):
        v,d = self.resultados()
        origem, velocidade = self.a.df_sensores.copy(), v.df_sensores.copy()
        corrigido = d.df_sensores.copy()
        d.painel_intervalo.definir_intervalo_segundos(.2,.8)
        d.checkboxes_canais[2].setChecked(False)
        d.controle_passa_banda.campo_inferior.setValue(3)
        d.controle_passa_banda.campo_superior.setValue(20)
        self.assertTrue(d.aplicar_passa_banda())
        esperado,_ = Processamento.aplicar(d.tempo, corrigido, {'passa_banda':(3,20)})
        pd.testing.assert_frame_equal(d.df_sensores, esperado)
        d.aplicar_passa_banda()
        pd.testing.assert_frame_equal(d.df_sensores, esperado)
        self.assertEqual(d.intervalo_exportacao(), (.2,.8))
        self.assertFalse(d.checkboxes_canais[2].isChecked())
        tempo,dados,canais,metadata = d.dados_para_csv()
        self.assertEqual(list(canais), [1,3])
        self.assertTrue(all(c['unidade']=='mm' for c in canais.values()))
        destino = self.arquivo(['g']*3).with_name('posicao_tratada.csv')
        salvar_csv_tratado(destino,tempo,dados,canais,inicio_csv=d.inicio_exportacao,metadados=metadata)
        relido = ler_csv_tratado(destino)
        pd.testing.assert_frame_equal(relido.dados,dados)
        self.assertEqual(relido.metadados['passa_banda_posicao_hz'], [3,20])
        self.assertEqual([e['grau_ajuste_apos_integrar'] for e in relido.metadados['etapas_integracao']], [1,2])
        self.assertTrue(d.aplicar_passa_banda(desativar=True))
        pd.testing.assert_frame_equal(d.df_sensores, corrigido)
        pd.testing.assert_frame_equal(self.a.df_sensores, origem)
        pd.testing.assert_frame_equal(v.df_sensores, velocidade)
        self.aviso.assert_not_called()

    def test_filtro_invalido_nao_substitui_posicao_e_estatisticas_respeitam_recorte(self):
        v,d = self.resultados()
        antes = d.df_sensores.copy()
        d.controle_passa_banda.campo_inferior.setValue(30)
        d.controle_passa_banda.campo_superior.setValue(1)
        self.assertFalse(d.aplicar_passa_banda())
        pd.testing.assert_frame_equal(d.df_sensores, antes)
        self.assertIsNone(d.cortes_posicao)
        self.aviso.assert_called_once()
        v.checkboxes_canais[2].setChecked(False)
        v.painel_intervalo.definir_intervalo_segundos(.2,.8)
        estat, intervalo, quantidade = v.dados_estatisticas()
        recorte = v.df_sensores.loc[(v.tempo>=.2)&(v.tempo<=.8),[1,3]]
        self.assertEqual(quantidade,len(recorte))
        self.assertEqual(intervalo,(.2,.8))
        np.testing.assert_allclose(estat['RMS'],np.sqrt((recorte**2).mean()))
        np.testing.assert_allclose(estat['Máximo'],recorte.max())
        np.testing.assert_allclose(estat['Mínimo'],recorte.min())
        janela = v.mostrar_estatisticas()
        self.assertEqual(janela.findChild(QTableWidget).rowCount(), 2)
        janela.close()
        d.mostrar_detalhes().close()
