# Heurísticas de Detecção e Divisão de Layout de Duas Colunas em PDFs

## Objetivo

Mapear e documentar a lógica de detecção e divisão automática de páginas com layout de duas colunas (comum em Diários Oficiais), garantindo que:
1. Páginas com duas colunas sejam corretamente fatiadas verticalmente (esquerda/direita) para preservar a ordem correta de leitura.
2. Cabeçalhos de largura total (como títulos do diário, brasões e metadados no topo da página) sejam preservados em sua largura original acima da divisão de colunas.
3. Páginas de coluna única que contenham tabelas, assinaturas centralizadas, cabeçalhos ou listas justificadas não sofram divisões falsas (falsos positivos).

## Arquitetura e Algoritmo

A extração de texto estruturado ocorre no arquivo local [packages/markitdown/src/markitdown/converters/_pdf_converter.py](file:///c:/Users/muril/Desktop/Projetos/DocFlow/packages/markitdown/src/markitdown/converters/_pdf_converter.py). A função [extract_text_with_layout_and_columns](file:///c:/Users/muril/Desktop/Projetos/DocFlow/packages/markitdown/src/markitdown/converters/_pdf_converter.py#L510-L600) processa cada página seguindo estas etapas:

### 1. Filtragem da Região Central
Para identificar a calha ou sarjeta (gutter) entre as colunas, o algoritmo analisa apenas as palavras situadas no terço central horizontal da página (entre 40% e 60% da largura total da página). Isso evita que margens ou conteúdos exclusivos de uma das colunas interfiram na busca do divisor.

### 2. Agrupamento por Linhas Físicas (Densidade e Gaps)
As palavras da região central são agrupadas verticalmente em linhas físicas aproximadas (arredondando a coordenada `top` para múltiplos de 4 pontos). Em cada linha com palavras à esquerda e à direita do ponto central da página:
* Calcula-se se há um espaço em branco (gap) maior que 15 pontos de largura no terço central.
* Se sim, esse gap é registrado com sua coordenada horizontal e vertical.

### 3. Agrupamento de Calhas (Gutter Clustering)
Os gaps encontrados são agrupados por proximidade horizontal (dentro de uma tolerância de 20 pontos de distância de centro). O grupo mais frequente (com maior número de gaps verticais) é selecionado. A calha central (`gutter_x`) é definida como a média ponderada do centro desse grupo, e a largura é determinada pelo maior gap individual do grupo.

A linha mais alta onde a calha começa a ser detectada define o topo da região de colunas (`column_top`), ajustada com uma margem de segurança de 100 pontos para cima.

### 4. Validação Rigorosa (Filtro Anti-Falso Positivo)
Para validar se a calha detectada é real e a página é de fato de duas colunas, aplicam-se três critérios rigorosos:
1. **Frequência de Lacunas (`gaps_in_group >= 4`)**: O grupo de gaps vencedor deve ter no mínimo 4 ocorrências verticais na página. Isso impede que espaçamentos curtos em tabelas ou assinaturas forcem uma divisão de coluna.
2. **Densidade de Linhas (`pct_dense_rows >= 0.25`)**: Pelo menos 25% das linhas horizontais da página devem conter 6 ou mais palavras. Isso garante que a página possua um volume textual mínimo característico de texto corrido em colunas, evitando dividir páginas de capa, índices esparsos, ou folhas com assinaturas isoladas.
3. **Sobreposição de Palavras (`len(overlapping_words) <= 3`)**: Conta-se quantas palavras na região de colunas atravessam fisicamente a coordenada `gutter_x` (ou seja, têm `x0 < gutter_x < x1`). Se mais de 3 palavras cruzarem essa linha divisória, assume-se que há texto contínuo cruzando a calha (como títulos longos ou linhas de tabela de largura total) e a divisão é abortada.

Se qualquer uma das condições falhar, a página é tratada como coluna única e extraída de forma padrão.

### 5. Fatiamento e Preservação de Cabeçalho
Se a validação passar:
* O texto acima de `column_top` é extraído em largura total (preservando o cabeçalho/título da página).
* O restante da página é cortado verticalmente em duas caixas (`left_box` e `right_box`) divididas por `gutter_x`.
* O texto de ambas as caixas é extraído separadamente e concatenado na sequência correta: `[Cabeçalho] + [Coluna Esquerda] + [Coluna Direita]`.

---

## Verificação e Testes

Os testes automatizados em [test_app.py](file:///c:/Users/muril/Desktop/Projetos/DocFlow/test_app.py) cobrem esta funcionalidade:
* [test_pdf_converter_column_layout_detection](file:///c:/Users/muril/Desktop/Projetos/DocFlow/test_app.py#L698): Simula uma página com duas colunas contendo texto denso estruturado para verificar se o algoritmo divide as colunas e extrai o cabeçalho.
* Testes com mock de páginas de coluna única com pouca densidade ou palavras atravessando o divisor central para assegurar que não ocorra a divisão incorreta.
