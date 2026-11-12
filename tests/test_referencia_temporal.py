"""Cabeçalhos variantes, diagnóstico visível e ajuste explícito da referência."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/isq-matplotlib")

from datetime import datetime
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from tests.apoio import ArquivoMixin
from isq_dataanalysys.leitores.metadados import ler_referencia_temporal, interpretar_data_hora
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.extensometria import TelaLynxExtensometria
from isq_dataanalysys.exportacao.html import criar_figura_html


class CabecalhoHorarioTests(ArquivoMixin, unittest.TestCase):
    def test_variacoes_da_etiqueta_que_antes_retornavam_vazio(self):
        for etiqueta in ("StartTime (UTC+00:00):", "StartTime (UTC-0):", "StartTimeUTC0:",
                         "StartTime UTC (yyyy/mm/dd hh:mm:ss):", "StartTime [UTC]:"):
            with self.subTest(etiqueta=etiqueta):
                caminho = self.arquivo(["MPa"], alterar=lambda l: l[1].__setitem__(slice(-2, None),
                                       [etiqueta, "27/10/2026 14:45"]))
                original = caminho.read_bytes()
                info = ler_referencia_temporal(caminho)
                self.assertEqual(info["inicio"], datetime(2026, 10, 27, 14, 45))
                self.assertEqual(info["etiqueta"], etiqueta)
                self.assertEqual(info["valor"], "27/10/2026 14:45")
                self.assertEqual(info["erro"], "")
                self.assertEqual(caminho.read_bytes(), original)

    def test_valores_com_precisao_extra_separadores_e_anotacoes(self):
        casos = [
            ("2026/10/27-14:45:01.123456789", datetime(2026, 10, 27, 14, 45, 1, 123456)),
            ("2026-10-27T14:45:01.123456789Z", datetime(2026, 10, 27, 14, 45, 1, 123456)),
            ("27/10/2026 14:45:01,1234567", datetime(2026, 10, 27, 14, 45, 1, 123456)),
            ("27.10.2026 14:45", datetime(2026, 10, 27, 14, 45)),
            ("'27/10/2026\u00a014:45", datetime(2026, 10, 27, 14, 45)),
            ("2026-10-27T14:45:00+01:00", datetime(2026, 10, 27, 14, 45)),
            ("27/10/2026 14:45:00 UTC", datetime(2026, 10, 27, 14, 45)),
        ]
        for valor, esperado in casos:
            with self.subTest(valor=valor):
                self.assertEqual(interpretar_data_hora(valor), esperado)

    def test_celulas_vazias_data_hora_separadas_e_valor_embutido(self):
        for celulas in (["StartTime UTC:", "", "27/10/2026 14:45"],
                        ["StartTime UTC:", "27/10/2026", "14:45:00"],
                        ["StartTime: 27/10/2026 14:45:00"],
                        ["StartTime (UTC+0): 27/10/2026 14:45:00"]):
            with self.subTest(celulas=celulas):
                caminho = self.arquivo(["MPa"], alterar=lambda l: l[1].__setitem__(slice(-2, None), celulas))
                self.assertEqual(ler_referencia_temporal(caminho)["inicio"], datetime(2026, 10, 27, 14, 45))

    def test_falha_tem_motivo_e_valor_original_sem_inventar_data(self):
        for valor in ("31/02/2026 14:45", "sem data", "46322,5", "27/10/2026"):
            with self.subTest(valor=valor):
                caminho = self.arquivo(["MPa"], alterar=lambda l: l[1].__setitem__(-1, valor))
                info = ler_referencia_temporal(caminho)
                self.assertIsNone(info["inicio"])
                self.assertEqual(info["valor"], valor)
                self.assertIn("encontrado", info["erro"])
        caminho = self.arquivo(["MPa"], alterar=lambda l: l[1].__setitem__(-2, "Outro campo"))
        self.assertIn("não encontrado", ler_referencia_temporal(caminho)["erro"])


class PainelHorarioTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas = []
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

    def abrir(self, classe, horario):
        janela = classe()
        self.janelas.append(janela)
        janela.show()
        caminho = self.arquivo(["g"] * 3 if classe is TelaLynxAcelerometria else ["MPa"],
                               alterar=lambda l: l[1].__setitem__(slice(-2, None), horario))
        self.assertTrue(janela.importar_caminho(caminho))
        self.app.processEvents()
        return janela

    def test_identificacao_automatica_nas_duas_modalidades_e_detalhes_copiaveis(self):
        for classe in (TelaLynxAcelerometria, TelaLynxExtensometria):
            janela = self.abrir(classe, ["StartTime (UTC+0):", "27/10/2026 14:45:00.123456789"])
            self.assertTrue(janela.painel_referencia.isVisible())
            self.assertIn("27/10/2026 11:45:00", janela.painel_referencia.rotulo.text())
            self.assertIn("27/10/2026 14:45:00", janela.painel_referencia.rotulo.text())
            if classe is TelaLynxAcelerometria:
                janela.painel_referencia.botao_detalhes.click()
                self.assertIn("123456789", self.informacao.call_args.args[2])
            else:
                self.assertFalse(hasattr(janela.painel_referencia, "botao_detalhes"))
                self.assertFalse(hasattr(janela.painel_referencia, "botao_definir"))
            figura = criar_figura_html(janela.plots_para_exportar())
            self.assertEqual(figura.data[0].x[0], "2026-10-27T11:45:00.123456")

    def test_horario_manual_atualiza_tela_html_svg_e_novas_integracoes(self):
        for classe in (TelaLynxAcelerometria,):
            janela = self.abrir(classe, ["StartTime UTC:", "formato desconhecido"])
            self.assertIn("não reconhecida", janela.painel_referencia.rotulo.text())
            self.assertIn("formato desconhecido", janela.painel_referencia.detalhes())
            original = janela.df_sensores.copy(deep=True)
            tempo = janela.tempo.copy()
            arquivo = janela.caminho_atual.read_bytes()
            plots = janela.plots_para_exportar()
            plots[0].setXRange(.2, .8, padding=0)
            self.app.processEvents()
            faixas = [plot.viewRange() for plot in plots]
            with patch.object(QInputDialog, "getText", return_value=("27/10/2026 14:45:00", True)):
                janela.painel_referencia.botao_definir.click()
            for plot, faixa in zip(plots, faixas):
                np.testing.assert_allclose(plot.viewRange(), faixa)
            self.assertEqual(janela.inicio_arquivo, datetime(2026, 10, 27, 14, 45))
            for plot in janela.plots_para_exportar():
                self.assertEqual(plot.getAxis("bottom").tickStrings([0], 1, 1), ["27/10/2026 11:45:00"])
            self.assertEqual(janela.caminho_atual.read_bytes(), arquivo)
            pd.testing.assert_frame_equal(janela.df_sensores, original)
            np.testing.assert_array_equal(janela.tempo, tempo)
            resultados = [janela]
            if classe is TelaLynxAcelerometria:
                vel = janela.gerar_velocidade()
                desp = vel.gerar_deslocamento()
                self.janelas.extend([vel, desp])
                resultados.extend([vel, desp])
            for resultado in resultados:
                figura = criar_figura_html(resultado.plots_para_exportar())
                self.assertEqual(figura.data[0].x[0], "2026-10-27T11:45:00.000000")
                salvar = Figure.savefig
                chamadas = []
                def conferir(figura, *args, **kwargs):
                    self.assertEqual(str(figura.axes[0].lines[0].get_xdata()[0]), "2026-10-27T11:45:00.000000")
                    chamadas.append(True)
                    return salvar(figura, *args, **kwargs)
                with patch.object(QFileDialog, "getExistingDirectory", return_value=self.tmp.name), \
                        patch.object(Figure, "savefig", conferir):
                    resultado.exportar_svg()
                    resultado.exportar_html()
                self.assertEqual(chamadas, [True])
            self.aviso.assert_not_called()

    def test_cancelar_ou_informar_data_invalida_preserva_referencia_e_dados(self):
        janela = self.abrir(TelaLynxAcelerometria, ["StartTime UTC:", "27/10/2026 14:45"])
        original = janela.df_sensores.copy(deep=True)
        info = janela.painel_referencia.info.copy()
        for retorno in (("", False), ("31/02/2026 14:45", True)):
            with patch.object(QInputDialog, "getText", return_value=retorno):
                janela.painel_referencia.botao_definir.click()
            self.assertEqual(janela.painel_referencia.info, info)
            self.assertEqual(janela.inicio_arquivo, info["inicio"])
            pd.testing.assert_frame_equal(janela.df_sensores, original)
        self.aviso.assert_called_once()

    def test_definir_horario_em_fft_preserva_frequencias_e_aplica_ao_voltar(self):
        janela = self.abrir(TelaLynxAcelerometria, ["StartTime UTC:", "sem data"])
        janela.botao_fft.click()
        x, y = (a.copy() for a in janela.curvas_lynx[(1, "X")].getOriginalDataset())
        with patch.object(QInputDialog, "getText", return_value=("27/10/2026 14:45", True)):
            janela.painel_referencia.botao_definir.click()
        self.assertTrue(janela.botao_fft.isChecked())
        self.assertEqual(janela.graficos_eixos["X"].getAxis("bottom").labelUnits, "Hz")
        for antes, depois in zip((x, y), janela.curvas_lynx[(1, "X")].getOriginalDataset()):
            np.testing.assert_array_equal(antes, depois)
        janela.botao_fft.click()
        self.assertEqual(janela.graficos_eixos["X"].getAxis("bottom").tickStrings([0], 1, 1), ["27/10/2026 11:45:00"])


if __name__ == "__main__":
    unittest.main()
