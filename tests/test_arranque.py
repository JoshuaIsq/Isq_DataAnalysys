"""Abre o main.py real em outro processo e usa os botões da aplicação."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROTEIRO = r'''
import csv
from pathlib import Path
import runpy
import sys
import tempfile
import traceback
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
import shiboken6

raiz = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(raiz))
from tela_lynx_acm import TelaLynxAcelerometria
from versao import VERSAO
exec_original = QApplication.exec

def executar(app):
    app.setQuitOnLastWindowClosed(False)
    def verificar():
        sucesso = False
        try:
            principal = next(w for w in app.topLevelWidgets() if w.windowTitle().startswith('ISQ_Analysys'))
            assert VERSAO in principal.windowTitle()
            lynx = next(b for b in principal.findChildren(QPushButton) if b.text() == 'Lynx')
            acao = next(a for a in lynx.menu().actions() if a.text() == 'Acelerometria')
            acao.trigger()
            acm = next(w for w in app.topLevelWidgets() if isinstance(w, TelaLynxAcelerometria))
            acm.resize(1330, 625)
            app.processEvents()
            assert acm.isVisible()
            assert VERSAO in acm.windowTitle()
            assert acm.botao_velocidade.isVisible()
            assert not acm.botao_velocidade.isEnabled()
            assert not acm.botao_velocidade.visibleRegion().isEmpty()
            with tempfile.TemporaryDirectory() as pasta:
                csv_path = Path(pasta) / 'aceleracao.csv'
                with csv_path.open('w', encoding='utf-8-sig', newline='') as arquivo:
                    linhas = csv.writer(arquivo, delimiter=';')
                    linhas.writerows([['Name', 'X', 'Y', 'Z'], ['Unit', 'g', 'g', 'g'],
                                      ['HighLim', '100', '100', '100'], ['LowLim', '-100', '-100', '-100'], ['Time (s)']])
                    for i in range(500):
                        linhas.writerow([i/200, .01*((i % 11)-5), .02*((i % 13)-6), .03*((i % 7)-3)])
                assert acm.importar_caminho(csv_path)
                app.processEvents()
                assert acm.botao_velocidade.isEnabled()
                QTest.mouseClick(acm.botao_velocidade, Qt.MouseButton.LeftButton)
                assert len(acm.janelas_resultados) == 1
                vel = acm.janelas_resultados[0]
                app.processEvents()
                assert vel.isVisible() and acm.isVisible()
                assert not vel.botao_deslocamento.visibleRegion().isEmpty()
                QTest.mouseClick(vel.botao_deslocamento, Qt.MouseButton.LeftButton)
                assert len(vel.janelas_resultados) == 1
                desp = vel.janelas_resultados[0]
                app.processEvents()
                assert all(w.isVisible() for w in (acm, vel, desp))
                assert vel.graficos_eixos['X'].getAxis('left').labelUnits == 'mm/s'
                assert desp.graficos_eixos['X'].getAxis('left').labelUnits == 'mm'
                assert acm.graficos_eixos['X'].getAxis('left').labelUnits == 'g'
            print('ARRANQUE_OK ' + VERSAO)
            sucesso = True
        except BaseException:
            traceback.print_exc()
        finally:
            for janela in app.topLevelWidgets():
                if shiboken6.isValid(janela):
                    janela.close()
            app.exit(0 if sucesso else 1)
    QTimer.singleShot(0, verificar)
    return exec_original()

QApplication.exec = executar
runpy.run_path(str(raiz / 'main.py'), run_name='__main__')
'''


class ArranqueTests(unittest.TestCase):
    def test_main_real_abre_os_tres_graficos_com_diferentes_escalas(self):
        raiz = Path(__file__).resolve().parents[1]
        for escala in ('1', '1.25', '1.5'):
            with self.subTest(escala=escala):
                ambiente = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=escala,
                                PYTHONDONTWRITEBYTECODE='1')
                processo = subprocess.run(
                    [sys.executable, '-c', ROTEIRO, str(raiz)],
                    cwd=raiz, env=ambiente, capture_output=True, text=True, timeout=40,
                )
                self.assertEqual(processo.returncode, 0, processo.stdout + processo.stderr)
                self.assertIn('ARRANQUE_OK', processo.stdout)
