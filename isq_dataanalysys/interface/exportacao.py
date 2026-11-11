"""Diálogos de exportação compartilhados pelas telas de medição e resultados."""
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from PySide6.QtWidgets import QFileDialog, QMessageBox
import pyqtgraph as pg
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys.exportacao.svg import salvar_svg
from isq_dataanalysys.leitores.metadados import ler_inicio_lynx
from isq_dataanalysys.exportacao.csv_tratado import salvar_csv_tratado
from isq_dataanalysys import __version__


class ExportacaoGraficos:
    """Requer grafico, df_sensores e os serviços de uma QMainWindow."""

    def plots_para_exportar(self):
        if isinstance(self.grafico, pg.PlotWidget):
            return [self.grafico.getPlotItem()]
        return [plot for plot in self.graficos_eixos.values() if plot.isVisible()]

    def inicio_para_exportar(self):
        if hasattr(self, "inicio_exportacao"):
            return self.inicio_exportacao
        if hasattr(self, "inicio_arquivo"):
            return self.inicio_arquivo
        return ler_inicio_lynx(getattr(self, "caminho_atual", None))

    def _identidade_curva_csv(self, curva, sequencia):
        """Resolve a identidade da coluna sem inferir canais por nomes repetidos."""
        canal = curva.property('canal_id')
        for atributo in ('curvas', 'curvas_ext', 'curvas_regua', 'curvas_lynx'):
            for chave, item in getattr(self, atributo, {}).items():
                if item is curva:
                    canal = (self.sensores_lynx[chave[0]-1][chave[1]]
                             if atributo == 'curvas_lynx' else chave)
                    break
        return sequencia if canal is None else canal

    def dados_para_csv(self):
        """Coleta as curvas temporais visíveis, com unidades efetivamente exibidas."""
        if getattr(self, 'df_sensores', None) is None:
            raise ValueError('Abra um arquivo primeiro.')
        plots = self.plots_para_exportar()
        if any(p.getAxis('bottom').labelUnits == 'Hz' for p in plots):
            raise ValueError('CSV tratado usa dados no tempo. Desative FFT para exportar; RMS temporal é aceito.')
        colunas, canais, base = {}, {}, None
        for plot in plots:
            unidade = plot.getAxis('left').labelUnits or ''
            for curva in plot.listDataItems():
                if not curva.isVisible():
                    continue
                x, y = curva.getOriginalDataset()
                if x is None or y is None or not len(x):
                    continue
                # RMS em escala log oculta zeros somente na curva; o CSV mantém o RMS linear.
                x, y = np.asarray(x,dtype=float), np.asarray(getattr(curva,'dados_csv',y),dtype=float)
                if base is None:
                    base = x
                elif not np.array_equal(base,x):
                    raise ValueError('Os canais selecionados têm bases temporais diferentes.')
                canal = self._identidade_curva_csv(curva,len(colunas)+1)
                if canal in colunas:
                    raise ValueError('Identidades de canais repetidas na exportação.')
                nome = curva.name() or f'Canal {canal}'
                info = getattr(self,'canais',{}).get(canal)
                if isinstance(info,dict):
                    eixo, nome = info.get('eixo',''), info.get('nome',nome)
                elif isinstance(info,tuple):
                    eixo = info[0]
                    nome = nome.removeprefix(f'Canal {canal} — ')
                else:
                    eixo = getattr(self,'info_arquivo',{}).get('eixos',{}).get(canal,'')
                    nome = getattr(self,'info_arquivo',{}).get('nomes',{}).get(canal,nome)
                canais[canal] = dict(nome=nome, unidade=unidade, eixo=eixo)
                colunas[canal] = y
        if base is None:
            raise ValueError('Selecione pelo menos um canal com dados.')
        ordem = [c for c in self.df_sensores.columns if c in colunas]
        ordem += [c for c in colunas if c not in ordem]
        colunas = {c:colunas[c] for c in ordem}
        canais = {c:canais[c] for c in ordem}
        intervalo = (self.intervalo_exportacao() if hasattr(self,'intervalo_exportacao') else None)
        if intervalo is None:
            intervalo = plots[0].viewRange()[0]
        baixo, alto = map(float, intervalo)
        tolerancia = max(abs(baixo),abs(alto),1)*np.finfo(float).eps*16
        selecao = (base>=baixo-tolerancia)&(base<=alto+tolerancia)
        if not np.any(selecao):
            raise ValueError('O intervalo escolhido não contém amostras. Amplie o intervalo.')
        dados = pd.DataFrame({c:v[selecao] for c,v in colunas.items()})
        metadata = dict(getattr(self,'metadados_tratados',{}))
        metadata.update(versao_app=__version__, titulo=self.windowTitle(),
                        descricao=getattr(self,'descricao_exportacao','') or
                                  getattr(getattr(self,'rotulo_ativos',None),'text',lambda:'')(),
                        inicio_gravacao_s=float(getattr(self,'inicio_gravacao_s',metadata.get('inicio_gravacao_s',0))),
                        intervalo_original_s=metadata.get('intervalo_original_s',[float(base[0]),float(base[-1])]),
                        intervalo_avaliacao_s=[baixo,alto],
                        modalidade=getattr(self,'grandeza',type(self).__name__))
        if getattr(getattr(self,'botao_rms',None),'isChecked',lambda:False)():
            metadata.update(modo='RMS AC',janela_rms_s=float(self.campo_janela_rms.value()),
                            valores_csv='RMS em escala linear, em mg')
        fs_origem = getattr(self,'info_processamento',{}).get('fs')
        if fs_origem is not None:
            metadata['fs_origem_hz'] = float(fs_origem)
        return base[selecao].copy(), dados, canais, metadata

    def exportar_csv(self):
        try:
            tempo, dados, canais, metadata = self.dados_para_csv()
        except ValueError as erro:
            QMessageBox.information(self,'Exportação CSV',str(erro))
            return
        caminho, _ = QFileDialog.getSaveFileName(self,'Salvar CSV tratado',
            f'dados_tratados_{datetime.now():%Y%m%d_%H%M%S}.csv','CSV tratado (*.csv)')
        if not caminho:
            return
        destino = Path(caminho)
        if destino.suffix.lower() != '.csv':
            destino = destino.with_suffix('.csv')
        origem = getattr(self,'caminho_atual',None)
        if origem and destino.resolve() == Path(origem).resolve():
            QMessageBox.warning(self,'Exportação CSV','Escolha outro arquivo para preservar o arquivo de origem.')
            return
        try:
            salvar_csv_tratado(destino,tempo,dados,canais,inicio_csv=self.inicio_para_exportar(),metadados=metadata)
        except (OSError,ValueError) as erro:
            QMessageBox.warning(self,'Falha ao exportar CSV',str(erro))
            return
        self.statusBar().showMessage(f'CSV tratado salvo em: {destino}')
        QMessageBox.information(self,'Exportação concluída',f'Arquivo salvo em:\n{destino}\n\nReabra em Dados tratados na tela inicial.')

    def exportar_svg(self):
        if getattr(self, "df_sensores", None) is None:
            QMessageBox.information(
                self,
                "Exportação",
                "Abra um arquivo primeiro."
            )
            return

        plots = self.plots_para_exportar()

        # Exporta somente as curvas que estão selecionadas.
        selecionadas = [
            [
                curva
                for curva in plot.listDataItems()
                if curva.isVisible()
            ]
            for plot in plots
        ]

        if not any(selecionadas):
            QMessageBox.information(
                self,
                "Exportação",
                "Selecione pelo menos um canal."
            )
            return

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta para salvar o SVG"
        )

        if not pasta:
            return

        nome = (
            f"grafico_{datetime.now():%Y%m%d_%H%M%S_%f}.svg"
        )
        caminho = Path(pasta) / nome

        try:
            salvar_svg(plots, caminho, descricao=getattr(self, "descricao_exportacao", ""),
                       titulo=self.windowTitle(), inicio=self.inicio_para_exportar())
        except Exception as erro:
            QMessageBox.warning(self, "Falha ao exportar SVG", str(erro))
            return

        self.statusBar().showMessage(f"SVG salvo em: {caminho}")

        QMessageBox.information(self, "Exportação concluída", f"Arquivo salvo em:\n{caminho}")


    def exportar_html(self):
        if getattr(self, "df_sensores", None) is None:
            QMessageBox.information(
                self,
                "Exportação",
                "Abra um arquivo primeiro.",
            )
            return

        plots = self.plots_para_exportar()

        tem_selecao = any(
            curva.isVisible()
            for plot in plots
            for curva in plot.listDataItems()
        )

        if not tem_selecao:
            QMessageBox.information(
                self,
                "Exportação",
                "Selecione pelo menos um canal.",
            )
            return

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta para salvar o HTML interativo",
        )

        if not pasta:
            return

        nome = f"grafico_{datetime.now():%Y%m%d_%H%M%S_%f}.html"
        caminho = Path(pasta) / nome

        try:
            figura = criar_figura_html(
                plots,
                inicio=self.inicio_para_exportar(),
                titulo=self.windowTitle(),
                descricao=getattr(self, "descricao_exportacao", ""),
            )

            figura.write_html(
                str(caminho),
                include_plotlyjs=True,
                full_html=True,
                auto_open=False,
                config={
                    "scrollZoom": True,
                    "displaylogo": False,
                    "responsive": True,
                },
            )

        except Exception as erro:
            QMessageBox.warning(
                self,
                "Falha ao exportar HTML",
                str(erro),
            )
            return

        self.statusBar().showMessage(
            f"HTML salvo em: {caminho}"
        )

        QMessageBox.information(
            self,
            "Exportação concluída",
            f"Arquivo salvo em:\n{caminho}\n\n"
            "Abra esse arquivo no navegador para consultar "
            "os valores passando o mouse sobre as curvas.",
        )
