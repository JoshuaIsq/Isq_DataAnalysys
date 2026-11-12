"""Regressões de canais fora de ordem, eixos repetidos e identificação parcial."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/isq-matplotlib")

from pathlib import Path
import random
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from matplotlib.figure import Figure
from plotly.graph_objects import Figure as FiguraHtml

from tests.apoio import ArquivoMixin
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.leitores.acelerometria import EIXO_DESCONHECIDO, ler_lynx_acelerometria
from isq_dataanalysys.leitores.extensometria import ler_lynx_extensometria
from isq_dataanalysys.processamento.integracao import integrar_relativo


def caso_imagem():
    nomes = [f"ACC {sensor} - {eixo}" for sensor in (92128, 92129) for eixo in "XYZ"]
    nomes += [f"Channel {n}" for n in range(7, 14)]
    nomes += ["ACC 92131 - Y", "ACC 92131 - Y", "Channel 16"]
    return ["g"] * 6 + ["µm/m"] * 7 + ["g", "g", "µm/m"], nomes


class LeituraCanaisTests(ArquivoMixin, unittest.TestCase):
    def test_reproduz_imagem_oito_canais_e_dois_y_iguais(self):
        unidades, nomes = caso_imagem()
        caminho = self.arquivo(unidades, nomes=nomes, encoding="cp1252")
        original = caminho.read_bytes()
        tempo, dados, sensores, info = ler_lynx_acelerometria(caminho)
        self.assertEqual(list(dados), [1, 2, 3, 4, 5, 6, 14, 15])
        self.assertEqual(sensores, [
            {"X": 1, "Y": 2, "Z": 3}, {"X": 4, "Y": 5, "Z": 6}, {"Y": 14}, {"Y": 15},
        ])
        self.assertEqual(info["nomes"][14], info["nomes"][15])
        self.assertEqual(info["eixos"][14], "Y")
        self.assertEqual(info["eixos"][15], "Y")
        self.assertTrue(any("repetido nos canais 14 e 15" in aviso for aviso in info["avisos"]))
        for canal in dados:
            np.testing.assert_allclose(dados[canal], canal * np.sin(2 * np.pi * 50 * tempo), atol=1e-9)
        self.assertEqual(caminho.read_bytes(), original)

    def test_permutacoes_e_unidades_intercaladas_preservam_cada_coluna(self):
        canais = [("g", f"ACC {sensor} - {eixo}", eixo) for sensor in (1, 2, 3) for eixo in "XYZ"]
        canais += [("MPa", "Tensão", None), ("µm/m", "Deformação", None)]
        sorteio = random.Random(20261105)
        for _ in range(20):
            sorteio.shuffle(canais)
            unidades, nomes, eixos = zip(*canais)
            _, dados, sensores, info = ler_lynx_acelerometria(self.arquivo(list(unidades), list(nomes)))
            esperados = {p: eixo for p, eixo in enumerate(eixos, 1) if eixo is not None}
            self.assertEqual(info["eixos"], esperados)
            self.assertEqual(list(dados), list(esperados))
            self.assertEqual(sorted(p for sensor in sensores for p in sensor.values()), sorted(esperados))
            for sensor in sensores:
                self.assertEqual(set(sensor), set("XYZ"))
                self.assertEqual(len({nomes[p - 1].split(" - ")[0] for p in sensor.values()}), 1)

    def test_eixo_repetido_em_quantidade_multipla_de_tres_nao_vira_xyz(self):
        for quantidade in (2, 3, 6, 8):
            with self.subTest(quantidade=quantidade):
                _, dados, sensores, info = ler_lynx_acelerometria(
                    self.arquivo(["g"] * quantidade, ["ACC 1 - Y"] * quantidade)
                )
                self.assertEqual(len(dados.columns), quantidade)
                self.assertEqual(sensores, [{"Y": n} for n in range(1, quantidade + 1)])
                self.assertEqual(set(info["origem_eixos"].values()), {"nome"})

    def test_canais_sem_eixo_em_qualquer_quantidade_incompleta(self):
        for quantidade in (1, 2, 4, 5, 7, 8):
            with self.subTest(quantidade=quantidade):
                _, dados, sensores, info = ler_lynx_acelerometria(self.arquivo(["g"] * quantidade))
                self.assertEqual(len(dados.columns), quantidade)
                self.assertEqual(sensores, [{EIXO_DESCONHECIDO: n} for n in range(1, quantidade + 1)])
                self.assertEqual(set(info["origem_eixos"].values()), {"não identificado"})

    def test_identificacao_parcial_nao_descarta_os_eixos_conhecidos(self):
        _, _, sensores, info = ler_lynx_acelerometria(self.arquivo(
            ["g"] * 6, ["ACC 1 - Y", "Channel 2", "ACC 1 - X", "XYZ", "ACC X Y", "Aux"],
        ))
        self.assertEqual(info["eixos"], {1: "Y", 2: EIXO_DESCONHECIDO, 3: "X",
                                         4: EIXO_DESCONHECIDO, 5: EIXO_DESCONHECIDO, 6: EIXO_DESCONHECIDO})
        self.assertEqual(sensores[0], {"Y": 1, "X": 3})
        self.assertNotIn("posição", info["origem_eixos"].values())

    def test_variantes_de_nome_eixo_prefixado_e_sufixo_de_unidade(self):
        nomes = ["ACC_1_x", "ACC 1 [Y]", "ACC 1 - Eixo Z (g)", "Y - ACC 2", "ACC 2 - X [g]",
                 "ACC3Z", "ACC3X", "ACC3Y"]
        _, _, sensores, info = ler_lynx_acelerometria(self.arquivo(["g"] * len(nomes), nomes))
        self.assertEqual(sensores, [{"X": 1, "Y": 2, "Z": 3}, {"Y": 4, "X": 5}, {"Z": 6, "X": 7, "Y": 8}])
        self.assertEqual(info["eixos"], {1: "X", 2: "Y", 3: "Z", 4: "Y", 5: "X", 6: "Z", 7: "X", 8: "Y"})

    def test_nomes_com_eixos_conflitantes_nao_acionam_inferencia_posicional(self):
        _, _, sensores, info = ler_lynx_acelerometria(self.arquivo(
            ["g"] * 3, ["ACC X Y", "Sensor Z/X", "Y ou Z"],
        ))
        self.assertEqual(sensores, [{EIXO_DESCONHECIDO: n} for n in range(1, 4)])
        self.assertNotIn("posição", info["origem_eixos"].values())

    def test_padrao_legado_so_sem_eixos_reconhecidos_e_com_aviso(self):
        _, _, sensores, info = ler_lynx_acelerometria(self.arquivo(["g"] * 6))
        self.assertEqual(sensores, [{"X": 1, "Y": 2, "Z": 3}, {"X": 4, "Y": 5, "Z": 6}])
        self.assertEqual(set(info["origem_eixos"].values()), {"posição"})
        self.assertTrue(any("associação é inferida" in aviso for aviso in info["avisos"]))

    def test_nome_vazio_no_meio_nao_trunca_as_colunas_seguintes(self):
        caminho = self.arquivo(["g"] * 4, ["ACC 1 X", "   ", "ACC 1 Z", "ACC 2 Y"])
        original = caminho.read_bytes()
        _, dados, sensores, info = ler_lynx_acelerometria(caminho)
        self.assertEqual(list(dados), [1, 2, 3, 4])
        self.assertEqual(info["eixos"], {1: "X", 2: EIXO_DESCONHECIDO, 3: "Z", 4: "Y"})
        self.assertEqual(info["nomes"][2], "Canal 2 (sem nome)")
        self.assertEqual(sorted(p for sensor in sensores for p in sensor.values()), [1, 2, 3, 4])
        self.assertTrue(any("nome vazio" in aviso for aviso in info["avisos"]))
        self.assertEqual(caminho.read_bytes(), original)

    def test_nome_vazio_no_ultimo_canal_com_unidade_nao_e_separador(self):
        for leitor, unidades in ((ler_lynx_acelerometria, ["g"] * 2),
                                 (ler_lynx_extensometria, ["MPa"] * 2)):
            with self.subTest(leitor=leitor.__name__):
                _, dados, _, info = leitor(self.arquivo(unidades, ["Medição", ""]))
                self.assertEqual(list(dados), [1, 2])
                self.assertEqual(info["nomes"][2], "Canal 2 (sem nome)")


class InterfaceCanaisTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas = []
        self.erros_qt = []
        self.addCleanup(lambda: self.assertEqual(self.erros_qt, []))
        patch("sys.excepthook", lambda tipo, erro, tb: self.erros_qt.append(str(erro))).start()
        self.aviso = patch.object(QMessageBox, "warning").start()
        patch.object(QMessageBox, "information").start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            janela.close()
            janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def tela(self, unidades, nomes=None):
        tela = TelaLynxAcelerometria()
        self.janelas.append(tela)
        tela.resize(1330, 700)
        tela.show()
        self.assertTrue(tela.importar_caminho(self.arquivo(unidades, nomes)))
        self.app.processEvents()
        return tela

    def verificar_curvas(self, tela):
        encontrados = []
        for (numero, eixo), curva in tela.curvas_lynx.items():
            canal = tela.sensores_lynx[numero - 1][eixo]
            encontrados.append(canal)
            self.assertTrue(curva.isVisible())
            np.testing.assert_array_equal(curva.getOriginalDataset()[1], tela.df_sensores[canal])
        self.assertEqual(sorted(encontrados), sorted(tela.df_sensores.columns))

    def exportar_e_conferir(self, janela, esperados):
        salvar_svg, salvar_html = Figure.savefig, FiguraHtml.write_html
        chamadas = []

        def verificar_svg(figura, *args, **kwargs):
            linhas = [linha for eixo in figura.axes for linha in eixo.lines]
            self.assertEqual(len(linhas), len(esperados))
            self.assertEqual({linha.get_label().split(" — ")[0] for linha in linhas},
                             {f"Canal {n}" for n in esperados})
            for linha in linhas:
                canal = int(linha.get_label().split(" — ")[0].split()[-1])
                np.testing.assert_array_equal(linha.get_ydata(), janela.df_sensores[canal])
            chamadas.append("svg")
            return salvar_svg(figura, *args, **kwargs)

        def verificar_html(figura, *args, **kwargs):
            self.assertEqual(len(figura.data), len(esperados))
            for curva in figura.data:
                canal = int(curva.name.split(" — ")[0].split()[-1])
                self.assertIn(canal, esperados)
                np.testing.assert_array_equal(curva.y, janela.df_sensores[canal])
            chamadas.append("html")
            return salvar_html(figura, *args, **kwargs)

        with patch.object(QFileDialog, "getExistingDirectory", return_value=self.tmp.name), \
                patch.object(Figure, "savefig", verificar_svg), \
                patch.object(FiguraHtml, "write_html", verificar_html):
            janela.exportar_svg()
            janela.exportar_html()
        self.assertEqual(chamadas, ["svg", "html"])

    def test_imagem_oito_canais_ate_velocidade_deslocamento_e_exportacoes(self):
        acm = self.tela(*caso_imagem())
        self.verificar_curvas(acm)
        self.assertEqual(len(acm.curvas_lynx), 8)
        self.assertIn("repetido", acm.rotulo_importacao.toolTip())
        self.assertTrue(acm.rotulo_importacao.isVisible())
        original = acm.df_original.copy(deep=True)
        self.assertTrue(acm.aplicar_configuracao({"passa_banda": (30, 100)}))
        self.verificar_curvas(acm)
        acm.botao_fft.click()
        acm.botao_velocidade.click()
        vel = acm.janelas_resultados[-1]
        self.janelas.append(vel)
        self.assertEqual(list(vel.df_sensores), [1, 2, 3, 4, 5, 6, 14, 15])
        entrada = acm.df_sensores.subtract(acm.df_sensores.mean(), axis='columns')
        np.testing.assert_allclose(vel.df_sensores, integrar_relativo(acm.tempo, entrada, "aceleracao"), atol=1e-9)
        self.assertEqual(vel.canais[14][0], "Y")
        self.assertEqual(vel.canais[15][0], "Y")
        vel.botao_deslocamento.click()
        desp = vel.janelas_resultados[-1]
        self.janelas.append(desp)
        self.app.processEvents()
        pd.testing.assert_frame_equal(desp.df_deslocamento_integrado, integrar_relativo(vel.tempo, vel.df_sensores, "velocidade"))
        self.assertTrue(all(janela.isVisible() for janela in (acm, vel, desp)))
        pd.testing.assert_frame_equal(acm.df_original, original)
        # Seleção dos dois Y com o mesmo nome, mantendo seus dados independentes.
        acm.botao_fft.click()
        for (numero, eixo), checkbox in acm.checkboxes_eixos.items():
            checkbox.setChecked(acm.sensores_lynx[numero - 1][eixo] in (14, 15))
        for janela in (vel, desp):
            for canal, checkbox in janela.checkboxes_canais.items():
                checkbox.setChecked(canal in (14, 15))
        for janela in (acm, vel, desp):
            self.exportar_e_conferir(janela, (14, 15))
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.svg"))), 3)
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.html"))), 3)

    def test_sem_eixo_plota_filtra_integra_e_exporta_sem_inventar_xyz(self):
        acm = self.tela(["g"] * 4)
        self.verificar_curvas(acm)
        self.assertTrue(acm.graficos_eixos[EIXO_DESCONHECIDO].isVisible())
        self.assertTrue(all(not acm.graficos_eixos[eixo].isVisible() for eixo in "XYZ"))
        self.assertEqual(len(acm.plots_para_exportar()), 1)
        self.assertTrue(acm.aplicar_configuracao({"passa_banda": (30, 100)}))
        self.verificar_curvas(acm)
        acm.botao_rms.click()
        self.assertEqual(len(acm.curvas_lynx), 4)
        acm.botao_velocidade.click()
        vel = acm.janelas_resultados[-1]
        self.janelas.append(vel)
        self.assertEqual({eixo for eixo, _ in vel.canais.values()}, {EIXO_DESCONHECIDO})
        self.assertEqual(vel.graficos_eixos[EIXO_DESCONHECIDO].getAxis("left").labelUnits, "mm/s")
        vel.botao_deslocamento.click()
        desp = vel.janelas_resultados[-1]
        self.janelas.append(desp)
        self.assertEqual(desp.graficos_eixos[EIXO_DESCONHECIDO].getAxis("left").labelUnits, "mm")
        self.assertTrue(np.all(vel.df_sensores.iloc[0] == 0))
        self.assertTrue(np.all(desp.df_deslocamento_integrado.iloc[0] == 0))
        np.testing.assert_allclose(desp.df_sensores.iloc[0],-desp.ajustes_rampa['intercepto_mm'],atol=1e-10)
        acm.botao_rms.click()
        for janela in (acm, vel, desp):
            self.assertEqual(len(janela.plots_para_exportar()), 1)
            self.exportar_e_conferir(janela, (1, 2, 3, 4))
        self.aviso.assert_not_called()

    def test_y_isolado_reimportacao_e_selecao_nao_deixam_curvas_antigas(self):
        acm = self.tela(["g"], ["ACC 1 - Y"])
        self.verificar_curvas(acm)
        self.assertEqual([e for e, plot in acm.graficos_eixos.items() if plot.isVisible()], ["Y"])
        vel_y = acm.gerar_velocidade()
        self.janelas.append(vel_y)
        self.assertEqual(list(vel_y.graficos_eixos), ["Y"])
        self.assertEqual(vel_y.canais[1][0], "Y")
        self.assertTrue(acm.importar_caminho(self.arquivo(["g"] * 4)))
        self.assertEqual(len(acm.curvas_lynx), 4)
        acm.checkboxes_canais[2].setChecked(False)
        self.assertFalse(acm.curvas_lynx[(2, EIXO_DESCONHECIDO)].isVisible())
        self.assertTrue(acm.importar_caminho(self.arquivo(["g"] * 3, ["ACC 2 - Z", "ACC 2 - X", "ACC 2 - Y"])))
        self.verificar_curvas(acm)
        self.assertFalse(acm.graficos_eixos[EIXO_DESCONHECIDO].isVisible())
        self.assertEqual(len(acm.plots_para_exportar()), 3)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        self.assertEqual(list(vel.df_sensores), [1, 2, 3])
        self.assertEqual({c: e for c, (e, _) in vel.canais.items()}, {1: "Z", 2: "X", 3: "Y"})
        self.aviso.assert_not_called()


if __name__ == "__main__":
    unittest.main()
