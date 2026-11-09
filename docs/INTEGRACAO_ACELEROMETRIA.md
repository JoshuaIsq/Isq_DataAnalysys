# Velocidade e deslocamento relativos

Na acelerometria, o sinal temporal continua em **g**. Após aplicar os
tratamentos desejados, selecione os acelerômetros/eixos e clique em
**Gerar velocidade**. Uma nova janela apresenta velocidade em **mm/s**;
a janela de aceleração permanece aberta. Mesmo com FFT ou RMS visível,
a entrada da integração é o sinal temporal tratado completo.

Desde a revisão **2026.11.09.1**, o cálculo integra diretamente cada canal do
sinal tratado, sem subtrair média ou reta. Converte g para mm/s² usando
**1 g = 9806,65 mm/s²** e integra pelos trapézios cumulativos, com velocidade
inicial zero. Nenhum tratamento adicional é aplicado durante a integração.

Na janela de velocidade, selecione os canais e clique em
**Gerar deslocamento**. O cálculo integra a velocidade exibida, sem subtrair
quadrática ou recentrar o sinal. Usa os trapézios e deslocamento inicial zero.
O resultado em **mm** abre em outra janela.

Os resultados são **relativos ao início do intervalo** completo carregado,
identificado nas janelas. Os cálculos mantêm os segundos da origem; quando
há data inicial válida, o eixo mostra data/hora local com a redução de três
horas do CSV.
Zoom apenas altera a visualização; não recorta o intervalo integrado.
Os resultados dependem dos tratamentos escolhidos e das condições iniciais
assumidas; não representam velocidade ou posição absoluta.

Cada resultado recebe uma cópia independente dos dados e da seleção de canais.
Alterar tratamentos, seleções ou reabrir arquivos na origem não altera os
resultados já gerados. Todas as janelas permitem selecionar canais e exportar
os gráficos visíveis em **SVG vetorial** e **HTML interativo**, com as unidades
e a referência temporal indicadas nos gráficos derivados. O método e a lista
dos tratamentos da aceleração ficam registrados no resultado e nas exportações,
mesmo depois de alterar ou fechar a janela de origem.

## O que a integral fiel garante

Para cada canal, em cada intervalo de amostragem:

```text
v[0] = 0
v[i] − v[i−1] = 9806,65 × (a[i−1] + a[i]) / 2 × (t[i] − t[i−1])
d[0] = 0
d[i] − d[i−1] = (v[i−1] + v[i]) / 2 × (t[i] − t[i−1])
```

`a` contém exatamente as amostras tratadas selecionadas na acelerometria;
`v` contém exatamente as amostras exibidas na janela de velocidade.
As igualdades estão sujeitas ao arredondamento de ponto flutuante. Não há
uso de FFT/RMS, imposição de repouso no final, remoção automática de deriva
ou modificação das medições de origem. Duas amostras válidas bastam para
calcular uma área.

Cada etapa é a integral da interpolação linear das suas amostras de entrada.
Isso define uma referência matemática verificável, mas não determina o sinal
contínuo desconhecido entre as amostras. Aplicar trapézios duas vezes também
aproxima o deslocamento do movimento contínuo; não torna essa dupla integral
fisicamente exata.

Por exemplo, para uma componente harmônica de frequência `f`, amostrada em
`fs`, a razão da amplitude dos trapézios para a integração contínua em regime
é `z/tan(z)`, com `z = πf/fs`, em cada etapa. A 200 Hz, uma componente de 5 Hz
tem aproximadamente 0,206% de redução de amplitude na velocidade e 0,411%
no deslocamento após duas etapas. A 30 Hz, as reduções são cerca de 7,51%
e 14,46%. Esses valores isolam a discretização; não incluem o ganho do filtro,
transientes, ruído, calibração ou incerteza das condições iniciais. Portanto,
concordância entre dois cálculos dos trapézios não certifica essa mesma precisão
em relação ao movimento físico.

## Deriva e filtros

Deriva é a mudança lenta que se acumula nas integrais. Uma aceleração residual
constante `b` produz `Δv = b × t` e `Δd = b × t²/2`. Apenas **0,000001 g**,
ao longo de 60 s, acrescenta **0,588399 mm/s** e **17,65197 mm**. A integral
fiel preserva isso, seja a componente causada por movimento, sensor ou filtro.

Um sinal oscilatório também pode produzir uma velocidade com média diferente
de zero quando se impõe v[0] = 0 em uma fase arbitrária. A condição inicial
não é uma estimativa automática da velocidade física do sensor. Essa média
gera uma componente linear no deslocamento, mesmo sem aceleração constante.

Filtros alteram as amostras e, consequentemente, suas integrais. O passa-banda
remove componentes fora da banda e apresenta transientes nas extremidades.
Filtrar um recorte não é equivalente a recortar um registro já filtrado,
especialmente perto das bordas. O Butterworth em ida e volta tem ganho de
aproximadamente 0,5 nos cortes informados (−6 dB), não ganho unitário em toda
a banda. Não se espera recuperar por integração as componentes removidas.

Com passa-banda de 1–30 Hz, os resultados derivam da aceleração nessa banda,
sob as condições iniciais escolhidas. Não são uma medição garantida de
deslocamento estático, permanente ou total. Uma régua só pode ser comparada
considerando o mesmo ponto, direção, tempo e banda relevante.

### Mudança em relação às versões anteriores

Até **2026.11.06.3**, a integração removia uma reta da aceleração e uma
quadrática da velocidade automaticamente. Esses ajustes globais podiam
introduzir componentes lentas depois do passa-banda e faziam o deslocamento
integrar uma velocidade diferente da exibida. A revisão **2026.11.09.1**
retira esses dois ajustes conforme a escolha pela integral fiel.

Resultados novos podem mostrar valores maiores ou deriva que antes era
removida. Não devem ser confundidos com confirmação de deslocamento físico.
É preciso gerar novas janelas para usar o método novo; resultados anteriores
não são recalculados automaticamente.

## Verificação

Com as dependências da aplicação instaladas:

```sh
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

A suíte cobre soluções constantes, polinomiais e harmônicas conhecidas,
conversão de unidades, condições iniciais, preservação das tendências,
referência numérica independente em precisão estendida, validação de entradas, uso do sinal tratado
com FFT/RMS ativos, preservação da origem, janelas independentes, seleção de
canais e gravação real de SVG/HTML, além das regressões de CSV e codificação.

## Identificar a revisão e o código aberto

A revisão **2026.10.30.3** mostra a versão no título e no rodapé da acelerometria,
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
consolidação do projeto no [guia de migração](MIGRACAO.md).
