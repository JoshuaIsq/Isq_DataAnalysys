"""Recorte em minutos, CSV reaberto e relógio nas exportações reais."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import csv
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtCore import QCoreApplication, QEvent, Qt
import shiboken6
from plotly.graph_objects import Figure

from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.extensometria import TelaLynxExtensometria
from isq_dataanalysys.interface.regua import TelaLynxReguaPotenciometrica
from isq_dataanalysys.interface.dados_tratados import TelaDadosTratados
from isq_dataanalysys.exportacao.csv_tratado import ler_csv_tratado


class ExportacaoCsvFluxoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pasta=Path(self.tmp.name)
        self.aviso=patch.object(QMessageBox,'warning').start()
        self.info=patch.object(QMessageBox,'information').start()
        self.addCleanup(patch.stopall)
        self.janelas=[]
        self.addCleanup(self.fechar)
        self.arquivo=self.pasta/'origem.csv'
        linhas=[['Name','ACC 1 - X','ACC 1 - Y','ACC 1 - Z','Tensão A','Ext A','Régua A','', 'SampFreq:','1Hz'],
                ['Unit','g','g','g','MPa','µm/m','mm','', 'StartTime UTC:','2026/11/11 15:00:00'],
                ['HighLim']+['100000']*6,['LowLim']+['-100000']*6,['Time (s)']]
        for t in range(4201):
            v=np.sin(2*np.pi*.03*t)
            valores=[t,.03+.001*v,.02+.002*v,.01+.003*v,10+v,20+v,30+v]
            linhas.append([format(x,'.17g').replace('.',',') for x in valores])
        with self.arquivo.open('w',encoding='utf-8-sig',newline='') as f:
            csv.writer(f,delimiter=';').writerows(linhas)

    def fechar(self):
        for w in reversed(self.janelas):
            if shiboken6.isValid(w):
                w.close()
                if not w.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
                    w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.janelas.clear()

    def abrir(self,classe):
        w=classe()
        self.janelas.append(w)
        w.show()
        w.importar_caminho(self.arquivo)
        self.app.processEvents()
        self.aviso.reset_mock()  # Aviso esperado: CSV mistura modalidades.
        return w

    def exportar(self,w,nome):
        p=self.pasta/f'{nome}.csv'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(p),'CSV')):
            w.exportar_csv()
        self.aviso.assert_not_called()
        return p,ler_csv_tratado(p)

    def test_aceleracao_velocidade_deslocamento_recorte_e_reabertura(self):
        acm=self.abrir(TelaLynxAcelerometria)
        acm.aplicar_configuracao({'offset':2})
        acm.botao_converter.click()
        fonte=acm.df_sensores.copy(deep=True)
        acm.aplicar_intervalo_temporal((2400,3600))
        acm.checkboxes_eixos[(1,'Y')].setChecked(False)
        acm.botao_converter.setChecked(True)
        vel=acm.gerar_velocidade()
        disp=vel.gerar_deslocamento()
        self.janelas.extend([vel,disp])
        self.app.processEvents()
        for w,nome,unidade in [(acm,'aceleracao','mm/s²'),(vel,'velocidade','mm/s'),(disp,'deslocamento','mm')]:
            caminho,relido=self.exportar(w,nome)
            np.testing.assert_array_equal(relido.tempo,np.arange(2400,3601))
            self.assertEqual(list(relido.dados),[1,3])
            self.assertTrue(all(c['unidade']==unidade for c in relido.canais.values()))
            pd.testing.assert_frame_equal(relido.dados.reset_index(drop=True),w.df_sensores[[1,3]].iloc[2400:3601].reset_index(drop=True))
            self.assertEqual(relido.inicio_csv,datetime(2026,11,11,15))
            self.assertIn('2026-11-11T12:40:00',caminho.read_text(encoding='utf-8-sig'))
            viewer=TelaDadosTratados()
            self.janelas.append(viewer)
            viewer.show()
            self.assertTrue(viewer.importar_caminho(caminho))
            self.app.processEvents()
            self.assertAlmostEqual(viewer.painel_intervalo.inicio_min.value(),40)
            self.assertAlmostEqual(viewer.painel_intervalo.fim_min.value(),60)
            segundo,outra=self.exportar(viewer,nome+'_outra')
            pd.testing.assert_frame_equal(outra.dados,relido.dados)
            np.testing.assert_array_equal(outra.tempo,relido.tempo)
            self.assertEqual(outra.inicio_csv,relido.inicio_csv)
            self.assertIn('2026-11-11T12:40:00',segundo.read_text(encoding='utf-8-sig'))
        pd.testing.assert_frame_equal(acm.df_sensores,fonte)

    def test_escalas_extensometria_regua_e_csv_visivel(self):
        for classe,nome in [(TelaLynxExtensometria,'ext'),(TelaLynxReguaPotenciometrica,'regua')]:
            w=self.abrir(classe)
            w.aplicar_configuracao({'calibracao':3})
            w.definir_limites([2400,3600],[-100000,100000])
            _,r=self.exportar(w,nome)
            self.assertEqual(len(r.tempo),1201)
            self.assertEqual(r.tempo[0],2400)
            for c in r.dados:
                if nome=='regua':
                    esperado=w.df_sensores[c].iloc[2400:3601]
                else:
                    esperado=w.valores_visuais(c)[2400:3601]
                np.testing.assert_array_equal(r.dados[c],esperado)
                self.assertEqual(r.canais[c]['unidade'],w.unidade_visual)

    def test_html_timestamp_todas_linhas_e_intervalo_exato(self):
        acm=self.abrir(TelaLynxAcelerometria)
        acm.aplicar_intervalo_temporal((2400,3600))
        acm.botao_converter.setChecked(True)
        vel=acm.gerar_velocidade()
        self.janelas.append(vel)
        self.app.processEvents()
        capturas=[]
        original=Figure.write_html
        def salvar(fig,*a,**k):
            capturas.append(fig)
            return original(fig,*a,**k)
        with patch.object(QFileDialog,'getExistingDirectory',return_value=str(self.pasta)),patch.object(Figure,'write_html',salvar):
            vel.exportar_html()
        self.assertEqual(len(capturas),1)
        for eixo in ('xaxis','xaxis2','xaxis3'):
            ax=getattr(capturas[0].layout,eixo)
            self.assertEqual(ax.type,'date')
            self.assertTrue(ax.showticklabels)
            self.assertEqual(list(ax.range),['2026-11-11T12:40:00.000000','2026-11-11T13:00:00.000000'])
        self.assertTrue(list(self.pasta.glob('*.html')))

    def test_fft_csv_nao_confunde_hz_com_tempo_e_origem_preservada(self):
        acm=self.abrir(TelaLynxAcelerometria)
        conteudo=self.arquivo.read_bytes()
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(self.arquivo),'CSV')):
            acm.exportar_csv()
        self.assertEqual(self.arquivo.read_bytes(),conteudo)
        self.assertEqual(self.aviso.call_count,1)
        acm.botao_fft.setChecked(True)
        acm.atualizar_graficos()
        with self.assertRaisesRegex(ValueError,'FFT'):
            acm.dados_para_csv()

    def test_rms_log_preserva_zeros_lineares_no_csv(self):
        acm=self.abrir(TelaLynxAcelerometria)
        # Sinal sintético nulo; calibração não faz parte da tela de acelerometria.
        acm.df_original.loc[:, :]=0
        acm.aplicar_configuracao({})
        acm.campo_janela_rms.setValue(2)
        acm.botao_rms.setChecked(True)
        acm.checkbox_log_rms.setChecked(True)
        acm.atualizar_graficos()
        _,r=self.exportar(acm,'rms_zeros')
        self.assertTrue(np.isfinite(r.dados.to_numpy()).all())
        np.testing.assert_array_equal(r.dados,0)
        self.assertEqual(list(r.dados),[1,2,3])
        self.assertTrue(all(c['unidade']=='mg' for c in r.canais.values()))
        self.assertEqual(r.metadados['modo'],'RMS AC')
        self.assertEqual(r.metadados['janela_rms_s'],2)
