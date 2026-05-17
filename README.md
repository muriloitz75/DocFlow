# DocFlow

Interface web local para conversão de documentos em **Markdown** ou **HTML**, construída sobre a biblioteca [MarkItDown](https://github.com/microsoft/markitdown) da Microsoft.

---

## Visão geral

O DocFlow oferece uma interface gráfica no navegador para converter arquivos de diversos formatos para texto estruturado, com tratamento especial para documentos jurídicos brasileiros (leis, decretos, regulamentos municipais).

## Funcionalidades

### Formatos suportados

| Categoria | Extensões |
|---|---|
| Documentos | PDF, DOCX, XLSX, XLS, PPTX |
| Web | HTML, HTM |
| Dados | CSV, JSON, XML |
| Imagens | PNG, JPG, JPEG, GIF, BMP |
| Áudio | MP3, WAV |
| Texto | TXT, MD |
| Outros | EPUB, ZIP |

Limite de upload: **100 MB** por arquivo.

### Modos de saída

| Modo | Descrição |
|---|---|
| **Padrão** | Conversão direta com limpeza de cabeçalhos/rodapés repetidos e formatação para PDFs |
| **Compacto** | Remove linhas em branco duplicadas para um resultado mais enxuto |
| **ABNT** | Numera títulos hierarquicamente (`1 INTRODUÇÃO`, `1.1 OBJETIVO`), força maiúsculas e reconhece estrutura legal (LIVRO, TÍTULO, CAPÍTULO, Seção) |

### Formatos de saída

- **Markdown** — arquivo `.md` com o texto estruturado
- **HTML** — arquivo `.html` completo com CSS embutido, texto justificado e estilos tipográficos

### Ações disponíveis

- **Copiar** — copia o conteúdo (Markdown ou HTML) para a área de transferência
- **Baixar** — gera o arquivo `.md` ou `.html` para download
- **Compartilhar** — usa a API nativa do navegador para compartilhar o conteúdo

---

## Pré-requisitos

- Python **3.10** ou superior
- Windows (testado no Windows 11)

---

## Instalação

```powershell
# 1. Clone o repositório
git clone <url-do-repositorio>
cd markitdown

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
cd markitdown
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
markitdown/
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

## Tratamento especial para PDFs jurídicos

O `app.py` contém lógica dedicada para documentos legais municipais:

- **Limpeza de cabeçalhos/rodapés** — remove marcas institucionais repetidas (ex.: DIAAF) detectadas por frequência entre páginas
- **Formatação modelo 2** — agrupa parágrafos fragmentados, formata artigos com negrito (`**Art. 1.**`), organiza incisos romanos e alíneas
- **Remoção de duplicatas** — detecta quando o PDF gerou o documento em duplicata e remove a segunda cópia
- **Correção de deslocamentos** — repara transposições de texto específicas de PDFs gerados por escâneres

---

## Testes

```powershell
.venv\Scripts\python.exe test_app.py
```

Os testes cobrem os endpoints da API, os modos de conversão e as funções de limpeza de Markdown, sem dependência de `pytest`.

---

## Base tecnológica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3 + Flask |
| Conversão | [MarkItDown](https://github.com/microsoft/markitdown) (Microsoft) |
| Frontend | HTML + CSS + JavaScript puro (sem frameworks) |
| Extração de PDF | pdfminer, pdfplumber, pypdfium2 |
| Documentos Office | mammoth (DOCX), python-pptx, openpyxl |
