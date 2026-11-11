"""CSV autocontido e versionado para preservar e reabrir séries tratadas.

O relógio original do CSV é preservado nos metadados. A coluna timestamp_local
é apresentação (original menos três horas), nunca uma nova origem do relógio.
"""
from array import array
from dataclasses import dataclass
from datetime import datetime, timedelta
import csv
import json
from numbers import Integral
import os
from pathlib import Path
import re
import tempfile

import numpy as np
import pandas as pd
from isq_dataanalysys.processamento.tempo import AJUSTE_HORARIO


MARCA = '# ISQ_DADOS_TRATADOS'
VERSAO_FORMATO = 1
_NUMERO = re.compile(r'[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?\Z')


@dataclass
class DadosTratados:
    tempo: np.ndarray
    dados: pd.DataFrame
    canais: dict
    inicio_csv: datetime | None
    metadados: dict


def _id_canal(valor):
    if isinstance(valor, bool) or not isinstance(valor, (Integral, str)):
        raise ValueError('Cada canal precisa ter um identificador inteiro ou texto.')
    if isinstance(valor, str):
        if not valor:
            raise ValueError('O identificador de um canal não pode ser vazio.')
        return valor
    return int(valor)


def _canais_normalizados(canais):
    if not isinstance(canais, dict) or not canais:
        raise ValueError('Informe pelo menos um canal para o CSV tratado.')
    resultado = {}
    for identificador, descricao in canais.items():
        identificador = _id_canal(identificador)
        if not isinstance(descricao, dict):
            raise ValueError('A descrição de cada canal precisa conter nome, unidade e eixo.')
        for chave in ('nome', 'unidade', 'eixo'):
            if chave not in descricao or not isinstance(descricao[chave], str):
                raise ValueError(f'Canal {identificador}: {chave} ausente ou inválido.')
        if not descricao['nome'].strip():
            raise ValueError(f'Canal {identificador}: nome vazio.')
        resultado[identificador] = descricao.copy()
    return resultado


def _validar_origem(inicio_csv):
    if inicio_csv is not None and (
        not isinstance(inicio_csv, datetime) or inicio_csv.tzinfo is not None
    ):
        raise ValueError('O início original do CSV precisa ser uma data/hora sem fuso, como no Lynx.')


def _timestamp(inicio_csv, segundos):
    if inicio_csv is None:
        return ''
    try:
        with np.errstate(over='raise', invalid='raise'):
            micros = int(np.rint(float(segundos) * 1_000_000))
        instante = inicio_csv + AJUSTE_HORARIO + timedelta(microseconds=micros)
        return instante.isoformat(timespec='microseconds')
    except (ValueError, OverflowError, FloatingPointError) as erro:
        raise ValueError('O tempo informado excede os limites de data/hora do CSV tratado.') from erro


def _vetores(tempo, dados):
    try:
        t = np.asarray(tempo, dtype=float)
    except (TypeError, ValueError) as erro:
        raise ValueError('O tempo precisa conter valores numéricos.') from erro
    if t.ndim != 1 or not len(t) or not np.isfinite(t).all():
        raise ValueError('O tempo precisa conter pelo menos uma amostra finita.')
    if np.any(t[1:] <= t[:-1]):
        raise ValueError('O tempo deve ser crescente, sem repetições.')
    if not isinstance(dados, pd.DataFrame) or dados.empty or len(dados) != len(t):
        raise ValueError('Tempo e dados precisam ter a mesma quantidade de amostras.')
    if dados.columns.has_duplicates:
        raise ValueError('Os identificadores dos canais não podem se repetir.')
    try:
        y = dados.to_numpy(dtype=float)
    except (ValueError, TypeError) as erro:
        raise ValueError('As medições precisam conter valores numéricos.') from erro
    if not np.isfinite(y).all():
        raise ValueError('Existem medições vazias ou não finitas.')
    return t, y


def salvar_csv_tratado(caminho, tempo, dados, canais, inicio_csv=None, metadados=None):
    """Salva amostras exatas de float64, unidades e origem temporal no mesmo arquivo.

    Não recorta nem zera o tempo recebido. Canais são um dicionário ordenado por
    identificadores (int/texto), com nome, unidade e eixo. Nomes podem se repetir.
    Uma amostra é válida; não se exige amostragem regular para permitir RMS.
    """
    canais = _canais_normalizados(canais)
    t, y = _vetores(tempo, dados)
    if list(dados.columns) != list(canais):
        raise ValueError('A ordem e os identificadores dos dados precisam corresponder aos canais.')
    _validar_origem(inicio_csv)
    if metadados is None:
        metadados = {}
    if not isinstance(metadados, dict):
        raise ValueError('Os metadados precisam ser um dicionário.')
    campos = [f'canal_{i}' for i in range(1, len(canais)+1)]
    cabecalho = {
        'formato': 'ISQ_DADOS_TRATADOS',
        'versao_formato': VERSAO_FORMATO,
        'inicio_csv': None if inicio_csv is None else inicio_csv.isoformat(timespec='microseconds'),
        'ajuste_horario_horas': -3,
        'canais': [dict(id=c, coluna=coluna, descricao=descricao)
                   for coluna, (c, descricao) in zip(campos, canais.items())],
        'metadados': metadados,
    }
    try:
        metadados_json = json.dumps(cabecalho, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError) as erro:
        raise ValueError('Os metadados precisam conter apenas valores JSON válidos e finitos.') from erro
    # Verifica os extremos antes de criar o arquivo; intermediários são crescentes.
    _timestamp(inicio_csv, t[0])
    _timestamp(inicio_csv, t[-1])
    destino = Path(caminho)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='',
                                         dir=destino.parent, prefix=f'.{destino.name}.',
                                         suffix='.tmp', delete=False) as arquivo:
            temporario = Path(arquivo.name)
            escritor = csv.writer(arquivo, delimiter=';', lineterminator='\n')
            escritor.writerow([MARCA, VERSAO_FORMATO])
            escritor.writerow(['# METADADOS', metadados_json])
            escritor.writerow(['tempo_s', 'timestamp_local', *campos])
            for segundos, valores in zip(t, y):
                numeros = (format(float(v), '.17g').replace('.', ',') for v in valores)
                escritor.writerow([format(float(segundos), '.17g').replace('.', ','),
                                    _timestamp(inicio_csv, segundos), *numeros])
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def _numero(texto, linha):
    if not isinstance(texto, str) or not _NUMERO.fullmatch(texto.strip()):
        raise ValueError(f'CSV tratado: valor numérico inválido na linha {linha}.')
    try:
        numero = float(texto.strip().replace(',', '.'))
    except ValueError as erro:
        raise ValueError(f'CSV tratado: valor numérico inválido na linha {linha}.') from erro
    if not np.isfinite(numero):
        raise ValueError(f'CSV tratado: valor não finito na linha {linha}.')
    return numero


