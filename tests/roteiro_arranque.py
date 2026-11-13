"""Percurso da interface em processo isolado, compartilhado pelos testes."""
ROTEIRO = r'''
import csv
from pathlib import Path
import runpy
import sys
import tempfile
import traceback
from PySide6.QtCore import QTimer, Qt, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QLabel
import shiboken6

raiz = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(raiz))
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys import __version__ as VERSAO
exec_original = QApplication.exec

def executar(app):
    app.setQuitOnLastWindowClosed(False)
    def verificar():
        sucesso = False
        try:
            principal = next(w for w in app.topLevelWidgets() if w.windowTitle().startswith('ISQ_Analysys'))
            assert VERSAO in principal.windowTitle()
            assert any(not label.pixmap().isNull() for label in principal.findChildren(QLabel))
            lynx = next(b for b in principal.findChildren(QPushButton) if b.text() == 'Lynx')
            extensometria = next(a for a in lynx.menu().actions() if a.text() == 'Extensometria')
            extensometria.trigger()
            ext = principal.janela_extensometria
            assert ext.isVisible() and VERSAO in ext.windowTitle()
            ext.close()
            extensometria.trigger()
            assert principal.janela_extensometria is ext and ext.isVisible()
            regua_acao = next(a for a in lynx.menu().actions() if a.text() == 'Régua potenciométrica')
            regua_acao.trigger()
            regua = principal.janela_regua
            assert regua.isVisible() and VERSAO in regua.windowTitle()
            regua.close()
            regua_acao.trigger()
            assert principal.janela_regua is regua and regua.isVisible()
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
                assert not acm.botao_velocidade.isEnabled()
                QTest.mouseClick(acm.botao_converter, Qt.MouseButton.LeftButton)
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
                assert acm.graficos_eixos['X'].getAxis('left').labelUnits == 'mm/s²'
                regua_path = Path(pasta) / 'regua.csv'
                with regua_path.open('w', encoding='utf-8-sig', newline='') as arquivo:
                    linhas = csv.writer(arquivo, delimiter=';')
                    linhas.writerows([['Name', 'Régua A', 'Régua B'], ['Unit', 'mm', 'mm'],
                                      ['HighLim', '106', '106'], ['LowLim', '-195', '-195'], ['Time (s)']])
                    for i in range(500):
                        linhas.writerow([i/200, -7.11, i/100])
                assert regua.importar_caminho(regua_path)
                app.processEvents()
                assert regua.grafico.getAxis('left').labelUnits == 'mm'
                assert len(regua.curvas_regua) == 2
                assert regua.curvas_regua[1].getOriginalDataset()[1][0] == -7.11
            print('ARRANQUE_OK ' + VERSAO)
            sucesso = True
        except BaseException:
            traceback.print_exc()
        finally:
            # Fecha somente as janelas da aplicação. topLevelWidgets também
            # contém controles internos do pyqtgraph que não são janelas do usuário.
            janelas = [w for w in app.topLevelWidgets()
                       if type(w).__module__.startswith('isq_dataanalysys.interface.')]
            for janela in janelas:
                if shiboken6.isValid(janela):
                    janela.close()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            for janela in janelas:
                if shiboken6.isValid(janela):
                    shiboken6.delete(janela)
            app.exit(0 if sucesso else 1)
    QTimer.singleShot(0, verificar)
    return exec_original()

QApplication.exec = executar
sys.argv = [str(raiz / 'main.py')]
runpy.run_path(str(raiz / 'main.py'), run_name='__main__')
'''
