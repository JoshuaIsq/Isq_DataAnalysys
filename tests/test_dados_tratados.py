"""Abertura de CSV tratado: valores, unidades, recortes e relógio preservados."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/isq-matplotlib')

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from isq_dataanalysys.exportacao.csv_tratado import salvar_csv_tratado, ler_csv_tratado
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.interface.dados_tratados import TelaDadosTratados
from isq_dataanalysys.interface.inicial import TelaInicial


class DadosTratadosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.janelas = []
        self.addCleanup(self.fechar)
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.addCleanup(patch.stopall)
        self.tempo = np.arange(2400., 3601., 300.)
        self.dados = pd.DataFrame({1: [.03, .01, -.02, .005, 0.],
                                  7: [3., 4., -2., 1., 5.],
                                  'régua': [-7.11, -7.10, -7.08, -7.09, -7.12],
                                  22: [1.1, 1.2, 1.3, 1.2, 1.15]})
        self.canais = {1: dict(nome='Mesmo nome – Y', unidade='g', eixo='Y'),
                       7: dict(nome='Mesmo nome – Y', unidade='mm/s', eixo='Y'),
                       'régua': dict(nome='Régua', unidade='mm', eixo=''),
                       22: dict(nome='Extensômetro', unidade='MPa', eixo='')}
        self.inicio = datetime(2026,11,11,9,0)
        self.meta = dict(inicio_gravacao_s=0., intervalo_original_s=[0.,7200.],
                         intervalo_avaliacao_s=[2400.,3600.], descricao='Passa-banda 1–30 Hz; média retirada da aceleração.',
                         modalidade='ensaio_misto')
        self.caminho = Path(self.tmp.name)/'tratado.csv'
        salvar_csv_tratado(self.caminho,self.tempo,self.dados,self.canais,self.inicio,self.meta)

    def fechar(self):
        for janela in reversed(self.janelas):
            if shiboken6.isValid(janela):
                janela.close()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def abrir(self):
        janela = TelaDadosTratados()
        self.janelas.append(janela)
        janela.show()
        self.assertTrue(janela.importar_caminho(self.caminho))
        self.app.processEvents()
        return janela

    def test_reabre_valores_multiplas_unidades_sem_processar_ou_zerar_tempo(self):
        janela = self.abrir()
        np.testing.assert_array_equal(janela.tempo,self.tempo)
        pd.testing.assert_frame_equal(janela.df_sensores,self.dados)
        self.assertEqual(janela.canais,self.canais)
        self.assertEqual(janela.metadados_tratados,self.meta)
        self.assertEqual(janela.inicio_exportacao,self.inicio)
        self.assertEqual(len(janela.graficos_eixos),4)
        self.assertEqual(janela.painel_intervalo.inicio_min.value(),40.)
        self.assertEqual(janela.painel_intervalo.fim_min.value(),60.)
        for c,curva in janela.curvas.items():
            x,y = curva.getOriginalDataset()
            np.testing.assert_array_equal(x,self.tempo)
            np.testing.assert_array_equal(y,self.dados[c])
        for (unidade,_),plot in janela.graficos_eixos.items():
            self.assertEqual(plot.getAxis('left').labelUnits,unidade)
            self.assertEqual(plot.getAxis('bottom').tickStrings([2400],1,1),['11/11/2026 06:40:00'])
        figura = criar_figura_html(janela.plots_para_exportar(),inicio=janela.inicio_exportacao)
        self.assertEqual(figura.layout.xaxis.type,'date')
        self.assertEqual(figura.data[0].x[0],'2026-11-11T06:40:00.000000')
        self.aviso.assert_not_called()

    def test_recorte_e_reexportacao_reabertura_conservam_relogio_e_canais(self):
        janela = self.abrir()
        original = janela.df_sensores.copy(deep=True)
        janela.painel_intervalo.definir_intervalo_segundos(2700.,3300.)
        janela.checkboxes_canais[7].setChecked(False)
        janela.checkboxes_canais[22].setChecked(False)
        self.app.processEvents()
        for plot in janela.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange()[0],[2700.,3300.],atol=1e-8)
        saida = Path(self.tmp.name)/'recorte.csv'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(saida),'')), \
                patch.object(QMessageBox,'information'):
            janela.exportar_csv()
        arquivo = ler_csv_tratado(saida)
        self.assertEqual(list(arquivo.dados),[1,'régua'])
        np.testing.assert_array_equal(arquivo.tempo,[2700.,3000.,3300.])
        pd.testing.assert_frame_equal(arquivo.dados,self.dados.loc[1:3,[1,'régua']].reset_index(drop=True))
        self.assertEqual(arquivo.inicio_csv,self.inicio)
        self.assertEqual(arquivo.metadados['inicio_gravacao_s'],0.)
        self.assertEqual(arquivo.metadados['intervalo_original_s'],[0.,7200.])
        self.assertEqual(arquivo.metadados['intervalo_avaliacao_s'],[2700.,3300.])
        pd.testing.assert_frame_equal(janela.df_sensores,original)
        outra = TelaDadosTratados()
        self.janelas.append(outra)
        outra.show()
        self.assertTrue(outra.importar_caminho(saida))
        self.assertEqual(outra.painel_intervalo.inicio_min.value(),45.)
        self.assertEqual(outra.painel_intervalo.fim_min.value(),55.)
        plot = next(iter(outra.graficos_eixos.values()))
        self.assertEqual(plot.getAxis('bottom').tickStrings([2700],1,1),['11/11/2026 06:45:00'])
        self.aviso.assert_not_called()

    def test_importacao_invalida_preserva_janela_atual_e_metadados(self):
        janela = self.abrir()
        dados = janela.df_sensores.copy(deep=True)
        ruim = Path(self.tmp.name)/'invalido.csv'
        ruim.write_text('Não é um CSV tratado.',encoding='utf-8')
        self.assertFalse(janela.importar_caminho(ruim))
        pd.testing.assert_frame_equal(janela.df_sensores,dados)
        self.assertEqual(janela.caminho_atual,self.caminho)
        self.assertEqual(self.aviso.call_count,1)
        salvar_csv_tratado(ruim,self.tempo,self.dados,self.canais,self.inicio,
                           dict(self.meta,inicio_gravacao_s='inválido'))
        self.assertFalse(janela.importar_caminho(ruim))
        pd.testing.assert_frame_equal(janela.df_sensores,dados)
        self.assertEqual(self.aviso.call_count,2)

    def test_sem_data_uma_amostra_e_dialogo_cancelado(self):
        caminho = Path(self.tmp.name)/'uma_amostra.csv'
        salvar_csv_tratado(caminho,[3000.],pd.DataFrame({'a':[1.]}),
                           {'a':dict(nome='Um canal',unidade='mm',eixo='')})
        janela = TelaDadosTratados()
        self.janelas.append(janela)
        janela.show()
        self.assertTrue(janela.importar_caminho(caminho))
        self.assertIsNone(janela.inicio_exportacao)
        self.assertFalse(janela.painel_intervalo.isEnabled())
        self.assertEqual(janela.painel_intervalo.inicio_min.value(),50.)
        with patch.object(QFileDialog,'getOpenFileName',return_value=('','')):
            self.assertFalse(janela.abrir_arquivo())
        self.assertEqual(janela.df_sensores.iloc[0,0],1.)

    def test_reabrir_outro_csv_na_mesma_janela_limpa_grupos_anteriores(self):
        janela = self.abrir()
        vinculo_anterior = janela.vinculo_intervalos
        caminho = Path(self.tmp.name)/'outro.csv'
        dados = pd.DataFrame({9:[1.,2.,3.]})
        salvar_csv_tratado(caminho,[3000.,3060.,3120.],dados,
                           {9:dict(nome='Velocidade nova',unidade='mm/s',eixo='X')})
        self.assertTrue(janela.importar_caminho(caminho))
        self.app.processEvents()
        self.assertEqual(vinculo_anterior.plots,[])
        self.assertEqual(list(janela.curvas),[9])
        self.assertEqual(list(janela.checkboxes_canais),[9])
        self.assertEqual(len(janela.graficos_eixos),1)
        pd.testing.assert_frame_equal(janela.df_sensores,dados)
        self.assertIsNone(janela.inicio_exportacao)
        self.assertEqual(janela.painel_intervalo.inicio_min.value(),50.)
        self.assertEqual(janela.painel_intervalo.fim_min.value(),52.)
        np.testing.assert_allclose(next(iter(janela.graficos_eixos.values())).viewRange()[0],[3000.,3120.])

    def test_entrada_inicial_abre_janelas_independentes(self):
        inicial = TelaInicial()
        self.janelas.append(inicial)
        inicial.show()
        primeira = inicial.abrir_dados_tratados()
        segunda = inicial.abrir_dados_tratados()
        self.janelas.extend([primeira,segunda])
        self.assertIsNot(primeira,segunda)
        self.assertTrue(primeira.isVisible())
        self.assertTrue(segunda.isVisible())
        self.assertTrue(primeira.importar_caminho(self.caminho))
        self.assertIsNone(segunda.df_sensores)
        primeira.close()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.assertTrue(segunda.isVisible())
        self.assertEqual(inicial.janelas_dados_tratados,[segunda])
        inicial.close()
        self.assertTrue(segunda.isVisible())


if __name__=='__main__':
    unittest.main()
