# Reta removida do deslocamento e verificação por derivação

> Documento histórico da revisão 2026.11.12.1. O fluxo atual (2026.11.13.1) usa
> soma por segmento, reta após a velocidade e grau 2 após a posição. Consulte
> [o guia atual](INTEGRACAO_ACELEROMETRIA.md).

Na revisão **2026.11.12.1**, o fluxo mantém os tratamentos escolhidos e a opção
de retirar somente a média da aceleração. Ao clicar em **Gerar velocidade**,
a conversão é automática: **g × 9,80665 → m/s² → integrar → m/s × 1000 → mm/s**.
O deslocamento é obtido integrando essa velocidade, em mm/s, para mm.

## Ajuste após a segunda integração

A nova janela de deslocamento apresenta **Retirar reta do deslocamento** marcada
por padrão. Para cada canal, ajusta por mínimos quadrados uma reta ao
deslocamento integrado completo. Com τ = t − t₀:

```text
reta(τ) = b + mτ
deslocamento_exibido(τ) = deslocamento_integrado(τ) − reta(τ)
```

`b` é o intercepto em mm e `m` é a inclinação em mm/s. O ajuste usa tempo
normalizado para estabilidade em registros longos. Não se ajusta uma reta à
aceleração nem uma quadrática à velocidade. A janela de origem é preservada.

Desmarque a opção para comparar com a integral antes do ajuste; marcar novamente
recalcula a partir da cópia preservada, sem acumular correções. **Detalhes do
ajuste** mostra os coeficientes e o valor inicial corrigido por canal. CSV e
HTML registram o método e os coeficientes. SVG identifica a correção na descrição.

O ajuste usa todo o registro carregado. Os campos de intervalo em minutos continuam
controlando apenas visualização e exportação, sem recalcular as integrações ou
refazer o ajuste no trecho visível.

## Referência inicial

A integral anterior ao ajuste começa em `d₀ = 0`. A subtração da reta completa
faz o deslocamento corrigido começar em **−b**, em geral diferente de zero.
O programa identifica essa diferença e não reancora o resultado silenciosamente.
As condições iniciais da aceleração→velocidade e da integral bruta permanecem zero.

Uma constante na velocidade produz uma rampa no deslocamento. Esse é o modelo
removido pelo ajuste. Um viés constante na aceleração produz uma parábola no
deslocamento, que uma reta não consegue eliminar. Transientes e desvios variáveis
também podem manter tendências depois da correção.

## Verificar por derivação

O botão **Verificar por derivação** abre outra janela com:

- Velocidade obtida derivando o deslocamento exibido, em mm/s.
- Aceleração obtida por duas derivações, em g.
- Aceleração efetivamente usada na integração, quando disponível, e a velocidade
  de origem para comparação.
- RMSE, erro máximo, NRMSE e correlação por canal, nos detalhes do resultado.

A referência é a aceleração **após filtros e retirada de média escolhidos**,
não o CSV bruto. A verificação usa `numpy.gradient` em duas etapas, com
`edge_order=2`. As métricas desconsideram duas amostras de cada extremidade
quando há pelo menos cinco amostras. A janela permite selecionar canais e
exportar SVG, HTML e CSV; o CSV pode ser reaberto em Dados tratados.

Para o modelo contínuo, as identidades são:

```text
derivada(D − b − mτ) = V − m
segunda_derivada(D − b − mτ) = A
```

Por isso a velocidade derivada pode diferir da janela de velocidade original por
uma constante. A segunda derivada elimina qualquer reta: essa propriedade não
prova que a rampa removida era um erro instrumental ou que a posição corrigida
seja a posição física real. Posição e velocidade iniciais exigem informação adicional.

## Erro numérico da volta

Integração trapezoidal seguida de diferenças centrais não é uma identidade
amostra a amostra. Em amostragem uniforme, no interior do registro:

```text
A_rec[i] = (A[i−2] + 4A[i−1] + 6A[i] + 4A[i+1] + A[i+2]) / 16
```

O ganho de amplitude para uma componente harmônica é `cos⁴(πf/fs)`. A 200 Hz,
uma componente de 30 Hz volta com aproximadamente 63% da amplitude após esse
par de integrações/derivações. Correlação alta também não certifica amplitude
exata. A interface apresenta os erros em vez de presumir que a recuperação é exata.

## Evidência e limites

No CSV completo enviado para validação, foram verificados 124.740 pontos por
canal, 12 canais em g, 200 Hz e 623,695 s. O canal da régua, em mm, foi excluído:
o usuário informou que ele mede outro ponto. O ajuste foi verificado contra
uma solução independente em precisão estendida, com tratamentos sem filtro e
com passa-banda 1–30 Hz, ambos com a opção de retirada da média da aceleração.

O método removeu a componente linear, mas não todas as tendências dos dados
reais. A dupla derivação preservou praticamente a mesma aceleração numérica
com e sem a reta; a comparação com a entrada ainda apresentou o erro esperado
do par integrar/derivar. Não se certificou o deslocamento físico da estrutura.

A retirada de média **depois** de um passa-banda também pode influenciar tendências
lentas, pois a média finita depende das extremidades. O programa mantém a
escolha explícita dessa opção; não altera os tratamentos para obter uma curva
visualmente menor.

O procedimento da imagem fornecida foi reproduzido em uma simulação amortecida
com solução analítica conhecida. Não foi possível reproduzir o link original
do vídeo; a [descrição pública do tutorial relacionado do autor](https://www.youtube.com/watch?v=SCZBaOkHB_Y)
descreve a remoção de rampa e também ressalta limitações com sinais reais.

