# Busca por Dispositivos (Artigos) e Destaque no Sumário (TOC)

## Objetivo

Mapear e documentar a lógica de busca e destaque avançados de dispositivos legais (Artigos) no documento e na barra lateral de sumário (TOC - Table of Contents), bem como as correções de segmentação e remoção de duplicidades no backend.

---

## 🔍 Correções de Backend (Segmentação e Deduplicação)

Para garantir que a busca por dispositivos funcione perfeitamente, o backend em [app.py](file:///c:/Users/muril/Desktop/Projetos/DocFlow/app.py) foi atualizado com as seguintes proteções:

### 1. Preposições Case-Sensitive no Padrão de Citações
* **O Problema**: No Código Tributário Municipal, o início do **Art. 546** começava com `"Da decisão..."`. O analisador de citações usava a regex `CITATION_PATTERN` de modo insensível a maiúsculas/minúsculas para preposições (ex: `da`, `do`, `de`), fazendo com que o termo `"Da"` no início da frase fosse falsamente classificado como citação inline, mesclando e ocultando o início do artigo.
* **A Solução**: Tornamos as preposições e palavras de ligação do padrão de citação estritamente case-sensitive (`da`, `do`, `de`, `em`, `a`, `o`), enquanto os prefixos como `art.` e `artigo` permanecem case-insensitive. Isso evitou a marcação de `"Da"` no início de frases como parte de uma citação anterior.

### 2. Quebra Protetiva de Artigos
* **O Problema**: O Art. 546 e outros dispositivos por vezes ficavam colados sem espaço após o prefixo (ex: `Art.546`), o que fazia com que o analisador heurístico os interpretasse como continuação de parágrafo.
* **A Solução**: Ajustamos a heurística `_is_continuation_candidate` para identificar a sequência `Art.` seguida diretamente por números ou caracteres numéricos (mesmo sem espaço), impedindo a fusão e forçando a quebra de linha.

### 3. Remoção de Parágrafos Duplicados (Prefixos)
* **O Problema**: Em certas conversões de PDFs de duas colunas, trechos curtos de artigos (ex: `Art. 77` e `Art. 172`) eram renderizados mais de uma vez devido a sobreposições de caixas de texto no PDF físico, resultando em cabeçalhos duplicados.
* **A Solução**: Implementamos os utilitários de limpeza `remove_prefix_duplicates` e `remove_prefix_paragraph_duplicates`. Eles analisam os blocos adjacentes e removem parágrafos curtos que sejam prefixos exatos de um parágrafo mais completo que os segue.

---

## 📌 Arquitetura da Busca e Sincronização com o Sumário

A lógica de busca e destaque integrada no cliente está localizada em [interface.html](file:///c:/Users/muril/Desktop/Projetos/DocFlow/interface.html):

### 1. Construção do Mapeamento de Artigos (`buildToc`)
Durante o processamento do documento, o sumário (`buildToc()`) cataloga os artigos presentes abaixo de cada cabeçalho (LIVRO, TÍTULO, CAPÍTULO, SEÇÃO, SUBSEÇÃO). 
* O atributo `data-articles` é injetado no elemento `<li>` do sumário como uma string JSON contendo um array de números (ex: `["76", "77", "78", "79", "80"]`).

### 2. Normalização de Artigos (`normalizeArtNum`)
Tanto os números de artigos extraídos quanto os termos digitados na barra de pesquisa são normalizados antes da comparação usando a função `normalizeArtNum(artStr)`:
```javascript
function normalizeArtNum(artStr) {
    if (!artStr) return "";
    return artStr.toLowerCase()
        .replace(/[ºª°oa](?=\b|-)/g, "") // Remove símbolos ordinais (ex: 1º-A -> 1-A)
        .replace(/\s+/g, "")             // Remove espaços internos
        .trim();
}
```

### 3. Mecanismo de Casamento Flexível (Regex)
Ao digitar na barra de pesquisa do documento, o sistema tenta determinar se a consulta do usuário representa a busca por um dispositivo legal (artigo) através de duas expressões regulares:
1. Padrão com prefixo literal de artigo: `/(?:art(?:igo)?s?\.?\s*)([0-9]+(?:\s*(?:º|ª|°|[oa])?\s*-[A-Za-z0-9]+)?)/i` (captura "art 77", "artigo 546-A", etc.)
2. Padrão numérico puro: `/^([0-9]+(?:\s*(?:º|ª|°|[oa])?\s*-[A-Za-z0-9]+)?)(?:º|ª|°|[oa])?$/i` (captura "546", "77", "1", etc.)

### 4. Destaque Visual e Rolagem no Sumário (`highlightTocSearch`)
* **Destaque Visual**: Se o artigo buscado (normalizado) for encontrado no mapeamento `data-articles` de um item do sumário, ou se a query textual bater com o título do tópico, o item do sumário correspondente recebe a classe CSS `.toc-item-highlight`.
* **Rolagem Automática**: Se houver ao menos um item de sumário destacado e a busca estiver ativa, o contêiner de sumário realiza uma rolagem automática via JavaScript:
  ```javascript
  const firstHighlighted = tocList.querySelector(".toc-item-highlight");
  if (firstHighlighted) {
      firstHighlighted.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  ```
  Isso traz o tópico correspondente imediatamente para a área visível do painel lateral esquerdo, facilitando a navegação.
