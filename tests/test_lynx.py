"""Regressões de importação e interface com CSVs sintéticos, sem monitor."""
import codecs
from datetime import datetime
import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/isq-matplotlib')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/isq-cache')

import numpy as np
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
import shiboken6
from tests.apoio import ArquivoMixin

from isq_dataanalysys.leitores.lynx import LinhaFinalIncompleta
from isq_dataanalysys.leitores.codificacao import detectar_codificacao_csv
from isq_dataanalysys.leitores.acelerometria import ler_lynx_acelerometria
from isq_dataanalysys.leitores.extensometria import ler_lynx_extensometria
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.extensometria import TelaLynxExtensometria
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.leitores.metadados import ler_inicio_lynx




class LeituraTests(ArquivoMixin, unittest.TestCase):
    def test_codificacoes_preservam_nomes_unidades_e_arquivo(self):
        for encoding in ('cp1252', 'utf-8', 'utf-8-sig', 'utf-16'):
            with self.subTest(encoding=encoding):
                caminho = self.arquivo(['MPa', 'µm/m', 'g', 'g', 'g'],
                                       nomes=['Tensão', 'Deformação — µ', 'Aceleração X', 'Aceleração Y', 'Aceleração Z'],
                                       encoding=encoding)
                original = caminho.read_bytes()
                if encoding == 'cp1252':
                    self.assertIn(b'\xb5', original)
                    with self.assertRaises(UnicodeDecodeError):
                        original.decode('utf-8')
                _, dados, mapa, info = ler_lynx_extensometria(caminho)
                self.assertEqual(list(dados), [1, 2])
                self.assertEqual(mapa[1], 'Tensão')
                self.assertEqual(mapa[2], 'Deformação — µ')
                self.assertEqual(info['unidades'][2], 'μm/m')
                _, acm, sensores, _ = ler_lynx_acelerometria(caminho)
                self.assertEqual(list(acm), [3, 4, 5])
                self.assertEqual(sensores, [{'X': 3, 'Y': 4, 'Z': 5}])
                self.assertEqual(ler_inicio_lynx(caminho), datetime(2026, 10, 28, 12))
                self.assertEqual(caminho.read_bytes(), original)

    def test_utf16_big_endian_com_bom(self):
        caminho = self.arquivo(['μm/m'], nomes=['Deformação'], encoding='utf-8')
        caminho.write_bytes(codecs.BOM_UTF16_BE + caminho.read_text(encoding='utf-8').encode('utf-16-be'))
        _, _, mapa, info = ler_lynx_extensometria(caminho)
        self.assertEqual(mapa[1], 'Deformação')
        self.assertEqual(info['unidade'], 'μm/m')

    def test_codificacao_e_validada_alem_do_primeiro_bloco(self):
        caminho = Path(self.tmp.name) / 'blocos.csv'
        caminho.write_bytes(b'a' * 65535 + 'µ'.encode('utf-8'))
        self.assertEqual(detectar_codificacao_csv(caminho), 'utf-8')
        caminho.write_bytes(b'a' * 65536 + b'\xb5')
        self.assertEqual(detectar_codificacao_csv(caminho), 'cp1252')

    def test_exemplo_da_imagem_e_posicoes_originais(self):
        caminho = self.arquivo(['g'] * 6 + ['μm/m'] * 7 + ['mm'])
        original = caminho.read_bytes()
        tempo, dados, mapa, info = ler_lynx_extensometria(caminho)
        self.assertEqual(list(dados), list(range(7, 14)))
        self.assertEqual(mapa[7], 'Sensor livre 7')
        self.assertEqual([c['posicao'] for c in info['ignorados']], list(range(1, 7)) + [14])
        self.assertAlmostEqual(info['fs'], 1000)
        _, acm, sensores, _ = ler_lynx_acelerometria(caminho)
        self.assertEqual(list(acm), list(range(1, 7)))
        self.assertEqual(sensores, [{'X': 1, 'Y': 2, 'Z': 3}, {'X': 4, 'Y': 5, 'Z': 6}])
        self.assertEqual(caminho.read_bytes(), original)
        self.assertEqual(len(tempo), 1000)

    def test_nomes_repetidos_ou_channel_nao_definem_identidade(self):
        _, dados, mapa, _ = ler_lynx_extensometria(self.arquivo(['MPa'] * 3, ['igual', 'igual', 'Channel 99']))
        self.assertEqual(list(dados), [1, 2, 3])
        self.assertEqual(mapa, {1: 'igual', 2: 'igual', 3: 'Channel 99'})
        np.testing.assert_allclose(dados[2], dados[1] * 2, atol=2e-9)

    def test_variacoes_de_unidade_e_decimal(self):
        for decimal in (',', '.'):
            with self.subTest(decimal=decimal):
                _, dados, _, info = ler_lynx_extensometria(self.arquivo([' mPa ', 'µm/m', 'μm/m', 'um/m', 'mm/m', 'G', 'MM', ''], decimal=decimal))
                self.assertEqual(list(dados), [1, 2, 3, 4, 5])
                self.assertEqual(list(info['unidades'].values()), ['MPa', 'μm/m', 'μm/m', 'μm/m', 'mm/m'])

    def test_acelerometros_em_quantidade_variavel(self):
        for quantidade in (3, 6, 12, 15):
            with self.subTest(quantidade=quantidade):
                _, dados, sensores, _ = ler_lynx_acelerometria(self.arquivo([' G '] * quantidade))
                self.assertEqual(len(sensores), quantidade // 3)
                self.assertEqual(len(dados.columns), quantidade)

    def test_ordem_xyz_entre_canais_selecionados(self):
        _, _, sensores, _ = ler_lynx_acelerometria(self.arquivo(['MPa', 'g', 'μm/m', 'g', 'g', 'mm']))
        self.assertEqual(sensores, [{'X': 2, 'Y': 4, 'Z': 5}])

    def test_trio_incompleto_importa_sem_adivinhar_eixo(self):
        _, dados, sensores, info = ler_lynx_acelerometria(self.arquivo(['g'] * 4 + ['MPa']))
        self.assertEqual(list(dados), [1, 2, 3, 4])
        self.assertEqual(sensores, [{'Sem eixo': n} for n in range(1, 5)])
        self.assertTrue(all(eixo == 'Sem eixo' for eixo in info['eixos'].values()))
        self.assertTrue(any('eixo não identificado' in aviso for aviso in info['avisos']))

    def test_nenhum_canal_compativel(self):
        for leitor in (ler_lynx_extensometria, ler_lynx_acelerometria):
            with self.subTest(leitor=leitor.__name__), self.assertRaisesRegex(ValueError, 'Nenhum canal compatível'):
                leitor(self.arquivo(['mm', 'V', '']))

    def test_valores_invalidos_em_medicao_ignorada_nao_bloqueiam(self):
        def alterar(linhas):
            linhas[10][1] = 'erro'
            linhas[11][1] = ''
            linhas[2][1] = 'sem limite'
        _, dados, _, _ = ler_lynx_extensometria(self.arquivo(['g', 'MPa'], alterar=alterar))
        self.assertEqual(list(dados), [2])

    def test_erro_em_canal_selecionado_e_recusado(self):
        for valor in ('erro', 'NaN', 'inf', ''):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                ler_lynx_extensometria(self.arquivo(['MPa'], alterar=lambda linhas: linhas[10].__setitem__(1, valor)))

    def test_tempo_duplicado_invertido_irregular_e_recusado(self):
        for valor in ('0,004', '-1', '0,0041'):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                ler_lynx_extensometria(self.arquivo(['MPa'], alterar=lambda linhas: linhas[10].__setitem__(0, valor)))

    def test_ultima_linha_exige_confirmacao_nas_duas_modalidades(self):
        for unidades, leitor in ((['MPa'], ler_lynx_extensometria), (['g'] * 3, ler_lynx_acelerometria)):
            with self.subTest(unidades=unidades):
                caminho = self.arquivo(unidades, alterar=lambda linhas: linhas[-1].__setitem__(1, ''))
                with self.assertRaises(LinhaFinalIncompleta):
                    leitor(caminho)
                resultado = leitor(caminho, ignorar_ultima_incompleta=True)
                self.assertEqual(len(resultado[0]), 999)
                self.assertEqual(resultado[-1]['linhas_ignoradas'], 1)

    def test_lacuna_no_meio_nao_e_ignorada(self):
        caminho = self.arquivo(['MPa'], alterar=lambda linhas: linhas[50].__setitem__(1, ''))
        with self.assertRaisesRegex(ValueError, 'antes da última'):
            ler_lynx_extensometria(caminho, ignorar_ultima_incompleta=True)

    def test_limites_e_qualidade_por_posicao(self):
        def alterar(linhas):
            linhas[2][2] = '0,1'
            for linha in linhas[5:]:
                linha[1] = '5'
        _, _, _, info = ler_lynx_extensometria(self.arquivo(['MPa', 'μm/m'], alterar=alterar))
        self.assertIn('constante', info['qualidade'][1])
        self.assertIn('fora dos limites', info['qualidade'][2])
        for valor in ('nan', '-1000000', 'erro'):
            with self.subTest(valor=valor), self.assertRaisesRegex(ValueError, 'limites'):
                ler_lynx_extensometria(self.arquivo(['MPa'], alterar=lambda linhas: linhas[2].__setitem__(1, valor)))

    def test_frequencia_do_tempo_prevalece_sobre_metadado(self):
        def alterar(linhas):
            linhas[0][-1] = '200Hz'
        _, _, _, info = ler_lynx_extensometria(self.arquivo(['MPa'], alterar=alterar))
        self.assertEqual(info['fs_cabecalho'], 200)
        self.assertIn('Usando o tempo', info['avisos'][0])

    def test_cabecalho_e_colunas_invalidas(self):
        alteracoes = [lambda l: l[0].__setitem__(0, 'outro'),
                      lambda l: l[6].append('99'),
                      lambda l: l[1].clear(),
                      lambda l: l[2].clear()]
        for alterar in alteracoes:
            with self.subTest(alterar=alterar), self.assertRaises(ValueError):
                ler_lynx_extensometria(self.arquivo(['MPa'], alterar=alterar))

    def test_delimitador_final_vazio_aceito(self):
        def alterar(linhas):
            for linha in linhas[5:]:
                linha.append('')
        self.assertEqual(len(ler_lynx_extensometria(self.arquivo(['MPa'], alterar=alterar))[0]), 1000)


class InterfaceTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas = []
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar_janelas)

    def janela(self, classe):
        janela = classe()
        self.janelas.append(janela)
        janela.show()
        self.app.processEvents()
        return janela

    def fechar_janelas(self):
        for janela in self.janelas:
            janela.close()
            shiboken6.delete(janela)
        self.app.processEvents()

    @staticmethod
    def visiveis(janela):
        return [n for n, curva in janela.curvas_ext.items() if curva.isVisible()]

    def test_popup_e_graficos_do_arquivo_misto(self):
        caminho = self.arquivo(['g'] * 6 + ['μm/m'] * 7 + ['mm'])
        ext = self.janela(TelaLynxExtensometria)
        self.assertTrue(ext.importar_caminho(caminho))
        self.assertEqual(self.visiveis(ext), list(range(7, 14)))
        self.assertFalse(ext.botao_tensao.isEnabled())
        mensagem = self.aviso.call_args.args[2]
        self.assertIn('Canal 14 — Sensor livre 14 (mm)', mensagem)
        self.assertIn('não serão plotados nem contabilizados', mensagem)
        acm = self.janela(TelaLynxAcelerometria)
        self.assertTrue(acm.importar_caminho(caminho))
        self.assertEqual(len(acm.curvas_lynx), 6)
        self.assertEqual(len(acm.checkboxes_canais), 2)
        self.assertIn('Canal 7', self.aviso.call_args.args[2])

    def test_csv_ansi_importa_nas_duas_telas_e_exporta_html(self):
        caminho = self.arquivo(['g'] * 3 + ['µm/m'],
                               nomes=['Aceleração X', 'Aceleração Y', 'Aceleração Z', 'Deformação'],
                               encoding='cp1252')
        ext = self.janela(TelaLynxExtensometria)
        self.assertTrue(ext.importar_caminho(caminho))
        self.assertEqual(self.visiveis(ext), [4])
        self.assertEqual(ext.unidade_visual, 'μm/m')
        fig = criar_figura_html([ext.grafico.getPlotItem()], inicio=ler_inicio_lynx(caminho))
        self.assertIn('Deformação', fig.data[0].name)
        self.assertEqual(fig.layout.xaxis.type, 'date')
        acm = self.janela(TelaLynxAcelerometria)
        self.assertTrue(acm.importar_caminho(caminho))
        self.assertEqual(len(acm.curvas_lynx), 3)

    def test_modos_separam_grandezas_e_preservam_dados(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa', 'μm/m', 'mm/m']))
        original = ext.df_original.copy()
        self.assertEqual(self.visiveis(ext), [1])
        ext.botao_deformacao.click()
        ext.unidade_deformacao.setCurrentText('μm/m')
        self.assertEqual(self.visiveis(ext), [2, 3])
        legendas = [rotulo.text for _, rotulo in ext.grafico.getPlotItem().legend.items]
        self.assertEqual(len(legendas), 2)
        self.assertFalse(any('Canal 1 ' in texto for texto in legendas))
        np.testing.assert_allclose(ext.curvas_ext[3].getOriginalDataset()[1], original[3] * 1000)
        ext.unidade_deformacao.setCurrentText('mm/m')
        np.testing.assert_allclose(ext.curvas_ext[2].getOriginalDataset()[1], original[2] / 1000)
        ext.botao_tensao.click()
        self.assertEqual(self.visiveis(ext), [1])
        np.testing.assert_array_equal(ext.df_original, original)
        np.testing.assert_array_equal(ext.df_sensores, original)

    def test_escala_tempo_por_modo_e_exportacao_html(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa', 'μm/m']))
        for campo, valor in ((ext.campo_y_min, -5), (ext.campo_y_max, 10),
                             (ext.campo_tempo_inicio, .2), (ext.campo_tempo_fim, .8)):
            campo.setValue(valor)
        self.assertTrue(ext.aplicar_visualizacao())
        ext.botao_deformacao.click()
        ext.botao_tensao.click()
        np.testing.assert_allclose(ext.grafico.viewRange(), [[.2, .8], [-5, 10]])
        fig = criar_figura_html([ext.grafico.getPlotItem()])
        self.assertEqual(len(fig.data), 1)
        self.assertEqual(list(fig.layout.yaxis.range), [-5, 10])
        self.assertEqual(list(fig.layout.xaxis.range), [.2, .8])
        self.assertIn('MPa', fig.layout.yaxis.title.text)
        data = criar_figura_html([ext.grafico.getPlotItem()], inicio=datetime(2026, 1, 1))
        self.assertEqual(data.layout.xaxis.range[0], '2026-01-01T00:00:00.200000')

    def test_limites_invalidos_nao_alteram_a_vista(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa']))
        antes = ext.grafico.viewRange()
        ext.campo_y_min.setValue(5)
        ext.campo_y_max.setValue(-5)
        self.assertFalse(ext.aplicar_visualizacao())
        np.testing.assert_allclose(ext.grafico.viewRange(), antes)

    def test_filtrar_e_restaurar_mantem_modo_e_unidade(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa', 'μm/m']))
        ext.botao_deformacao.click()
        self.assertTrue(ext.aplicar_configuracao({'calibracao': 2, 'passa_baixa': 100}))
        self.assertEqual(self.visiveis(ext), [2])
        self.assertEqual(ext.unidade_visual, 'μm/m')
        ext.restaurar_original()
        np.testing.assert_array_equal(ext.df_sensores, ext.df_original)
        self.assertEqual(self.visiveis(ext), [2])

    def test_canais_desmarcados_nao_sao_exportados(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa'] * 20))
        self.assertEqual(len(ext.checkboxes_canais), 20)
        ext.checkboxes_canais[20].setChecked(False)
        fig = criar_figura_html([ext.grafico.getPlotItem()])
        self.assertEqual(len(fig.data), 19)
        self.assertFalse(any('Canal 20 ' in t.name for t in fig.data))

    def test_reimportacao_limpa_canais_e_modos_antigos(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa', 'μm/m']))
        ext.botao_deformacao.click()
        ext.importar_caminho(self.arquivo(['MPa']))
        self.assertEqual(self.visiveis(ext), [1])
        self.assertEqual(ext.unidade_visual, 'MPa')
        self.assertFalse(ext.botao_deformacao.isEnabled())
        ext.importar_caminho(self.arquivo(['μm/m']))
        self.assertEqual(ext.unidade_visual, 'μm/m')
        self.assertEqual(self.visiveis(ext), [1])
        self.assertFalse(ext.botao_tensao.isEnabled())
        acm = self.janela(TelaLynxAcelerometria)
        acm.importar_caminho(self.arquivo(['g'] * 15))
        self.assertEqual(len(acm.checkboxes_canais), 5)
        acm.importar_caminho(self.arquivo(['g'] * 3))
        self.assertEqual(len(acm.checkboxes_canais), 1)
        self.assertEqual(len(acm.curvas_lynx), 3)

    def test_importacao_invalida_preserva_arquivo_anterior(self):
        ext = self.janela(TelaLynxExtensometria)
        acm = self.janela(TelaLynxAcelerometria)
        for tela, unidades in ((ext, ['MPa']), (acm, ['g'] * 3)):
            valido = self.arquivo(unidades)
            tela.importar_caminho(valido)
            if tela is ext:
                with self.assertRaises(ValueError):
                    tela.importar_caminho(self.arquivo(['mm']))
            else:
                self.assertFalse(tela.importar_caminho(self.arquivo(['mm'])))
            self.assertEqual(tela.caminho_atual, valido)

    def test_fft_rms_e_selecao_xyz_com_nomes_livres(self):
        acm = self.janela(TelaLynxAcelerometria)
        acm.importar_caminho(self.arquivo(['MPa'] + ['g'] * 6))
        acm.botao_fft.click()
        x, y = acm.curvas_lynx[(1, 'X')].getOriginalDataset()
        self.assertAlmostEqual(x[np.argmax(y)], 50)
        self.assertAlmostEqual(float(np.max(y)), 2, places=7)
        self.assertIsNotNone(acm.info_fft)
        fig = criar_figura_html(list(acm.graficos_eixos.values()))
        self.assertEqual(fig.layout.xaxis.title.text, 'Frequência (Hz)')
        acm.botao_rms.click()
        self.assertFalse(acm.botao_fft.isChecked())
        _, y = acm.curvas_lynx[(1, 'X')].getOriginalDataset()
        np.testing.assert_allclose(y, 2 / np.sqrt(2) * 1000, rtol=1e-7)
        acm.checkboxes_eixos[(1, 'X')].setChecked(False)
        self.assertFalse(acm.curvas_lynx[(1, 'X')].isVisible())
        acm.checkboxes_canais[2].setChecked(False)
        self.assertFalse(any(acm.curvas_lynx[(2, e)].isVisible() for e in 'XYZ'))
        acm.restaurar_original()
        self.assertFalse(acm.botao_rms.isChecked())
        np.testing.assert_array_equal(acm.df_sensores, acm.df_original)

    def test_exportacoes_reais_svg_e_html(self):
        ext = self.janela(TelaLynxExtensometria)
        ext.importar_caminho(self.arquivo(['MPa', 'μm/m']))
        ext.botao_deformacao.click()
        ext.campo_tempo_inicio.setValue(.2)
        ext.campo_tempo_fim.setValue(.8)
        ext.campo_y_min.setValue(-7)
        ext.campo_y_max.setValue(8)
        ext.aplicar_visualizacao()
        from matplotlib.figure import Figure
        salvar = Figure.savefig
        def verificar_figura(figura, *args, **kwargs):
            np.testing.assert_allclose(figura.axes[0].get_xlim(), [.2, .8])
            np.testing.assert_allclose(figura.axes[0].get_ylim(), [-7, 8])
            return salvar(figura, *args, **kwargs)
        with patch.object(QFileDialog, 'getExistingDirectory', return_value=self.tmp.name), patch.object(QMessageBox, 'information'):
            with patch.object(Figure, 'savefig', verificar_figura):
                ext.exportar_svg()
            ext.exportar_html()
        self.aviso.assert_not_called()
        svg = list(Path(self.tmp.name).glob('*.svg'))
        html = list(Path(self.tmp.name).glob('*.html'))
        self.assertEqual(len(svg), 1)
        self.assertEqual(len(html), 1)
        self.assertIn('<svg', svg[0].read_text())
        self.assertIn('Canal 2', html[0].read_text())
        self.assertNotIn('Canal 1 —', html[0].read_text())

    def test_confirmacao_da_ultima_linha_pela_interface(self):
        for classe, unidades in ((TelaLynxExtensometria, ['MPa']), (TelaLynxAcelerometria, ['g'] * 3)):
            with self.subTest(classe=classe.__name__):
                tela = self.janela(classe)
                valido = self.arquivo(unidades)
                tela.importar_caminho(valido)
                incompleto = self.arquivo(unidades, alterar=lambda linhas: linhas[-1].__setitem__(1, ''))
                with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(incompleto), '')):
                    with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
                        tela.carregar_arquivo_lynx()
                        self.assertEqual(tela.caminho_atual, valido)
                    with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                        tela.carregar_arquivo_lynx()
                        self.assertEqual(tela.caminho_atual, incompleto)
                        self.assertEqual(len(tela.tempo), 999)


if __name__ == '__main__':
    unittest.main()
