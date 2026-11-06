# Régua potenciométrica Lynx

## Abrir e selecionar os canais

1. Inicie com `python main.py` e escolha **Lynx → Régua potenciométrica**.
2. Clique em **Abrir arquivo** e escolha o CSV Lynx.
3. Confira o aviso das outras unidades, quando o arquivo contiver medições mistas.
4. Selecione os canais de deslocamento na lista lateral.

O formato é o mesmo das outras análises: linhas `Name`, `Unit`, `HighLim`,
`LowLim`, `Time (s)`, seguidas das medições. A seleção usa a unidade **mm**,
independentemente do nome, da ordem ou da quantidade de canais. A posição da
coluna identifica o canal: um canal na posição 16 continua sendo o canal 16.
Nomes repetidos são permitidos e nomes vazios recebem um rótulo pela posição.

São importados apenas os canais em mm; `g`, `MPa`, `μm/m` e `mm/m` pertencem
às outras análises. Em particular, **mm/m é deformação**, não deslocamento.
Os codecs, separadores decimais e verificações de CSV são os mesmos das demais
modalidades. A última linha incompleta exige confirmação antes de ser ignorada
apenas na importação, preservando o arquivo original.

## Valores e tratamentos

O CSV já fornece os valores em mm. A janela mostra diretamente essas medições:
por exemplo, `-7,11E+00` aparece como **−7,11 mm**, com sinal e referência inicial
preservados. Não é necessário integrar o sinal. A janela não presume propriedades
elétricas ou calibração específica de um modelo de sensor.

Os controles disponíveis são os mesmos tratamentos comuns da extensometria:

- **Fator de calibração:** multiplica o sinal pelo fator informado.
- **Offset:** subtrai a média das primeiras N amostras de cada canal. É opcional
  e permite escolher uma referência para o deslocamento.
- **Remover outliers:** substitui candidatos pela mediana local, com limiar e
  janela de amostras definidos pelo usuário, sem apagar linhas.
- **Passa-alta** e **passa-baixa:** cortes em Hz, respeitando a frequência de Nyquist.
- **Média móvel:** janela em número de amostras.

Cada botão **Aplicar** recalcula os tratamentos a partir dos dados originais,
na ordem comum: calibração, outliers, offset, passa-alta, passa-baixa e média móvel.
Os tratamentos atuam nos canais em mm carregados; as marcas laterais controlam
a exibição e a exportação. **Restaurar original** remove os tratamentos e recupera
os valores importados. Uma importação inválida preserva o arquivo anterior.

Um sinal constante ou com amostras fora dos limites declarados recebe um aviso
de qualidade, mas continua disponível para análise. O asterisco na lista indica
os canais com esses avisos. O CSV não é regravado pelos tratamentos.

## Horário, escala e exportação

O eixo X segue a mesma regra das outras telas: **horário inicial do CSV − 3 horas**,
somado ao tempo da amostra. O painel apresenta a referência reconhecida e oferece
**Detalhes do horário** e **Definir horário…**. Sem data válida, o sinal permanece
em segundos com aviso explícito.

Use os campos de escala para informar os limites em mm e os campos de tempo para
informar segundos relativos à referência do CSV. **Aplicar escala e tempo** muda
a vista, e **Ajustar aos dados** enquadra os canais selecionados. Esses controles
não recortam nem alteram os dados recebidos.

O menu **Exportar** oferece **SVG vetorial** e **HTML interativo**. As exportações
contêm os canais selecionados com os valores tratados em mm e preservam a escala
e o intervalo inicialmente visíveis. Todos os pontos são enviados à exportação,
mesmo que a tela reduza os pontos desenhados para exibir registros longos.

Essa janela é independente das análises de acelerometria e extensometria.
Fechar e reabrir a opção no menu Lynx recupera a janela com seus dados atuais.
