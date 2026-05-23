# DocFlow

Interface web local para conversão de documentos em **Markdown** ou **HTML**, construída sobre a biblioteca [MarkItDown](https://github.com/microsoft/markitdown) da Microsoft.

---

## Visão geral

O DocFlow oferece uma interface gráfica no navegador para converter arquivos de diversos formatos para texto estruturado, com tratamento especial para documentos jurídicos brasileiros (leis, decretos, regulamentos municipais).

## Funcionalidades

### Formatos suportados

| Categoria | Extensões / Tipos |
|---|---|
| Documentos | PDF, DOCX, XLSX, XLS, PPTX |
| Web | HTML, HTM, **URLs Públicas** |
| Dados | CSV, JSON, XML |
| Imagens | PNG, JPG, JPEG, GIF, BMP |
| Áudio | MP3, WAV |
| Texto | TXT, MD |
| Outros | EPUB, ZIP |

Limites: **100 MB** por upload de arquivo. Suporte a extração e conversão de textos diretamente via **Links/URLs** copiados da web (como o portal do Planalto).

### Modos de saída

| Modo | Descrição |
|---|---|
| **Padrão** | Conversão direta com limpeza de cabeçalhos/rodapés repetidos e formatação para PDFs |
| **Compacto** | Remove linhas em branco duplicadas para um resultado mais enxuto |
| **ABNT** | Numera títulos hierarquicamente (`1 INTRODUÇÃO`, `1.1 OBJETIVO`), força maiúsculas e reconhece estrutura legal (LIVRO, TÍTULO, CAPÍTULO, Seção) |

### Formatos de saída

- **Markdown** — arquivo `.md` com o texto estruturado.
- **HTML** — arquivo `.html` completo com CSS embutido, texto justificado e estilos tipográficos elegantes.
- **JSON** — arquivo `.json` com a estrutura analítica completa do documento analisada no cliente, contendo metadados (nome do arquivo, modo, contagem de caracteres e linhas) e um array de blocos tipados (`heading`, `paragraph`, `list_item`, `code_block`, `table_row`, `blockquote`, `divider`).

### Ações disponíveis

- **Copiar** — copia o conteúdo ativo (Markdown, HTML ou JSON) para a área de transferência.
- **Baixar** — gera o arquivo `.md`, `.html` ou `.json` correspondente para download imediato.
- **Compartilhar** — usa a API nativa de compartilhamento (`navigator.share`) do navegador para compartilhar o conteúdo ativo.

---

## Pré-requisitos

- Python **3.10** ou superior
- Windows (testado no Windows 11)

---

## Instalação

```powershell
# 1. Clone o repositório
git clone <url-do-repositorio>
cd DocFlow

# 2. Crie o ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
.venv\Scripts\activate

# 4. Instale as dependências
pip install flask
pip install -e "packages/markitdown[all]"
```

---

## Como executar

```powershell
.venv\Scripts\python.exe app.py
```

Abra o navegador em: **http://localhost:5000**

Para parar o servidor, pressione `Ctrl+C` no terminal.

### Launcher alternativo

```powershell
.venv\Scripts\python.exe start.py
```

O `start.py` verifica as dependências, inicia o servidor e abre o navegador automaticamente.

---

## Estrutura do projeto

```
DocFlow/
├── app.py              # Backend Flask — API REST e lógica de transformação
├── interface.html      # Frontend single-page (HTML + CSS + JS)
├── start.py            # Launcher com abertura automática do navegador
├── test_app.py         # Testes unitários (unittest)
├── image/              # Imagens usadas na interface
├── packages/           # Código-fonte local do MarkItDown e plugins
│   ├── markitdown/
│   ├── markitdown-mcp/
│   ├── markitdown-ocr/
│   └── markitdown-sample-plugin/
└── .venv/              # Ambiente virtual Python
```

---

## API

### `GET /`
Serve a interface HTML.

### `GET /api/health`
Verifica o estado do servidor.

```json
{
  "status": "ok",
  "markitdown": "ready",
  "maxUploadMb": 100,
  "formats": ["bmp", "csv", "docx", ...]
}
```

### `POST /api/convert`
Converte um arquivo para Markdown.

**Parâmetros (multipart/form-data):**

| Campo | Tipo | Descrição |
|---|---|---|
| `file` | arquivo | Arquivo a converter |
| `option` | string | `standard` \| `compact` \| `abnt` |

**Resposta:**

```json
{
  "success": true,
  "content": "# Título\n\nConteúdo...",
  "filename": "documento.pdf",
  "mode": "standard",
  "characters": 15420,
  "originalCharacters": 15420,
  "truncated": false
}
```

> O conteúdo é truncado em **1 MB** caso o documento seja muito extenso.

### `GET /image/<filename>`
Serve arquivos estáticos da pasta `image/`.

---

## Tratamento especial para textos jurídicos

O sistema contém lógicas dedicadas (no Backend e no Frontend) para melhorar drasticamente a legibilidade de documentos legais e governamentais:

- **Limpeza de cabeçalhos/rodapés** — remove marcas institucionais repetidas (ex.: DIAAF) detectadas por frequência entre páginas.
- **Estruturação hierárquica** — agrupa parágrafos fragmentados, formata artigos com negrito (`**Art. 1.**`), e organiza corretamente as classificações de Capítulos, Seções, e Subseções, além de extrair títulos especiais como `DISPOSIÇÕES GERAIS`.
- **Destaque Visual Inteligente** — a própria interface aplica colorização automática da taxonomia legal (Artigos em Laranja, Parágrafos em Verde, Incisos em Azul e Alíneas em Roxo), ignorando menções no meio do texto e aplicando apenas para as aberturas de bloco.
- **Remoção de duplicatas** — detecta quando o PDF gerou o documento em duplicata (anexos inteiros idênticos) e remove a segunda cópia.
- **Correção de deslocamentos** — repara transposições de texto específicas de PDFs gerados por escâneres e protege menções legais (ex: de leis e parágrafos) para que não quebrem o formato do documento.

---

## Testes

```powershell
.venv\Scripts\python.exe test_app.py
```

Os testes cobrem os endpoints da API, os modos de conversão e as funções de limpeza de Markdown, sem dependência de `pytest`.

---

## Deploy e Produção (Railway)

O projeto está totalmente preparado e configurado para deploy imediato no **Railway**. Os seguintes arquivos gerenciam essa infraestrutura:

- **`Procfile`** — define o comando de inicialização do servidor de produção utilizando o **Gunicorn** (servidor WSGI robusto de nível industrial):
  ```text
  web: gunicorn --bind 0.0.0.0:$PORT app:app
  ```
- **`runtime.txt`** — fixa a versão do Python no Railway para `python-3.11.9`.
- **`requirements.txt`** — lista todas as dependências externas puras e independentes de caminhos locais, garantindo cacheamento ultra-rápido no Railpack.

### Processo de Build automático no Railway:
1. O Railway detecta a configuração do Python automaticamente.
2. Instala pacotes do sistema como **`ffmpeg`** (utilizado pelo `pydub`).
3. Instala as dependências e executa o servidor de produção respondendo a requisições de forma robusta e otimizada.

---

## Base tecnológica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3 + Flask |
| Conversão | [MarkItDown](https://github.com/microsoft/markitdown) (Microsoft) |
| Frontend | HTML + CSS + JavaScript puro (sem frameworks) |
| Extração de PDF | pdfminer, pdfplumber, pypdfium2 |
| Documentos Office | mammoth (DOCX), python-pptx, openpyxl |
