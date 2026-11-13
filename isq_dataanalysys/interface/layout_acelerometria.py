"""Apresentação da acelerometria: controles e canais na mesma lateral."""
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)


ESTILO = """
QWidget#acelerometria_central { background: #f0f0f0; color: #202428; }
QWidget#acelerometria_central QWidget { font-family: 'Segoe UI', 'DejaVu Sans'; font-size: 12px; }
QFrame[cartao="true"] { background: white; border: 1px solid #dcdfe1; border-radius: 6px; }
QLabel { background: transparent; border: none; }
QLabel[titulo="true"] { font-size: 13px; font-weight: 600; }
QScrollArea, QStackedWidget { background: transparent; border: none; }
QWidget#pagina_controles, QWidget#pagina_canais { background: transparent; }
QPushButton, QDoubleSpinBox { background: #f8f8f8; border: 1px solid #dedfe1; border-radius: 4px; min-height: 20px; }
QPushButton { padding: 1px 6px; }
QPushButton:hover { background: #ebf1f5; border-color: #b7cad6; }
QPushButton:pressed, QPushButton:checked { background: #ddeaf2; border-color: #8fb4cc; }
QPushButton:disabled, QDoubleSpinBox:disabled { color: #92989c; background: #f5f5f5; }
QDoubleSpinBox { padding: 0px 2px; }
QCheckBox { spacing: 5px; background: transparent; }
QToolButton { background: transparent; border: none; padding: 3px; }
QToolButton:hover { background: #e1e8ed; border-radius: 3px; }
QToolButton[navegacao="true"] { border-left: 3px solid transparent; border-radius: 0px; }
QToolButton[navegacao="true"]:checked { border-left: 3px solid #58a5ce; background: #e8eef2; }
QPushButton#gerar_velocidade { background: #dce5eb; }
QPushButton#gerar_velocidade:hover { background: #c6dbe9; }
"""


def icone_lateral(tipo):
    """Ícones vetoriais pequenos, sem depender de fontes de símbolos do sistema."""
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#647681'), 1.4))
    if tipo == 'arquivo':
        caminho = QPainterPath()
        caminho.moveTo(2, 16)
        caminho.lineTo(2, 4)
        caminho.lineTo(8, 4)
        caminho.lineTo(10, 6)
        caminho.lineTo(18, 6)
        caminho.lineTo(18, 16)
        caminho.closeSubpath()
        painter.drawPath(caminho)
    elif tipo == 'exportar':
        painter.drawLine(10, 2, 10, 13)
        painter.drawLine(6, 9, 10, 13)
        painter.drawLine(14, 9, 10, 13)
        painter.drawLine(3, 13, 3, 17)
        painter.drawLine(3, 17, 17, 17)
        painter.drawLine(17, 17, 17, 13)
    else:
        painter.drawEllipse(QRectF(3, 3, 14, 14))
        painter.drawLine(10, 9, 10, 14)
        painter.drawPoint(10, 6)
    painter.end()
    return QIcon(pixmap)


def cartao(titulo):
    quadro = QFrame()
    quadro.setProperty('cartao', True)
    layout = QVBoxLayout(quadro)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    rotulo = QLabel(titulo)
    rotulo.setProperty('titulo', True)
    layout.addWidget(rotulo)
    return quadro, layout


def rolagem(pagina):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(pagina)
    return area


def largura_flexivel(widget, minimo=0):
    widget.setMinimumWidth(minimo)
    widget.setMaximumWidth(16777215)
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)


