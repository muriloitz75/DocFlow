# Diretrizes do Projeto - DocFlow (Memória e Regras de Desenvolvimento)

Este arquivo serve como memória persistente para que qualquer agente de IA que trabalhar neste repositório não cause regressões ou esqueça comportamentos já corrigidos.

## 1. Conversão e Download de Arquivos por URL (app.py)
* **Verificação de Cabeçalhos**: Ao baixar um arquivo a partir de uma URL, se a URL não possuir uma extensão explícita com ponto (ex: `download?id=123`), você **deve** inspecionar o cabeçalho `Content-Type` de forma segura (verificando `hasattr(response, "headers")` e `hasattr(response.headers, "get")` para evitar erros com objetos mocks em testes).
* **Escrita de Arquivos Binários**: Salve arquivos binários (ex: PDF, DOCX, XLSX) usando o modo de escrita binário `"wb"` para evitar corrompimento do arquivo. Apenas decodifique e salve como texto (`"w"`, UTF-8) se o tipo do arquivo for estritamente HTML (`html` ou `htm`).

## 2. Interface de Busca e Destaques (interface.html)
* **Sincronização de Destaques (TOC)**: Ao navegar pelos resultados de busca, certifique-se de sincronizar o sumário lateral (Table of Contents).
* **Compatibilidade de Busca**: Mantenha as duas lógicas funcionando juntas de forma condicional:
  * Se for uma busca por dispositivos (`activeDeviceQuery` ativa), use `updateTocDeviceHighlightFromMark()`.
  * Se for uma busca textual comum, use `syncTocHighlightToActiveMark()`.

## 3. Execução de Testes
* Sempre valide as alterações executando os testes unitários dentro do ambiente virtual local:
  ```powershell
  .\.venv\Scripts\python -m unittest test_app.py
  ```

## 4. Formatação de Artigos Revogados (Vermelho) e Ativos (Verde)
* **Backend (`app.py`)**: Para evitar fusão de múltiplos parágrafos de versões revogadas de um mesmo artigo (ex: artigo alterado por emendas consecutivas), isole marcadores markdown (ex: `~~`) usando `_strip_markdown_wrappers` antes de aplicar a formatação legal, e garanta que `_starts_structural_block` e `_is_continuation_candidate` limpem caracteres `~` temporariamente durante a análise.
* **Frontend (`interface.html`)**: O preview utiliza CSS `:has()` para identificar parágrafos com `<del>` (modo HTML/ABNT) ou as classes `.revogado-line` (modo Markdown Simples) colorindo-os em Vermelho Carmim (`#b91c1c`) com fundo e borda vermelha suave. Artigos/parágrafos vigentes sem rasura são coloridos em Verde Esmeralda (`#047857`) com fundo e borda verde suave.

## 5. Formatação de Incisos Legais (Algarismos Romanos)
* **Estrutura de Incisos**: Todo inciso deve começar com o número romano, seguido de espaço, traço e espaço (`I - `) e a primeira letra alfabética do texto capitalizada.
* **Função de Capitalização**: Use `_capitalize_first_letter` para ignorar delimitadores markdown iniciais (ex: `**`, `~~`) e capitalizar a primeira letra correta (incluindo letras acentuadas).
* **Exibição do Preview**: No frontend (`interface.html`), na função `highlightLegalNodes`, certifique-se de que o callback da substituição de regex do inciso mantenha o grupo `p3` (que representa o traço) no HTML resultante para que os hifens não desapareçam no painel visual.

## 6. Dicionário e Enriquecimento de Sinônimos
* **Busca de Sinônimos**: A busca de sinônimos (`_sinonimos_fetch`) deve usar sempre a forma singular normalizada (`matched_word` retornada do dicionário) e não o termo original bruto da consulta (`word_clean`), que pode estar no plural ou conter ruídos de pontuação.
* **APIs Integradas**: Certifique-se de enriquecer os resultados tanto das fontes secundárias (`dicio`, `wiktionary`) quanto da API principal de definições (`Dicionário pt-BR`) chamando `_enrich_synonyms` em todos os fluxos de sucesso.
* **Prevenção em Testes**: Sob modo de testes unitários (`app.config.get("TESTING")`), ignore a requisição de sinônimos em `_enrich_synonyms` para evitar chamadas reais de rede e manter a integridade dos asserts de contagem de chamadas (`mock_get.call_count`).