def _constante_json_invalida(_valor):
    raise ValueError('Constante JSON não finita.')


def _ler_cabecalho(leitor):
    if next(leitor, None) != [MARCA, str(VERSAO_FORMATO)]:
        raise ValueError('Arquivo não reconhecido ou versão de CSV tratado não suportada.')
    linha = next(leitor, None)
    if linha is None or len(linha) != 2 or linha[0] != '# METADADOS':
        raise ValueError('CSV tratado sem metadados válidos.')
    try:
        meta = json.loads(linha[1], parse_constant=_constante_json_invalida)
    except (ValueError, TypeError) as erro:
        raise ValueError('CSV tratado com metadados JSON inválidos.') from erro
    if (not isinstance(meta, dict) or meta.get('formato') != 'ISQ_DADOS_TRATADOS'
            or type(meta.get('versao_formato')) is not int or meta['versao_formato'] != VERSAO_FORMATO
            or type(meta.get('ajuste_horario_horas')) is not int or meta['ajuste_horario_horas'] != -3
            or 'inicio_csv' not in meta or not isinstance(meta.get('metadados'), dict)
            or not isinstance(meta.get('canais'), list) or not meta['canais']):
        raise ValueError('CSV tratado com estrutura de metadados inválida.')
    try:
        inicio = None if meta['inicio_csv'] is None else datetime.fromisoformat(meta['inicio_csv'])
    except (ValueError, TypeError) as erro:
        raise ValueError('CSV tratado com início original inválido.') from erro
    _validar_origem(inicio)
    canais = {}
    campos = []
    for indice, canal in enumerate(meta['canais'], 1):
        if not isinstance(canal, dict) or not {'id', 'coluna', 'descricao'} <= canal.keys():
            raise ValueError('CSV tratado com identificação de canal inválida.')
        identificador = _id_canal(canal['id'])
        if identificador in canais or canal['coluna'] != f'canal_{indice}':
            raise ValueError('CSV tratado com canais repetidos ou fora de ordem.')
        canais[identificador] = canal['descricao']
        campos.append(canal['coluna'])
    canais = _canais_normalizados(canais)
    if next(leitor, None) != ['tempo_s', 'timestamp_local', *campos]:
        raise ValueError('CSV tratado com cabeçalho de colunas incompatível com os metadados.')
    return meta, inicio, canais


def ler_csv_tratado(caminho):
    """Reabre o CSV exportado, sem refiltrar, reintegrar ou reaplicar ajuste de hora."""
    try:
        with open(caminho, encoding='utf-8-sig', newline='') as arquivo:
            leitor = csv.reader(arquivo, delimiter=';', strict=True)
            meta, inicio, canais = _ler_cabecalho(leitor)
            # Armazenamento compacto para registros longos: evita uma lista Python
            # e um objeto float para cada medição dos milhões de amostras Lynx.
            tempos, valores = array('d'), array('d')
            for linha in leitor:
                n = leitor.line_num
                if len(linha) != len(canais)+2:
                    raise ValueError(f'CSV tratado: quantidade incorreta de colunas na linha {n}.')
                segundos = _numero(linha[0], n)
                if tempos and segundos <= tempos[-1]:
                    raise ValueError(f'CSV tratado: tempo repetido ou fora de ordem na linha {n}.')
                esperado = _timestamp(inicio, segundos)
                if inicio is None:
                    if linha[1] != '':
                        raise ValueError(f'CSV tratado: timestamp sem referência temporal na linha {n}.')
                else:
                    try:
                        instante = datetime.fromisoformat(linha[1])
                    except (ValueError, TypeError) as erro:
                        raise ValueError(f'CSV tratado: timestamp inválido na linha {n}.') from erro
                    if instante != datetime.fromisoformat(esperado):
                        raise ValueError(f'CSV tratado: timestamp incompatível com o tempo na linha {n}.')
                tempos.append(segundos)
                valores.extend(_numero(v, n) for v in linha[2:])
    except (csv.Error, UnicodeError) as erro:
        raise ValueError('CSV tratado inválido ou com codificação incompatível com UTF-8.') from erro
    if not tempos:
        raise ValueError('CSV tratado sem amostras.')
    matriz = np.frombuffer(valores, dtype=float).reshape(len(tempos), len(canais))
    dados = pd.DataFrame(matriz, columns=list(canais), dtype=float)
    return DadosTratados(np.frombuffer(tempos, dtype=float), dados, canais, inicio, meta['metadados'])