def montar_lateral_acelerometria(tela):
    """Reposiciona os controles existentes, preservando seus sinais e estados."""
    anterior = tela.takeCentralWidget()
    canais = anterior.findChild(QScrollArea).takeWidget()
    central = QWidget()
    central.setObjectName('acelerometria_central')
    central.setStyleSheet(ESTILO)
    principal = QHBoxLayout(central)
    principal.setContentsMargins(0, 8, 8, 8)
    principal.setSpacing(8)

    trilho = QFrame()
    trilho.setFixedWidth(28)
    navegacao = QVBoxLayout(trilho)
    navegacao.setContentsMargins(0, 0, 0, 0)
    navegacao.setSpacing(4)
    tela.grupo_lateral = QButtonGroup(central)
    tela.grupo_lateral.setExclusive(True)
    tela.paginas_laterais = QStackedWidget()
    # Inclui espaço para a barra de rolagem em telas baixas.
    tela.paginas_laterais.setFixedWidth(260)
    for indice, nome, tipo in ((0, 'Controles', 'arquivo'), (1, 'Canais', 'canais')):
        botao = QToolButton()
        botao.setObjectName('aba_' + nome.lower())
        botao.setProperty('navegacao', True)
        botao.setAccessibleName(nome)
        botao.setToolTip(nome)
        botao.setIcon(icone_lateral(tipo))
        botao.setIconSize(QSize(19, 19))
        botao.setFixedSize(28, 30)
        botao.setCheckable(True)
        tela.grupo_lateral.addButton(botao, indice)
        navegacao.addWidget(botao)
        setattr(tela, 'botao_aba_' + nome.lower(), botao)
    navegacao.addStretch()
    tela.grupo_lateral.idClicked.connect(tela.paginas_laterais.setCurrentIndex)
    tela.botao_aba_controles.setChecked(True)
    principal.addWidget(trilho)
    principal.addWidget(tela.paginas_laterais)

    pagina = QWidget()
    pagina.setObjectName('pagina_controles')
    blocos = QGridLayout(pagina)
    blocos.setContentsMargins(0, 0, 0, 0)
    blocos.setSpacing(8)

    arquivo, layout = cartao('Arquivo e Dados')
    tela.abrir.setIcon(icone_lateral('arquivo'))
    tela.exportar.setIcon(icone_lateral('exportar'))
    for botao in (tela.abrir, tela.exportar, tela.botao_restaurar):
        layout.addWidget(botao, 0, Qt.AlignmentFlag.AlignLeft)
    blocos.addWidget(arquivo, 0, 0)

    filtros, layout = cartao('Filtros e Tratamento')
    layout.addWidget(tela.controle_passa_banda)
    banda = tela.controle_passa_banda
    banda.layout().setHorizontalSpacing(6)
    banda.layout().setVerticalSpacing(4)
    banda.layout().setColumnStretch(2, 0)
    banda.layout().setColumnStretch(1, 1)
    for campo in (banda.campo_inferior, banda.campo_superior):
        largura_flexivel(campo)
    offset = tela.controle_offset
    rotulo_offset = offset.layout().itemAt(1).widget()
    offset.layout().removeWidget(rotulo_offset)
    offset.layout().itemAt(0).layout().insertWidget(0, rotulo_offset)
    offset.layout().itemAt(0).layout().setStretch(1, 1)
    offset.layout().itemAt(0).layout().setStretch(3, 0)
    largura_flexivel(offset.campo, 55)
    offset.botao.setFixedWidth(58)
    offset.botao.setFixedHeight(24)
    layout.addWidget(offset)
    blocos.addWidget(filtros, 1, 0)

    processamento, layout = cartao('Processamento de Sinal')
    tela.rotulo_ativos.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    layout.addWidget(tela.rotulo_ativos)
    modos = QHBoxLayout()
    modos.setSpacing(4)
    modos.addWidget(tela.botao_fft)
    modos.addWidget(tela.botao_psd)
    modos.addWidget(tela.botao_rms)
    modos.addStretch()
    layout.addLayout(modos)
    rms = QHBoxLayout()
    rms.setSpacing(6)
    rms.addWidget(QLabel('Janela RMS:'))
    largura_flexivel(tela.campo_janela_rms)
    rms.addWidget(tela.campo_janela_rms, 1)
    layout.addLayout(rms)
    layout.addWidget(tela.checkbox_log_rms)
    tela.checkbox_log_rms.setStyleSheet('font-size: 11px;')
    tela.botao_velocidade.setStyleSheet('')
    tela.botao_velocidade.setMinimumHeight(28)
    tela.botao_converter.setStyleSheet('font-size: 11px;')
    layout.addWidget(tela.botao_converter)
    integracao = QHBoxLayout()
    integracao.setSpacing(2)
    integracao.addWidget(tela.botao_velocidade)
    tela.botao_info_integracao = QToolButton()
    tela.botao_info_integracao.setIcon(icone_lateral('info'))
    tela.botao_info_integracao.setIconSize(QSize(15, 15))
    tela.botao_info_integracao.setAccessibleName('Sobre a integração')
    tela.botao_info_integracao.setToolTip('Método de integração e ajustes')
    tela.botao_info_integracao.clicked.connect(tela.mostrar_metodo_integracao)
    integracao.addWidget(tela.botao_info_integracao)
    integracao.addStretch()
    layout.addLayout(integracao)
    layout.addWidget(tela.botao_unificado)
    tela.rotulo_metodo_integracao.setParent(processamento)
    tela.rotulo_metodo_integracao.hide()
    blocos.addWidget(processamento, 2, 0)

    visual, layout = cartao('Visualização e Escala')
    campos = QGridLayout()
    campos.setHorizontalSpacing(8)
    campos.setVerticalSpacing(6)
    for linha, coluna, titulo, campo in (
        (0, 0, 'Escala mínima', tela.campo_y_min), (0, 1, 'máxima', tela.campo_y_max),
        (2, 0, 'Tempo inicial (min)', tela.campo_tempo_inicio), (2, 1, 'final (min)', tela.campo_tempo_fim),
    ):
        rotulo = QLabel(titulo)
        rotulo.setStyleSheet('font-size: 11px;')
        campos.addWidget(rotulo, linha, coluna)
        largura_flexivel(campo)
        campos.addWidget(campo, linha + 1, coluna)
    campos.setColumnStretch(0, 1)
    campos.setColumnStretch(1, 1)
    layout.addLayout(campos)
    botoes = QHBoxLayout()
    botoes.setSpacing(4)
    for botao in (tela.botao_aplicar_visualizacao, tela.botao_ajustar):
        botao.setStyleSheet('font-size: 10px; padding: 1px 3px;')
        botoes.addWidget(botao)
    layout.addLayout(botoes)
    blocos.addWidget(visual, 3, 0)
    blocos.setRowStretch(4, 1)
    tela.rolagem_controles = rolagem(pagina)
    tela.paginas_laterais.addWidget(tela.rolagem_controles)

    pagina_canais = QWidget()
    pagina_canais.setObjectName('pagina_canais')
    lista = QVBoxLayout(pagina_canais)
    lista.setContentsMargins(0, 0, 0, 0)
    lista.setSpacing(8)
    canais.setProperty('cartao', True)
    canais.setFrameShape(QFrame.Shape.NoFrame)
    largura_flexivel(canais)
    canais.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    lista.addWidget(canais)
    tela.rotulo_importacao.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    lista.addWidget(tela.rotulo_importacao)
    # Metadados continuam acessíveis junto dos canais, sem ocupar os gráficos.
    referencia, layout = cartao('Horário da medição')
    painel = tela.painel_referencia
    linha = painel.layout()
    coluna = QVBoxLayout()
    for widget in (painel.rotulo, painel.botao_definir, painel.botao_detalhes):
        linha.removeWidget(widget)
        coluna.addWidget(widget)
    linha.addLayout(coluna)
    layout.addWidget(painel)
    painel.rotulo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    lista.addWidget(referencia)
    lista.addStretch()
    tela.rolagem_canais = rolagem(pagina_canais)
    tela.paginas_laterais.addWidget(tela.rolagem_canais)

    quadro_graficos = QFrame()
    quadro_graficos.setProperty('cartao', True)
    graficos = QVBoxLayout(quadro_graficos)
    graficos.setContentsMargins(6, 6, 6, 6)
    graficos.addWidget(tela.grafico)
    principal.addWidget(quadro_graficos, 1)
    tela.layout_controles = blocos
    tela.setCentralWidget(central)
    anterior.deleteLater()
    tela.resize(1200, 800)
