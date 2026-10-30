# Velocidade e deslocamento relativos

Na acelerometria, o sinal temporal continua em **g**. Após aplicar os
tratamentos desejados, selecione os acelerômetros/eixos e clique em
**Gerar velocidade**. Uma nova janela apresenta velocidade em **mm/s**;
a janela de aceleração permanece aberta. Mesmo com FFT ou RMS visível,
a entrada da integração é o sinal temporal tratado completo.

O cálculo ajusta por mínimos quadrados uma reta a cada canal de aceleração,
subtrai essa reta, converte g para mm/s² usando **1 g = 9806,65 mm/s²**
e integra pelo método dos trapézios cumulativos com velocidade inicial zero.

Na janela de velocidade, selecione os canais e clique em
**Gerar deslocamento**. O cálculo subtrai um ajuste quadrático por mínimos
quadrados de cada canal de velocidade e integra pelos trapézios, com
deslocamento inicial zero. O resultado em **mm** abre em outra janela.

Os resultados são **relativos ao início do intervalo** completo carregado,
identificado nas janelas. O eixo de tempo mantém os segundos da origem.
Zoom apenas altera a visualização; não recorta o intervalo integrado.
Esses resultados dependem da remoção de tendências e das condições iniciais
assumidas; não representam velocidade ou posição absoluta.

Cada resultado recebe uma cópia independente dos dados e da seleção de canais.
Alterar tratamentos, seleções ou reabrir arquivos na origem não altera os
resultados já gerados. Todas as janelas permitem selecionar canais e exportar
os gráficos visíveis em **SVG vetorial** e **HTML interativo**, com as unidades
e a referência temporal indicadas nos gráficos derivados.

## Verificação

Com as dependências da aplicação instaladas:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

A suíte cobre soluções polinomiais conhecidas, conversão de unidades, condições
iniciais, remoção de tendências, validação de entradas, uso do sinal tratado
com FFT/RMS ativos, preservação da origem, janelas independentes, seleção de
canais e gravação real de SVG/HTML, além das regressões de CSV e codificação.

## Identificar a revisão e o código aberto

A revisão **2026.10.30.2** mostra a versão no título e no rodapé da acelerometria,
com **Gerar velocidade** destacado em azul abaixo de FFT/RMS. O botão aparece
mesmo antes de abrir o CSV e habilita após uma importação válida.

O botão fica disponível nos modos temporal, FFT e RMS. O sinal temporal continua
em g; a visualização RMS AC existente continua em mg. FFT e RMS nunca são usados
como entrada da integração.

A seleção de canais dos resultados fica na lateral. As exportações derivadas
incluem o método, o intervalo temporal, a condição inicial e a referência ao início
do intervalo. A data de início do CSV é preservada na importação: mudar ou remover
o arquivo de origem não altera essa referência nas exportações dos resultados.

Fechar a aceleração mantém velocidade e deslocamento abertos. Fechar a velocidade
mantém o deslocamento aberto; os dados de uma janela fechada são liberados após
seu fechamento. Fechar resultados não altera os dados da origem.

Se o título não mostrar a revisão, consulte as instruções de atualização e de
abertura de uma cópia limpa no [README](../README.md).
