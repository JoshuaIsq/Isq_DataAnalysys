# Acelerometria: fluxo por segmento — 2026.11.13.1

## Operação

1. Abra o CSV em **Lynx → Acelerometria** e selecione os canais.
2. Em **Passa-banda**, informe Low cutoff e High cutoff e clique **Aplicar**.
   O Butterworth em SOS, ordem de projeto 4 e `sosfiltfilt`, foi preservado.
   Use `0 < Low < High < fs/2`. Offset continua sendo uma operação opcional anterior à banda.
3. **FFT** mostra amplitude de pico em **g**; **PSD** mostra densidade em **g²/Hz**.
   Clique novamente no modo ativo para voltar ao tempo. As duas análises usam o
   sinal temporal tratado em g, mesmo após ativar a conversão.
4. Clique **Converter g → mm/s² (×9810)**. O gráfico temporal e a exportação
   temporal passam a mm/s². Reaplicar filtros não acumula multiplicações.
   Desmarcar esse controle volta a g. Restaurar original/importar outro CSV reinicia a conversão.
5. Clique **Gerar velocidade**. Abre-se a velocidade em mm/s, já com seu ajuste
   linear subtraído **depois** de integrar.
6. Na velocidade, **Visualizar estatísticas** mostra RMS total, máximo e mínimo
   dos canais selecionados no intervalo aplicado. RMS = √média(v²); não é RMS AC.
7. Clique **Obter posição**. A velocidade corrigida é integrada e o ajuste de
   **grau 2** é subtraído da posição. A unidade é mm.
8. Na posição, o **Passa-banda** é opcional e independente da banda da aceleração.
   Aplicar novamente parte sempre da posição após o ajuste quadrático; não encadeia
   filtragens repetidas. **Desativar** restaura essa posição anterior ao filtro.

Os resultados abertos são cópias independentes: alterar ou fechar a origem não
modifica resultados já calculados. O procedimento não retira automaticamente a
média da aceleração. A opção antiga saiu do fluxo principal.

## Cálculo definido

Cada arquivo carregado é **um segmento**. Não há acumulação entre arquivos nem
segmentação automática em janelas. As duas integrações usam amostragem uniforme:

```text
a_mm[i] = 9810 × a_g_tratada[i]
v_bruta[i] = v_bruta[i−1] + a_mm[i] × dt
v[i] = v_bruta[i] − (b_v + m_v × τ[i])
x_bruta[i] = x_bruta[i−1] + v[i] × dt
x[i] = x_bruta[i] − (c0 + c1 × τ[i] + c2 × τ[i]²)
τ = t − t[0]
```

Os acumuladores começam em zero **antes** da primeira amostra. Portanto,
`v_bruta[0] = a_mm[0] × dt` e `x_bruta[0] = v[0] × dt`. Esta é a soma
retangular **Sum[Xdt] / Per segment calculation**, não a integração por trapézios
usada nas revisões anteriores. O fator solicitado é **9810**, em lugar de 9806,65.

Os ajustes por mínimos quadrados são independentes por canal, incluem o intercepto
e usam o registro completo. O cálculo normaliza o tempo em [-1, 1] para melhorar
sua estabilidade numérica. **Detalhes do cálculo** informa os coeficientes na
base de segundos relativos. O resultado ajustado não é forçado a começar em zero.

## FFT e PSD

Ambas usam o registro inteiro, janela retangular e retirada de média apenas para
a análise espectral. A resolução é `Δf = fs/N`. FFT é amplitude unilateral de pico;
PSD é o periodograma unilateral com normalização de densidade. DC e Nyquist não
são duplicados. A soma `Σ PSD × Δf` reproduz a média quadrática do sinal AC em g².
Não se usa Welch nem suavização espectral implícita. Sem as configurações de janela,
normalização e médias do bloco espectral do LabVIEW, não se afirma igualdade com
uma PSD gerada lá. HTML/SVG exportam os espectros em Hz; CSV tratado é temporal.

RMS AC por janelas continua disponível na aceleração: em mg antes da conversão,
em mm/s² após a conversão. Ele não é usado como entrada das integrações.

## Intervalos, exportação e limites

Os campos em minutos selecionam **visualização, CSV exportado e estatísticas**.
Não reiniciam a integração nem refazem ajustes só no recorte. Para integrar um novo
segmento desde o início, carregue um arquivo contendo esse segmento.

CSV tratado mantém as unidades, coeficientes, banda da origem, filtro adicional
da posição, método e timestamp. Reabra em **Dados tratados**. HTML/SVG mantêm o
horário local do CSV −3 h nos eixos temporais. A FFT/PSD usam frequência.
Os campos da tela principal mantêm a apresentação de duas casas em minutos do
commit do usuário (0,01 min = 0,6 s); as janelas de resultados permitem mais precisão.

Subtrair a reta da velocidade altera a aceleração por uma constante. Subtrair o
ajuste quadrático da posição também altera a aceleração por uma constante.
Para a soma discreta, no interior do registro, antes do filtro final:

```text
Δ²x[i]/dt² = a_mm[i] − m_v − 2*c2, i >= 2
```

Assim, derivar a posição corrigida não deve ser apresentado como uma confirmação
de igualdade com a aceleração original. O passa-banda final também muda a série.
O método remove tendências escolhidas; não prova que essas tendências eram erro
instrumental, nem recupera movimento/condições iniciais removidos pelos filtros.

## Verificação reproduzível

```powershell
python -m unittest discover -s tests -v
python -m scripts.auditar_cinematica "caminho\medicao.csv" --low 1 --high 30
```

A auditoria usa soma em precisão estendida e ajuste por projeção QR como referência
independente. Testes cobrem valores calculados à mão, soma geométrica de senoides,
resíduos ortogonais conhecidos, PSD/Parseval, unidades, reinicialização por segmento,
canal/intervalo nas estatísticas, filtro reversível e exportações.

No CSV de ensaio fornecido: **124.740 amostras × 12 canais em g, 200 Hz**, de 0 a
623,695 s; Channel 16 em mm foi excluído. Com banda 1–30 Hz:

| Comparação com a referência independente | Erro absoluto máximo |
|---|---:|
| Velocidade corrigida | 4,09 × 10⁻¹⁴ mm/s |
| Posição corrigida | 2,24 × 10⁻¹² mm |
| Segunda diferença vs. aceleração ajustada | 1,05 × 10⁻¹¹ mm/s² |

Esses erros medem concordância numérica entre implementações. Não há uma série
exportada pelo LabVIEW para certificar igualdade amostra a amostra com aquele ensaio.
O script grava métricas e estatísticas em `work/auditoria_cinematica`, sem copiar o CSV.

Referências de operação: configuração **Integral (Sum[Xdt]) / Per segment calculation**
fornecida pelo usuário; [discussão NI sobre acumulação e dt](https://forums.ni.com/t5/Industrial-Communications/Time-Domain-Math-VI-I-am-trying-to-integrate-a-data-streem-over/m-p/3145392)
e [reinicialização por segmento](https://forums.ni.com/t5/LabVIEW/reset-integral/m-p/1514200).

As funções históricas em `processamento/integracao.py` e a antiga janela em
`interface/integracao.py` permanecem para compatibilidade e seus testes; a tela
principal agora usa `processamento/cinematica.py` e `interface/cinematica.py`.
