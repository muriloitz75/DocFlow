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
