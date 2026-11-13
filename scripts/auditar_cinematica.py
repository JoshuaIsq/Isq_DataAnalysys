"""Auditoria reproduzível: python -m scripts.auditar_cinematica arquivo.csv.

Grava somente métricas em work/auditoria_cinematica; não copia o CSV de entrada.
Referência: soma em precisão estendida e projeção por QR, independente do lstsq
usado no aplicativo. Acordo numérico não certifica movimento físico nem igualdade
com um ensaio LabVIEW sem a série de saída desse ensaio.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.linalg import qr

from isq_dataanalysys.leitores.acelerometria import ler_lynx_acelerometria
from isq_dataanalysys.processamento.cinematica import (
    converter_aceleracao, integrar_segmento, retirar_ajuste, estatisticas,
)
from isq_dataanalysys.processamento.sinais import Processamento


def referencia(t, entrada, grau):
    dt = np.longdouble(t[-1]-t[0]) / (len(t)-1)
    bruto = np.add.accumulate(entrada.astype(np.longdouble)*dt, axis=0).astype(float)
    u = (t-t[0]) / (t[-1]-t[0])
    # Base independente [1,u,u²], projetada por QR em vez de resolver lstsq.
    q, _ = qr(np.column_stack([u**k for k in range(grau+1)]), mode='economic')
    return bruto-q@(q.T@bruto)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--low', type=float, default=1)
    parser.add_argument('--high', type=float, default=30)
    parser.add_argument('--saida', type=Path, default=Path('work/auditoria_cinematica'))
    args = parser.parse_args()
    t, original, _, info = ler_lynx_acelerometria(args.csv)
    fs = Processamento.validar_dados(t, original)
    g, _ = Processamento.aplicar(t, original, {'passa_banda':(args.low,args.high)})
    a = converter_aceleracao(t, g)
    vb = integrar_segmento(t, a)
    v, cv = retirar_ajuste(t, vb, 1)
    db = integrar_segmento(t, v)
    d, cd = retirar_ajuste(t, db, 2)
    vf = referencia(t, a.to_numpy(), 1)
    df = referencia(t, vf, 2)
    np.testing.assert_allclose(v, vf, rtol=1e-9, atol=1e-8)
    np.testing.assert_allclose(d, df, rtol=1e-8, atol=1e-7)
    # A diferença regressiva é inversa da soma retangular no interior.
    # Acrescenta explicitamente as componentes removidas pelos dois ajustes.
    recuperada = np.diff(d.to_numpy(), n=2, axis=0)*fs**2
    referencia_a = a.iloc[2:].to_numpy()-cv['c1'].to_numpy()-2*cd['c2'].to_numpy()
    erro_derivacao = recuperada-referencia_a
    _, psd, infop = Processamento.psd_ac(t, g)
    potencia = ((g-g.mean())**2).mean().to_numpy()
    np.testing.assert_allclose(psd.sum()*infop['resolucao_hz'], potencia, rtol=1e-10, atol=1e-18)
    metricas = {
        'sha256_csv': hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        'amostras': len(t), 'canais_g': len(a.columns), 'fs_hz': fs,
        'intervalo_s': [float(t[0]),float(t[-1])], 'passa_banda_hz': [args.low,args.high],
        'fator_g_mm_s2': 9810, 'segmentos': 1,
        'erro_max_velocidade_vs_referencia_mm_s': float(np.max(np.abs(v.to_numpy()-vf))),
        'erro_max_posicao_vs_referencia_mm': float(np.max(np.abs(d.to_numpy()-df))),
        'erro_max_derivada_segunda_vs_aceleracao_ajustada_mm_s2': float(np.max(np.abs(erro_derivacao))),
        'erro_rms_derivada_segunda_mm_s2': float(np.sqrt(np.mean(erro_derivacao**2))),
        'interpretacao': 'A derivação retorna a aceleração ajustada, a - c1_velocidade - 2*c2_posicao. '
                         'A auditoria não compara com saídas medidas/exportadas do LabVIEW.',
    }
    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida/'metricas.json').write_text(json.dumps(metricas, ensure_ascii=False, indent=2)+'\n')
    for nome, dados in (('velocidade_mm_s',v),('posicao_mm',d)):
        tabela = estatisticas(dados)
        tabela.insert(0, 'nome', [info['nomes'][c] for c in tabela.index])
        tabela.to_csv(args.saida/f'{nome}.csv', sep=';', decimal=',', encoding='utf-8-sig')
    print(json.dumps(metricas, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
