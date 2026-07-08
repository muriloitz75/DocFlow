# -*- coding: utf-8 -*-
"""Backend Flask da interface web do MarkItDown."""

from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
import re
import shutil
import tempfile
import sys
import json
import time
import threading
import unicodedata
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from uuid import uuid4
from functools import wraps

# Adicionar o diretório do markitdown ao path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))

from markitdown import MarkItDown, StreamInfo
from markitdown.converters._pdf_converter import extract_text_with_layout_and_columns

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "docflow-secret-key-123456"

# Configurações de autenticação
APP_USER = os.environ.get("APP_USER") or "admin"
APP_PASSWORD = os.environ.get("APP_PASSWORD") or "admin"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if app.config.get("TESTING"):
            return f(*args, **kwargs)
        if not session.get("logged_in"):
            return jsonify({"success": False, "error": "Autenticação requerida."}), 401
        return f(*args, **kwargs)
    return decorated_function


# Configurações
UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "markitdown-web")
SAVED_DOCS_DIR = os.path.join(BASE_DIR, "saved_docs")
os.makedirs(SAVED_DOCS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "pdf", "docx", "xlsx", "xls", "pptx",
    "html", "htm", "csv", "json", "xml",
    "png", "jpg", "jpeg", "gif", "bmp",
    "mp3", "wav", "txt", "md", "epub",
    "zip",
}

app.config["UPLOAD_FOLDER"] = UPLOAD_ROOT
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB
app.config["JSON_SORT_KEYS"] = False

# Inicializar MarkItDown
md_converter = MarkItDown(enable_plugins=False)

# Dicionario cache configuracoes e infraestrutura
DICT_CACHE_TTL = int(os.environ.get("DICT_CACHE_TTL", 86400))
DICT_CACHE_MAX = int(os.environ.get("DICT_CACHE_MAX", 500))
DICT_API_TIMEOUT = int(os.environ.get("DICT_API_TIMEOUT", 10))
DICT_API_MAX_RETRIES = int(os.environ.get("DICT_API_MAX_RETRIES", 1))
DICT_API_BASE_URL = os.environ.get("DICT_API_BASE_URL", "https://api.dicionario-aberto.net/word")

_dict_cache = {}
_dict_cache_lock = threading.Lock()

DATA_DIR = os.path.join(BASE_DIR, "data")
_plural_exceptions = None
_offline_dict = None


def _load_plural_exceptions():
    global _plural_exceptions
    if _plural_exceptions is not None:
        return _plural_exceptions
    try:
        path = os.path.join(DATA_DIR, "plural_exceptions.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _plural_exceptions = json.load(f)
        else:
            _plural_exceptions = {}
    except Exception:
        _plural_exceptions = {}
    return _plural_exceptions


def _load_offline_dict():
    global _offline_dict
    if _offline_dict is not None:
        return _offline_dict
    try:
        path = os.path.join(DATA_DIR, "pt_br_legal.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _offline_dict = json.load(f)
        else:
            _offline_dict = {}
    except Exception:
        _offline_dict = {}
    return _offline_dict


def dict_cache_get(key):
    with _dict_cache_lock:
        entry = _dict_cache.get(key)
        if entry and (time.time() - entry["ts"]) < DICT_CACHE_TTL:
            return entry["data"]
        elif entry:
            del _dict_cache[key]
        return None


def dict_cache_set(key, data):
    with _dict_cache_lock:
        if len(_dict_cache) >= DICT_CACHE_MAX:
            oldest = sorted(_dict_cache.items(), key=lambda x: x[1]["ts"])[0][0]
            del _dict_cache[oldest]
        _dict_cache[key] = {"data": data, "ts": time.time()}


# Cache de diarios oficiais — armazenado em disco para compatibilidade com multi-worker
GAZETTE_CACHE_DIR = os.path.join(tempfile.gettempdir(), "markitdown-web", "gazette_cache")


def _gazette_meta_path(cache_id):
    return os.path.join(GAZETTE_CACHE_DIR, f"{cache_id}.json")


def gazette_cache_get(cache_id):
    meta_path = _gazette_meta_path(cache_id)
    if not os.path.exists(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        pdf_path = os.path.join(GAZETTE_CACHE_DIR, f"{cache_id}.pdf")
        if not os.path.exists(pdf_path):
            return None
        return {
            "pdf_path": pdf_path,
            "norms": meta["norms"],
            "total_pages": meta["total_pages"],
            "index_text": meta.get("index_text", ""),
            "index_entries": meta.get("index_entries", []),
        }
    except Exception:
        return None


def gazette_cache_set(cache_id, pdf_path, norms, total_pages, index_text="", index_entries=None):
    os.makedirs(GAZETTE_CACHE_DIR, exist_ok=True)
    meta = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_pages": total_pages,
        "norms": norms,
        "index_text": index_text,
        "index_entries": index_entries or [],
    }
    with open(_gazette_meta_path(cache_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


GAZETTE_NORM_RE = re.compile(
    r"^\s*("
    r"LEI\s+COMPLEMENTAR|LEI\s+ORDIN[ÁA]RIA|LEI|"
    r"DECRETO\s+LEGISLATIVO|DECRETO|"
    r"PORTARIA\s+CONJUNTA|PORTARIA|"
    r"RESOLU[ÇC][ÃA]O|RESOLUCAO|"
    r"INSTRU[ÇC][ÃA]O\s+NORMATIVA|"
    r"DELIBERA[ÇC][ÃA]O|DELIBERACAO|"
    r"EDITAL|"
    r"ATO\s+NORMATIVO|ATO"
    r")\s+(?:Nº|N[°ºo]\.?)\s*([\w.\/-]+)",
    re.IGNORECASE | re.MULTILINE
)


def is_index_page(text):
    """Verificar se o texto de uma página corresponde a um sumário/índice."""
    # Cabeçalho explícito de índice/sumário
    if re.search(r"^\s*(Índice|Sumário|Sumario|SUMÁRIO|ÍNDICE)\b", text, re.IGNORECASE | re.MULTILINE):
        return True

    # Padrão clássico: "........ 20" ao final de cada linha (requer re.MULTILINE)
    inline_dots = re.compile(r"\.{3,}\s*\d+\s*$", re.MULTILINE)
    if len(inline_dots.findall(text)) >= 2:
        return True

    # Linhas compostas apenas por pontos (líder de tabulação de sumários)
    dot_only_line = re.compile(r"^\s*\.{5,}\s*\d*\s*$", re.MULTILINE)
    if len(dot_only_line.findall(text)) >= 2:
        return True

    return False


def _normalize_gazette_index_key(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _normalize_gazette_search_text(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _gazette_index_row_levels(parsed):
    indent_values = sorted({row["indent"] for row in parsed})
    indent_levels = {indent: min(position, 2) for position, indent in enumerate(indent_values)}
    section_prefixes = (
        "gabinete", "secretaria", "comissão", "comissao", "prefeitura",
        "câmara", "camara", "procuradoria", "controladoria", "fundação", "fundacao",
    )

    for row in parsed:
        level = indent_levels.get(row["indent"], 0)
        if len(indent_values) < 2:
            lowered = row["text"].lower()
            if lowered.startswith(section_prefixes):
                level = 0
            elif re.search(
                r"\b(?:n[º°o]\.?\s*)?\d+[./-]\d+|\bde\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}",
                row["text"], re.IGNORECASE,
            ):
                level = 2
            else:
                level = 1
        row["level"] = level
        row["role"] = ("section", "category", "document")[level]


def _infer_gazette_document_identity(category, title):
    explicit = re.match(
        r"^\s*(.*?)\s+N(?:º|°|o\.)\s*([\w./-]+)", title, re.IGNORECASE,
    )
    if explicit:
        tipo = explicit.group(1).strip() or category.strip()
        return tipo.upper(), explicit.group(2).strip()

    number_only = re.match(r"^\s*N(?:º|°|o\.)\s*([\w./-]+)", title, re.IGNORECASE)
    if number_only:
        return category.strip().upper(), number_only.group(1).strip()

    if re.match(r"^\s*ERRATA\b", title, re.IGNORECASE):
        return "ERRATA", ""

    loose_number = re.search(r"\b(\d+[./-]\d+(?:[\w./-]*))\b", title)
    if loose_number and category:
        return category.strip().upper(), loose_number.group(1).strip()

    first_phrase = re.split(r"\s[-–—]\s|[.:]", title, maxsplit=1)[0].strip()
    return (first_phrase or category or "DOCUMENTO").upper(), ""


def _find_gazette_title_page(title, indexed_page, body_pages):
    normalized_title = _normalize_gazette_search_text(title)
    if len(normalized_title) < 8:
        return None, None

    ordered_pages = sorted(body_pages.items(), key=lambda item: (abs(item[0] - indexed_page), item[0]))
    for page_num, page_text in ordered_pages:
        normalized_page = _normalize_gazette_search_text(page_text)
        position = normalized_page.find(normalized_title)
        if position >= 0:
            return page_num, position
    return None, None


def _add_index_document_candidates(index_entries, norms, body_pages):
    current_category = ""
    existing_titles = {
        _normalize_gazette_index_key(
            norm.get("title") or f"{norm.get('tipo', '')} Nº {norm.get('numero', '')}"
        )
        for norm in norms
    }

    for entry in index_entries:
        if entry["role"] == "section":
            current_category = ""
            continue
        if entry["role"] == "category":
            current_category = entry["text"]
            continue
        if entry["role"] != "document" or entry.get("norm_id") is not None:
            continue

        title = entry["text"].strip()
        title_key = _normalize_gazette_index_key(title)
        if not title_key or title_key in existing_titles:
            continue

        page_num, body_position = _find_gazette_title_page(title, entry["page"], body_pages)
        search_key_len = len(_normalize_gazette_search_text(title))

        if page_num is None:
            # Fallback: título composto pode não aparecer verbatim no corpo.
            # Tentar com prefixo de 4 ou 3 palavras normalizadas.
            words = _normalize_gazette_search_text(title).split()
            ordered_pages = sorted(
                body_pages.items(), key=lambda kv: (abs(kv[0] - entry["page"]), kv[0])
            )
            for prefix_len in (4, 3):
                if len(words) < prefix_len:
                    continue
                short_key = " ".join(words[:prefix_len])
                if len(short_key) < 8:
                    continue
                for pg, pg_text in ordered_pages:
                    pos = _normalize_gazette_search_text(pg_text).find(short_key)
                    if pos >= 0:
                        page_num, body_position, search_key_len = pg, pos, len(short_key)
                        break
                if page_num is not None:
                    break
            if page_num is None:
                continue

        tipo, numero = _infer_gazette_document_identity(current_category, title)
        page_text = body_pages[page_num]
        normalized_page = _normalize_gazette_search_text(page_text)
        remainder = normalized_page[body_position + search_key_len:].strip()
        ementa = remainder[:200]
        if len(remainder) > 200:
            ementa = ementa.rsplit(" ", 1)[0] + "..."

        norms.append({
            "id": len(norms),
            "tipo": tipo,
            "numero": numero,
            "title": title,
            "ementa": ementa,
            "start_page": page_num,
            "end_page": page_num,
            "_body_order": (page_num, body_position),
        })
        existing_titles.add(title_key)


def _linked_gazette_norm_ids(index_entries):
    linked_ids = []
    for entry in index_entries or []:
        norm_id = entry.get("norm_id")
        if entry.get("role") == "document" and norm_id is not None and norm_id not in linked_ids:
            linked_ids.append(norm_id)
    return linked_ids


def _next_linked_gazette_norm_id(index_entries, norm_id):
    linked_ids = _linked_gazette_norm_ids(index_entries)
    try:
        position = linked_ids.index(norm_id)
    except ValueError:
        return None
    if position + 1 >= len(linked_ids):
        return None
    return linked_ids[position + 1]


def _apply_linked_gazette_page_ranges(norms, index_entries, total_pages):
    norms_by_id = {norm["id"]: norm for norm in norms}
    linked_ids = _linked_gazette_norm_ids(index_entries)
    for position, norm_id in enumerate(linked_ids):
        norm = norms_by_id.get(norm_id)
        if not norm:
            continue
        if position + 1 < len(linked_ids):
            next_norm = norms_by_id.get(linked_ids[position + 1])
            if next_norm:
                norm["end_page"] = next_norm["start_page"]
        else:
            norm["end_page"] = total_pages


def parse_gazette_index_rows(index_text, norms):
    """Transform extracted index text into visual rows linked to detected norms."""
    raw_lines = (index_text or "").splitlines()
    parsed = []
    index = 0

    while index < len(raw_lines):
        raw_line = raw_lines[index].rstrip()
        stripped = raw_line.strip()
        index += 1

        if not stripped or re.fullmatch(r"(?:índice|indice|sumário|sumario)", stripped, re.IGNORECASE):
            continue

        inline_match = re.match(r"^(.*?)(?:\.\s*){3,}(\d+)\s*$", raw_line)
        if inline_match:
            text = inline_match.group(1).strip()
            page = int(inline_match.group(2))
        elif index + 1 < len(raw_lines) and re.fullmatch(r"\s*(?:\.\s*){3,}", raw_lines[index]):
            page_match = re.fullmatch(r"\s*(\d+)\s*", raw_lines[index + 1])
            if not page_match:
                continue
            text = stripped
            page = int(page_match.group(1))
            index += 2
        else:
            continue

        if text:
            parsed.append({
                "text": text,
                "page": page,
                "indent": len(raw_line) - len(raw_line.lstrip()),
            })

    _gazette_index_row_levels(parsed)

    norm_keys = []
    for norm in norms or []:
        norm_keys.append((
            norm.get("id"),
            _normalize_gazette_index_key(norm.get("tipo")),
            _normalize_gazette_index_key(norm.get("numero")),
            _normalize_gazette_index_key(norm.get("title")),
        ))

    rows = []
    current_category = ""
    for row in parsed:
        if row["role"] == "section":
            current_category = ""
        elif row["role"] == "category":
            current_category = row["text"]

        match_text = row["text"]
        if row["role"] == "document" and current_category:
            match_text = f"{current_category} {match_text}"
        normalized_text = _normalize_gazette_index_key(match_text)
        norm_id = None
        row_text_key = _normalize_gazette_index_key(row["text"])
        for candidate_id, type_key, number_key, title_key in norm_keys:
            if title_key and title_key == row_text_key:
                norm_id = candidate_id
                break
            if type_key and number_key and type_key in normalized_text and number_key in normalized_text:
                norm_id = candidate_id
                break
        rows.append({
            "text": row["text"],
            "page": row["page"],
            "level": row["level"],
            "role": row["role"],
            "norm_id": norm_id,
        })

    return rows


def scan_gazette_index(pdf_path):
    """Escanear PDF do Diário Oficial para identificar as normas e suas faixas de páginas."""
    import pdfplumber
    
    norms = []
    total_pages = 0
    seen_norms = set()
    index_text_parts = []
    body_pages = {}
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for page_idx, page in enumerate(pdf.pages):
            page_num = page_idx + 1
            
            # Usar extração com layout/colunas
            text = extract_text_with_layout_and_columns(page) or ""
            
            # Se for página de índice, capturar seu texto
            if is_index_page(text):
                index_text_parts.append(text)
                continue

            body_pages[page_num] = text
                
            for match in GAZETTE_NORM_RE.finditer(text):
                tipo = match.group(1).strip().upper()
                numero = match.group(2).strip()
                
                # De-duplicar normas idênticas detectadas no mesmo diário
                norm_key = (tipo, numero)
                if norm_key in seen_norms:
                    continue
                seen_norms.add(norm_key)

                # Ignorar citações: "LEI X Nº Y, que dispõe..." no meio de outra norma
                # é uma referência cruzada, não uma publicação nesta edição.
                _rest_preview = text[match.end():match.end() + 80].strip()
                if re.match(r'^,\s*que\b', _rest_preview, re.IGNORECASE):
                    seen_norms.discard(norm_key)
                    continue

                # Extrair ementa
                start_pos = match.end()
                rest_of_text = text[start_pos:].strip()

                # Remover linhas de pontos (líderes de sumário residuais) antes de montar a ementa
                rest_of_text = re.sub(r"\.{3,}[\s\d]*", " ", rest_of_text)
                # Limpar quebras de linha e espaços múltiplos
                rest_of_text = re.sub(r'\s+', ' ', rest_of_text).strip()

                # Remover data introdutória residual: ", DE 11 DE JUNHO DE 2026" ou ". DE 30 DE MARÇO..."
                rest_of_text = re.sub(
                    r'^[,.]?\s*DE\s+\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4}[\s.]*',
                    '', rest_of_text, flags=re.IGNORECASE
                ).strip()

                # Remover ocorrência duplicada do próprio título da norma no início da ementa
                dup_title_pattern = re.compile(
                    r'^' + r'\s+'.join(re.escape(w) for w in tipo.split())
                    + r'\s+(?:Nº|N[°ºo]\.?)\s*' + re.escape(numero)
                    + r'[,.]?\s*(?:DE\s+\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4}[\s.]*)?',
                    re.IGNORECASE
                )
                rest_of_text = dup_title_pattern.sub('', rest_of_text).strip()

                # Tentar pegar as primeiras ~200 letras como ementa
                ementa = rest_of_text[:200]
                if len(rest_of_text) > 200:
                    # Cortar na última palavra completa
                    last_space = ementa.rfind(' ')
                    if last_space > 100:
                        ementa = ementa[:last_space]
                    ementa += "..."
                    
                norms.append({
                    "id": len(norms),
                    "tipo": tipo,
                    "numero": numero,
                    "ementa": ementa,
                    "start_page": page_num,
                    "end_page": page_num,
                    "_body_order": (page_num, match.start()),
                })

    index_text = "\n".join(index_text_parts)
    preliminary_entries = parse_gazette_index_rows(index_text, norms)
    _add_index_document_candidates(preliminary_entries, norms, body_pages)
    norms.sort(key=lambda norm: norm.get("_body_order", (norm["start_page"], 0)))
    for norm_id, norm in enumerate(norms):
        norm["id"] = norm_id

    # Ajustar a página de fim para cada norma detectada
    for i in range(len(norms)):
        if i < len(norms) - 1:
            norms[i]["end_page"] = norms[i+1]["start_page"]
        else:
            norms[i]["end_page"] = total_pages
        norms[i].pop("_body_order", None)
            
    index_entries = parse_gazette_index_rows(index_text, norms)
    _apply_linked_gazette_page_ranges(norms, index_entries, total_pages)

    return {
        "total_pages": total_pages,
        "norms": norms,
        "index_text": index_text,
        "index_entries": index_entries,
    }


def cleanup_gazette_cache():
    """Remover PDFs em cache com mais de 30 minutos."""
    if not os.path.isdir(GAZETTE_CACHE_DIR):
        return
    now = datetime.now(timezone.utc)
    for fname in os.listdir(GAZETTE_CACHE_DIR):
        if not fname.endswith(".json"):
            continue
        meta_path = os.path.join(GAZETTE_CACHE_DIR, fname)
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            created_at = datetime.fromisoformat(meta["created_at"])
            if (now - created_at).total_seconds() > 1800:
                pdf_path = os.path.join(GAZETTE_CACHE_DIR, fname[:-5] + ".pdf")
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
                os.remove(meta_path)
        except Exception as e:
            print(f"Erro ao limpar cache de diário: {e}")


def get_norm_title_pattern(tipo, numero, title=None):
    """Gerar regex para localizar o cabeçalho de uma norma."""
    if title and not numero:
        words = re.findall(r"[\wÀ-ÿ]+", title, re.UNICODE)
        return r"(?:#+\s*|\*\*|^\s*)?" + r"[\W_]+".join(re.escape(word) for word in words)
    escaped_num = re.escape(numero)
    tipo_pattern = r"\s+".join(re.escape(word) for word in tipo.split())
    return r"(?:#+\s*|\*\*|^\s*)?" + tipo_pattern + r"\s+(?:Nº|N[°ºo]\.?)\s*" + escaped_num


def slice_norm_markdown(markdown, norm_title_pattern, next_norm_title_pattern=None):
    """Fatiar o Markdown para isolar apenas o texto da norma desejada. Retorna None se o título não for localizado."""
    match_start = re.search(norm_title_pattern, markdown, re.IGNORECASE | re.MULTILINE)
    if not match_start:
        return None
        
    start_pos = match_start.start()
    
    search_tail = markdown[match_start.end():]
    next_norm_pos = None
    if next_norm_title_pattern:
        match_end = re.search(next_norm_title_pattern, search_tail, re.IGNORECASE | re.MULTILINE)
        if match_end:
            next_norm_pos = match_start.end() + match_end.start()

    # Códigos de uma publicação anterior podem aparecer depois do título atual
    # em páginas com transição de colunas. Use o último código antes da próxima norma.
    code_search_end = next_norm_pos if next_norm_pos is not None else len(markdown)
    code_matches = list(re.finditer(
        r'(?:C[óo]d\.?\s*Identificador|C[óo]digo\s+[iI]dentificador)\s*:\s*([A-Za-z0-9$]+)',
        markdown[match_start.end():code_search_end],
        re.IGNORECASE
    ))
    
    end_pos = None
    if code_matches:
        end_pos = match_start.end() + code_matches[-1].end()
        
    if next_norm_pos is not None and (end_pos is None or next_norm_pos < end_pos):
        end_pos = next_norm_pos
                
    if end_pos is not None:
        return markdown[start_pos:end_pos].strip()
        
    return markdown[start_pos:].strip()



def allowed_file(filename):
    """Validar arquivo por extensão antes da tentativa de conversão."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def compact_markdown(content):
    """Produzir uma saída mais enxuta sem alterar a ordem do conteúdo."""
    lines = [line.rstrip() for line in content.splitlines()]
    compacted = []
    previous_blank = False

    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and previous_blank:
            continue
        compacted.append(line)
        previous_blank = is_blank

    return "\n".join(compacted).strip()


def normalize_abnt_markdown(content):
    """Normalizar Markdown para uma apresentação textual inspirada na ABNT."""
    normalized = compact_markdown(content)
    counters = [0, 0, 0, 0, 0, 0]
    output = []
    in_code_block = False

    legal_heading_patterns = [
        (1, re.compile(r"^LIVRO\s+(?:[IVXLCDM]+|COMPLEMENTAR)\b", re.I)),
        (2, re.compile(r"^T[ÍI]TULO\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
        (3, re.compile(r"^CAP[ÍI]TULO\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
        (4, re.compile(r"^Se[çc][ãa]o\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    ]

    def append_numbered_heading(level, title):
        counters[level - 1] += 1
        for idx in range(level, len(counters)):
            counters[idx] = 0
        number = ".".join(str(item) for item in counters[:level] if item)
        output.append(f"{'#' * level} {number} {title.upper()}")

    for raw_line in normalized.splitlines():
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            output.append(line)
            continue

        if in_code_block:
            output.append(line)
            continue

        stripped = line.strip()
        legal_level = None
        for level, pattern in legal_heading_patterns:
            if pattern.match(stripped):
                legal_level = level
                break

        if legal_level is not None:
            append_numbered_heading(legal_level, stripped)
            continue

        if stripped.startswith("#"):
            marker = stripped.split(" ", 1)[0]
            if set(marker) == {"#"} and 1 <= len(marker) <= 6 and " " in stripped:
                level = len(marker)
                title = stripped[level:].strip()
                if title:
                    title = _strip_generated_heading_number(title)
                    append_numbered_heading(level, title)
                    continue

        output.append(line)

    return "\n".join(output).strip()


LEGAL_HEADING_PATTERNS = [
    (1, re.compile(r"^LIVRO\s+(?:[IVXLCDM]+|COMPLEMENTAR|PRIMEIRO|SEGUNDO|TERCEIRO|QUARTO|[ÚU]NICO)\b", re.I)),
    (2, re.compile(r"^(?:DAS\s+)?DISPOSI[ÇC](?:[ÃA]O|[ÕO]ES)\s+(?:PRELIMINAR(?:ES)?|GERA(?:IS|L)|FINA(?:IS|L)|TRANSIT[ÓO]RIA(?:S)?)(?:\s+E\s+(?:PRELIMINAR(?:ES)?|GERA(?:IS|L)|FINA(?:IS|L)|TRANSIT[ÓO]RIA(?:S)?))?(?:\s*[-–—:]\s*.*)?$", re.I)),
    (2, re.compile(r"^T[ÍI]TULO\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    (3, re.compile(r"^CAP[ÍI]TULO\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    (4, re.compile(r"^SE[ÇC][ÃA]O\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    (5, re.compile(r"^SUBSE[ÇC][ÃA]O\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
]

STRUCTURAL_LINE_PATTERNS = [
    re.compile(r"^#{1,6}\s+\S+"),
    re.compile(r"^Art\.?\s*\d+", re.I),
    re.compile(r"^Par[\u00e1a]grafo\s+[\u00fau]nico\b", re.I),
    re.compile(r"^§\s*\d+"),
    re.compile(r"^[IVXLCDM]+\s*[-–—]", re.I),
    re.compile(r"^[a-z](?:\)|\s*[-–—])\s+"),
    re.compile(r"^\|"),
    re.compile(r"^```"),
]

CITATION_PATTERN = re.compile(
    r'^\s*(?:[aA]rts?\.?|\u00a7\u00a7?)\s*\d+(?:\.[\u00ba\u00b0\u00aa\u015f]|[\u00ba\u00b0\u00aa\u015foa])?\.?\s*(?:,\s*|da\b|do\b|de\b|e\b|[iI]nciso\b|[aA]l[\u00edi]nea\b|\s*da\s+[cC]onst|[dD]os\b|[dD]as\b|[sS][\u00f4o]bre\b|\bcaput\b|[dD]este\b|[dD]esta\b|[cC]ombinado\b|[cC]/[cC]\b|;|,|\s*$)'
)

VALID_ROMANS = {
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII", "XXVIII", "XXIX", "XXX",
    "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV", "XXXVI", "XXXVII", "XXXVIII", "XXXIX", "XL",
    "XLI", "XLII", "XLIII", "XLIV", "XLV", "XLVI", "XLVII", "XLVIII", "XLIX", "L",
    "LI", "LII", "LIII", "LIV", "LV", "LVI", "LVII", "LVIII", "LIX", "LX",
    "LXI", "LXII", "LXIII", "LXIV", "LXV", "LXVI", "LXVII", "LXVIII", "LXIX", "LXX",
    "LXXI", "LXXII", "LXXIII", "LXXIV", "LXXV", "LXXVI", "LXXVII", "LXXVIII", "LXXIX", "LXXX",
    "LXXXI", "LXXXII", "LXXXIII", "LXXXIV", "LXXXV", "LXXXVI", "LXXXVII", "LXXXVIII", "LXXXIX", "XC",
    "XCI", "XCII", "XCIII", "XCIV", "XCV", "XCVI", "XCVII", "XCVIII", "XCIX", "C",
    "M"
}


def split_inline_legal_elements(text):
    """Detectar e separar em novas linhas elementos estruturais grudados in-line por notas legislativas."""
    boundary = r'(?:[).;:]|Produ[\u00e7c][\u00e3a]o\s+de\s+efeitos|Vig[\u00eae]ncia|Vide\b)'
    
    # Split Art.
    text = re.sub(
        rf'({boundary}\s*)([*_]*Art\.\s*\d+)',
        r'\1\n\n\2',
        text,
        flags=re.IGNORECASE
    )
    
    # Split Parágrafo único
    text = re.sub(
        rf'({boundary}\s*)([*_]*Par[\u00e1a]grafo\s+[\u00fau]nico)',
        r'\1\n\n\2',
        text,
        flags=re.IGNORECASE
    )
    
    # Split §
    text = re.sub(
        rf'({boundary}\s*)([*_]*\u00a7\s*\d+)',
        r'\1\n\n\2',
        text
    )
    
    # Split Roman Numerals (ex: I, II, III...)
    roman_num = r'\b(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII|XIX|XX)\b'
    text = re.sub(
        rf'({boundary}\s*)({roman_num}(?:\s*[-–—])?\s+)',
        r'\1\n\n\2',
        text
    )
    
    # Split lettered items (ex: a), b), c))
    text = re.sub(
        rf'({boundary}\s*)([a-z]\)\s*)',
        r'\1\n\n\2',
        text,
        flags=re.IGNORECASE
    )
    
    return text


def _normalize_text_line(line):
    """Normalizar espaços sem remover conteúdo relevante."""
    line = line.replace("\u00a0", " ")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def _strip_generated_heading_number(text):
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", text).strip()


def _heading_from_line(line):
    stripped = _normalize_text_line(line)
    if not stripped:
        return None

    # Strip markdown bold and italic formatting wrappers
    clean_stripped = re.sub(r"[\*_]+", "", stripped).strip()

    if clean_stripped.startswith("#"):
        marker, _, title = clean_stripped.partition(" ")
        if set(marker) == {"#"} and 1 <= len(marker) <= 6 and title.strip():
            title = _strip_generated_heading_number(title.strip())
            return len(marker), title

    for level, pattern in LEGAL_HEADING_PATTERNS:
        if pattern.match(clean_stripped):
            return level, clean_stripped.upper()

    return None


def _is_all_caps_descriptor(line):
    text = _normalize_text_line(line)
    if len(text) < 2 or _heading_from_line(text):
        return False
    if any(pattern.match(text) for pattern in STRUCTURAL_LINE_PATTERNS[1:]):
        return False

    if re.fullmatch(r"[A-ZÀ-Ý0-9][A-ZÀ-Ý0-9/\-–— ]{1,24}", text):
        return True

    letters = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text)
    if not letters:
        return False
    uppercase = sum(1 for char in letters if char.upper() == char)
    return uppercase / len(letters) >= 0.75


def _is_titlecase_descriptor(line):
    text = _normalize_text_line(line)
    if len(text) < 4 or _heading_from_line(text):
        return False
    if any(pattern.match(text) for pattern in STRUCTURAL_LINE_PATTERNS[1:]):
        return False
    if re.search(r"[.;:]$", text):
        return False

    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", text)
    # Títulos/descritores podem ser longos se listarem várias opções (máximo 60 palavras)
    if not 1 <= len(words) <= 60:
        return False

    meaningful = [word for word in words if len(word) > 2]
    if not meaningful:
        return False

    starters = sum(1 for word in meaningful if word[0].upper() == word[0])
    return starters / len(meaningful) >= 0.55


def _is_sentencecase_descriptor(line):
    text = _normalize_text_line(line)
    if len(text) < 4 or _heading_from_line(text):
        return False
    if any(pattern.match(text) for pattern in STRUCTURAL_LINE_PATTERNS[1:]):
        return False
    if re.search(r"[.;:]$", text):
        return False

    # Deve começar com uma letra maiúscula (incluindo acentos portugueses)
    if not re.match(r"^[A-ZÀ-ÚÇ]", text):
        return False

    words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", text)
    # Títulos/descritores podem ser longos se listarem várias opções (máximo 60 palavras)
    if not 1 <= len(words) <= 60:
        return False

    return True


def _is_heading_descriptor(line):
    return (
        _is_all_caps_descriptor(line)
        or _is_titlecase_descriptor(line)
        or _is_sentencecase_descriptor(line)
    )


def _starts_structural_block(line):
    text = _normalize_text_line(line)
    if _heading_from_line(text):
        return True
        
    clean_text = re.sub(r"^[\*_~]+", "", text).strip()
    
    if CITATION_PATTERN.match(clean_text):
        return False
    if any(pattern.match(clean_text) for pattern in STRUCTURAL_LINE_PATTERNS[1:]):
        return True
        
    roman_match = re.match(r"^([IVXLCDM]+)\b\s*(?:[-–—]\s*)?(?![.,;:?!\)])", clean_text, flags=re.I)
    if roman_match and roman_match.group(1).upper() in VALID_ROMANS:
        return True
        
    return False


def _strip_markdown_wrappers(text):
    leading = ""
    trailing = ""
    for wrapper in ["~~", "**", "*", "_"]:
        if text.startswith(wrapper) and text.endswith(wrapper) and len(text) >= 2 * len(wrapper):
            leading += wrapper
            trailing = wrapper + trailing
            text = text[len(wrapper):-len(wrapper)]
    return leading, text, trailing


def _format_article_start(text):
    leading, inner, trailing = _strip_markdown_wrappers(text)
    # Regex to match article number and suffix precisely without swallowing letters like 'O' and 'A'
    # Handles optional opening and closing bold/italic markdown wrappers
    article_pattern = re.compile(
        r"^(?:\*\*|\*|)?[Aa]rt\.?\s*(\d+(?:-[A-Z])?)(?:\.?(?:[\u00ba\u00b0\u00aa\u015f]|[oa]\b))?\.?(?:\*\*|\*|)?\s*(.*)$"
    )
    match = article_pattern.match(inner)
    if not match:
        # Check and format Parágrafo único
        if re.match(r"^(?:\*\*|\*|)?Par[\u00e1a]grafo\s+[\u00fau]nico\.?(?:\*\*|\*|)?\s*(.*)$", inner, re.I):
            rest = re.sub(r"^(?:\*\*|\*|)?Par[\u00e1a]grafo\s+[\u00fau]nico\.?(?:\*\*|\*|)?\s*", "", inner, flags=re.I).strip()
            formatted_inner = f"**Parágrafo único.** {rest}".strip()
            return f"{leading}{formatted_inner}{trailing}"
        return text

    num_str = match.group(1)
    rest = match.group(2).strip()
    try:
        num = int(num_str.split('-')[0])
    except ValueError:
        num = 10
        
    if num < 10:
        prefix = f"**Art. {num_str}º**"
    else:
        prefix = f"**Art. {num_str}.**"
        
    formatted_inner = f"{prefix} {rest}".strip()
    return f"{leading}{formatted_inner}{trailing}"


def _format_paragraph_start(text):
    leading, inner, trailing = _strip_markdown_wrappers(text)
    paragraph_pattern = re.compile(
        r"^(?:\*\*|\*|)?\u00a7\s*(\d+)(?:\.?(?:[\u00ba\u00b0\u00aa\u015f]|[oa]\b))?\.?(?:\*\*|\*|)?\s*(.*)$"
    )
    match = paragraph_pattern.match(inner)
    if not match:
        return text

    num_str = match.group(1)
    rest = match.group(2).strip()
    prefix = f"**§ {num_str}º**"
    formatted_inner = f"{prefix} {rest}".strip()
    return f"{leading}{formatted_inner}{trailing}"


def _format_alinea_start(text):
    leading, inner, trailing = _strip_markdown_wrappers(text)
    alinea_pattern = re.compile(r"^([a-z])(?:\)|\s*[-–—])\s+(.*)$")
    match = alinea_pattern.match(inner)
    if not match:
        return text

    letter = match.group(1).lower()
    rest = match.group(2).strip()
    if not rest:
        return text

    formatted_inner = f"{letter}) {rest}".strip()
    return f"{leading}{formatted_inner}{trailing}"


def _capitalize_first_letter(text):
    if not text:
        return text
    # Match any leading non-alphabetic formatting characters (like *, _, ~, space)
    match = re.match(r"^([^a-zA-Z\u00C0-\u00FF]*)([a-zA-Z\u00C0-\u00FF])(.*)$", text)
    if match:
        prefix, char, rest = match.groups()
        return prefix + char.upper() + rest
    return text


def _format_inciso_start(text):
    leading, inner, trailing = _strip_markdown_wrappers(text)
    inciso_pattern = re.compile(
        r"^(?:\*\*|\*|)?([IVXLCDM]+)(?:\*\*|\*|)?\b\s*(?:[-–—]\s*)?(?![.,;:?!\)])(.*)$", re.I
    )
    match = inciso_pattern.match(inner)
    if not match:
        return text

    roman_num = match.group(1).upper()
    if roman_num not in VALID_ROMANS:
        return text

    rest = match.group(2).strip()
    if not rest:
        return text
        
    rest = _capitalize_first_letter(rest)
    formatted_inner = f"{roman_num} - {rest}".strip()
    return f"{leading}{formatted_inner}{trailing}"


def _roman_for_index(index):
    romans = [
        "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
        "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX",
    ]
    if 1 <= index <= len(romans):
        return romans[index - 1]
    return None


def _restore_orphan_legal_items(text):
    """Recriar incisos quando a extração do PDF removeu os algarismos romanos."""
    leading, inner, trailing = _strip_markdown_wrappers(text)
    if ":" not in inner:
        return text
    if re.search(r"(?m)^\s*(?:[IVXLCDM]+\s*[-–—]|[a-z]\))\s+", inner, flags=re.I):
        return text

    prefix, _, tail = inner.partition(":")
    clean_tail = tail.strip()
    clean_tail_no_wrappers = re.sub(r"[\*_~]+$", "", clean_tail).strip()
    if clean_tail_no_wrappers.count(";") < 2:
        return text

    if not re.match(r"^(?:\*\*)?(?:Art\.|§|Par[\u00e1a]grafo)", prefix.strip(), flags=re.I):
        return text

    parts = [part.strip() for part in re.split(r";\s*", clean_tail_no_wrappers) if part.strip()]
    if len(parts) < 3:
        return text

    restored = []
    for idx, part in enumerate(parts, start=1):
        roman = _roman_for_index(idx)
        if not roman:
            return text
        terminal = "." if idx == len(parts) else ";"
        item = part.rstrip(" .;")
        if not item or _starts_structural_block(item):
            return text
            
        item = _capitalize_first_letter(item)
        
        if leading and trailing:
            restored.append(f"{leading}{roman} - {item}{terminal}{trailing}")
        else:
            restored.append(f"{roman} - {item}{terminal}")

    if leading and trailing:
        return f"{leading}{prefix.strip()}:{trailing}\n\n" + "\n\n".join(restored)
    return f"{prefix.strip()}:{tail.partition(':')[1]}\n\n" + "\n\n".join(restored)


def _join_wrapped_lines(lines):
    result = []
    pronouns = {"se", "lo", "la", "nos", "vos", "lhes", "o", "a", "os", "as", "me", "te"}
    for line in lines:
        cleaned = _normalize_text_line(line)
        if not cleaned:
            continue
        if result and result[-1].endswith("-"):
            next_word = cleaned.split()[0] if cleaned.split() else ""
            clean_next_word = re.sub(r"[^\w]", "", next_word).lower()
            if (next_word and next_word[0].islower() and 
                clean_next_word not in pronouns and 
                not clean_next_word.startswith("de") and 
                not clean_next_word.startswith("lei")):
                result[-1] = result[-1][:-1] + cleaned
            else:
                result[-1] = result[-1] + cleaned
        else:
            if result:
                result.append(" " + cleaned)
            else:
                result.append(cleaned)
    paragraph = "".join(result)
    paragraph = re.sub(r"\s+([,.;:!?])", r"\1", paragraph)
    return paragraph.strip()


def _split_official_clauses(text):
    """Separar blocos formais que a extração costuma colar no mesmo parágrafo."""
    text = re.sub(
        r"(\bd[aá]\s+outras\s+provid[êe]ncias\.)\s+(FRANCISCO\s+DE\s+ASSIS)",
        r"\1\n\n\2",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(\bRevogam-se\s+as\s+disposi[çc][õo]es\s+em\s+contr[aá]rio\.)\s+(GABINETE\s+DO\s+PREFEITO)",
        r"\1\n\n\2",
        text,
        flags=re.I,
    )
    return text


def _is_continuation_candidate(previous, current):
    previous = _normalize_text_line(previous)
    current = _normalize_text_line(current)
    if not previous or not current:
        return False
    if previous.startswith("#") or current.startswith("#"):
        return False
    if re.match(r"^(?:REGULAMENTO|DECRETO|LEI\s+COMPLEMENTAR)\b", current, flags=re.I):
        return False
        
    # Limpar marcações de formatação em negrito/itálico/tachado para inspecionar o prefixo limpo
    clean_current = re.sub(r"^[\*_~]+|[\*_~]+$", "", current).strip()
    
    # Proibir mesclagem se a linha seguinte começar com termos ou símbolos estruturais de leis
    if re.match(r"^(?:Art\.?\s*\d+|Par[\u00e1a]grafo\s+[\u00fau]nico|\u00a7\s*\d+)(?:\s|$|\b)", clean_current, flags=re.I):
        if not CITATION_PATTERN.match(clean_current):
            return False
    if re.match(r"^[IVXLCDM]+\b", clean_current, flags=re.I):
        return False
    if re.match(r"^[a-z]\)", clean_current, flags=re.I):
        return False
    if re.match(r"^[-*+•]", clean_current):
        return False

    # Se a linha atual começa com letra minúscula (e não foi vetada pelas regras anteriores como alíneas),
    # ela é uma continuação da linha anterior, mesmo que a anterior termine com pontuação terminal (como ';').
    if clean_current and clean_current[0].islower():
        return True

    # Limpar wrappers de formatação do final da linha anterior antes de checar pontuação terminal
    clean_previous = re.sub(r"[\*_~]+$", "", previous).strip()
    previous_has_terminal = bool(re.search(r"[.!?:;)]$", clean_previous))
    if not previous_has_terminal:
        return True

    return False


def _merge_spurious_continuation_breaks(content):
    lines = content.splitlines()
    output = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.strip() or index == len(lines) - 1:
            output.append(line)
            index += 1
            continue

        previous = output[-1] if output else ""
        next_index = index + 1
        while next_index < len(lines) and not lines[next_index].strip():
            next_index += 1

        next_line = lines[next_index] if next_index < len(lines) else ""
        if _is_continuation_candidate(previous, next_line):
            prev_clean = previous.rstrip()
            next_clean = _normalize_text_line(next_line)
            if prev_clean.endswith("-"):
                next_word = next_clean.split()[0] if next_clean.split() else ""
                clean_next_word = re.sub(r"[^\w]", "", next_word).lower()
                pronouns = {"se", "lo", "la", "nos", "vos", "lhes", "o", "a", "os", "as", "me", "te"}
                if (next_word and next_word[0].islower() and 
                    clean_next_word not in pronouns and 
                    not clean_next_word.startswith("de") and 
                    not clean_next_word.startswith("lei")):
                    output[-1] = f"{prev_clean[:-1]}{next_clean}"
                else:
                    output[-1] = f"{prev_clean}{next_clean}"
            else:
                output[-1] = f"{prev_clean} {next_clean}"
            index = next_index + 1
            continue

        output.append(line)
        index += 1

    return "\n".join(output)


def _repair_known_pdf_text_dislocations(content):
    """Corrigir deslocamentos recorrentes em conversões do decreto/regulamento."""
    return re.sub(
        (
            r"segundo\s+a\s+capacidade\s+econ[ôo]mica\s+do\s+Tribut[aá]ria,\s+"
            r"(especialmente\s+para\s+conferir\s+efetividade\s+a\s+esses\s+objetivos,\s+"
            r"identificar,\s+nos\s+termos\s+da\s+lei\s+e\s+respeitados\s+os\s+direitos\s+"
            r"individuais,\s+o\s+patrim[ôo]nio,\s+os\s+rendimentos\s+e\s+as\s+atividades\s+"
            r"econ[ôo]micas\s+do\s+contribuinte\.)\s+contribuinte,\s+Administra[çc][aã]o\s+"
            r"facultado\s+[àa]"
        ),
        (
            "segundo a capacidade econômica do contribuinte, facultado à Administração "
            r"Tributária, \1"
        ),
        content,
        flags=re.I | re.S,
    )


def remove_prefix_paragraph_duplicates(blocks):
    """Remove parágrafos consecutivos ou próximos que são prefixos de parágrafos mais completos (glitch comum de PDFs)."""
    cleaned = []
    for i in range(len(blocks)):
        current = blocks[i].strip()
        if not current:
            cleaned.append(blocks[i])
            continue
        is_prefix = False
        curr_clean = re.sub(r'[\*_#\s]+', '', current).lower()
        for j in range(i + 1, min(len(blocks), i + 3)):
            nxt = blocks[j].strip()
            if nxt:
                nxt_clean = re.sub(r'[\*_#\s]+', '', nxt).lower()
                if nxt_clean.startswith(curr_clean) and len(nxt_clean) > len(curr_clean):
                    is_prefix = True
                    break
        if not is_prefix:
            cleaned.append(blocks[i])
    return cleaned


def polish_legal_markdown_model2(content):
    """Polimento final para manter documentos legais no padrão modelo 2."""
    content = split_inline_legal_elements(content)
    lines = compact_markdown(content).splitlines()
    output = []
    index = 0
    in_code_block = False

    def append_blank():
        if output and output[-1] != "":
            output.append("")

    while index < len(lines):
        raw_line = lines[index].rstrip()
        line = _normalize_text_line(raw_line)

        if not line:
            append_blank()
            index += 1
            continue

        if line.startswith("```"):
            in_code_block = not in_code_block
            output.append(raw_line)
            index += 1
            continue

        if in_code_block:
            output.append(raw_line)
            index += 1
            continue

        heading = _heading_from_line(line)
        if heading:
            level, title = heading
            descriptor_parts = []
            next_index = index + 1
            while next_index < len(lines) and not _normalize_text_line(lines[next_index]):
                next_index += 1

            temp_idx = next_index
            while temp_idx < len(lines):
                line_text = _normalize_text_line(lines[temp_idx])
                if not line_text:
                    break
                if _starts_structural_block(line_text):
                    break
                if re.search(r"[.;:]$", line_text):
                    break
                descriptor_parts.append(line_text)
                temp_idx += 1

            if descriptor_parts:
                candidate_descriptor = " ".join(descriptor_parts)
                candidate_descriptor = re.sub(r"\s+", " ", candidate_descriptor).strip()
                clean_candidate = re.sub(r"^\*+|\*+$", "", candidate_descriptor).strip()
                if _is_heading_descriptor(candidate_descriptor) and f" - {clean_candidate}" not in title:
                    title = f"{title} - {clean_candidate}"
                    index = temp_idx - 1

            append_blank()
            output.append(f"{'#' * level} {title}")
            append_blank()
            index += 1
            continue

        if not CITATION_PATTERN.match(line):
            line = _format_article_start(line)
            line = _format_paragraph_start(line)
            line = _format_inciso_start(line)
            line = _format_alinea_start(line)
        line = re.sub(r"\s+([:;,.!?])", r"\1", line)
        line = _restore_orphan_legal_items(line)
        line = _split_official_clauses(line)
        output.append(line)
        index += 1

    polished = compact_markdown("\n".join(output))
    polished = _merge_spurious_continuation_breaks(polished)
    polished = _repair_known_pdf_text_dislocations(polished)
    
    # Deduplicate prefix paragraphs
    paragraphs = polished.split("\n\n")
    dedupped = remove_prefix_paragraph_duplicates(paragraphs)
    return "\n\n".join(dedupped).strip()


def format_pdf_markdown_model2(content):
    """Formatar PDFs legais no padrão visual do modelo 2."""
    content = split_inline_legal_elements(content)
    normalized = compact_markdown(content)
    source_lines = normalized.splitlines()
    output = []
    index = 0
    in_code_block = False

    def append_block(block):
        block = block.strip()
        if block:
            output.append(block)

    while index < len(source_lines):
        line = _normalize_text_line(source_lines[index])
        if not line:
            index += 1
            continue

        if line.startswith("```"):
            code_lines = [line]
            index += 1
            in_code_block = not in_code_block
            while index < len(source_lines) and in_code_block:
                code_line = source_lines[index].rstrip()
                code_lines.append(code_line)
                if _normalize_text_line(code_line).startswith("```"):
                    in_code_block = False
                index += 1
            append_block("\n".join(code_lines))
            continue

        heading = _heading_from_line(line)
        if heading:
            level, title = heading
            descriptor_parts = []
            next_index = index + 1
            while next_index < len(source_lines) and not _normalize_text_line(source_lines[next_index]):
                next_index += 1

            temp_idx = next_index
            while temp_idx < len(source_lines):
                line_text = _normalize_text_line(source_lines[temp_idx])
                if not line_text:
                    break
                if _starts_structural_block(line_text):
                    break
                if re.search(r"[.;:]$", line_text):
                    break
                descriptor_parts.append(line_text)
                temp_idx += 1

            if descriptor_parts:
                candidate_descriptor = " ".join(descriptor_parts)
                candidate_descriptor = re.sub(r"\s+", " ", candidate_descriptor).strip()
                if _is_heading_descriptor(candidate_descriptor):
                    title = f"{title} - {candidate_descriptor}"
                    index = temp_idx - 1

            append_block(f"{'#' * level} {title}")
            index += 1
            continue

        clean_line = re.sub(r"^[\*_~]+|[\*_~]+$", "", line).strip()
        is_art_or_par = (re.match(r"^Art\.?\s*\d+", clean_line, flags=re.I) or re.match(r"^§\s*\d+", clean_line))
        if is_art_or_par and not CITATION_PATTERN.match(clean_line):
            paragraph_lines = [line]
            index += 1
            while index < len(source_lines):
                next_line = _normalize_text_line(source_lines[index])
                if not next_line:
                    index += 1
                    break
                if _starts_structural_block(next_line):
                    break
                paragraph_lines.append(next_line)
                index += 1

            paragraph = _join_wrapped_lines(paragraph_lines)
            paragraph = _format_article_start(paragraph)
            paragraph = _format_paragraph_start(paragraph)
            paragraph = _restore_orphan_legal_items(paragraph)
            append_block(paragraph)
            continue

        is_inciso = False
        roman_match = re.match(r"^([IVXLCDM]+)\b\s*(?:[-–—]\s*)?(?![.,;:?!\)])", clean_line, flags=re.I)
        if roman_match and roman_match.group(1).upper() in VALID_ROMANS:
            is_inciso = True
            
        if is_inciso:
            item_lines = [line]
            index += 1
            while index < len(source_lines):
                next_line = _normalize_text_line(source_lines[index])
                if not next_line:
                    index += 1
                    break
                if _starts_structural_block(next_line):
                    break
                item_lines.append(next_line)
                index += 1
            item_text = _join_wrapped_lines(item_lines)
            item_text = _format_inciso_start(item_text)
            append_block(item_text)
            continue

        is_alinea = re.match(r"^[a-z](?:\)|\s*[-–—])\s+", clean_line)
        if is_alinea:
            item_lines = [line]
            index += 1
            while index < len(source_lines):
                next_line = _normalize_text_line(source_lines[index])
                if not next_line:
                    index += 1
                    break
                if _starts_structural_block(next_line):
                    break
                item_lines.append(next_line)
                index += 1
            item_text = _join_wrapped_lines(item_lines)
            item_text = _format_alinea_start(item_text)
            append_block(item_text)
            continue

        paragraph_lines = [line]
        index += 1
        while index < len(source_lines):
            next_line = _normalize_text_line(source_lines[index])
            if not next_line:
                index += 1
                break
            if _starts_structural_block(next_line):
                break
            paragraph_lines.append(next_line)
            index += 1
        paragraph = _join_wrapped_lines(paragraph_lines)
        paragraph = _restore_orphan_legal_items(paragraph)
        append_block(paragraph)

    # Deduplicate prefix paragraphs
    output = remove_prefix_paragraph_duplicates(output)
    return polish_legal_markdown_model2("\n\n".join(output).strip())


def _header_footer_key(line):
    """Chave normalizada para comparar cabeçalhos/rodapés repetidos."""
    text = re.sub(r"\s+", " ", line).strip()
    text = re.sub(r"\b\d{1,4}\s*/\s*\d{1,4}\b", "", text)
    text = re.sub(r"\b(?:p[aá]g(?:ina)?|page)\s+\d+(?:\s+(?:de|of)\s+\d+)?\b", "", text, flags=re.I)

    return text.strip(" -–—|•\t").lower()


def _is_page_number_line(line):
    stripped = line.strip()
    return bool(
        re.fullmatch(r"\d{1,4}", stripped)
        or re.fullmatch(r"\d{1,4}\s*/\s*\d{1,4}", stripped)
        or re.fullmatch(r"(?:p[aá]g(?:ina)?|page)\s+\d+(?:\s+(?:de|of)\s+\d+)?", stripped, flags=re.I)
    )


def _remove_known_pdf_margin_noise(line):
    """Remover marcas institucionais que aparecem como cabeçalho no PDF."""
    known_noise_patterns = [
        r"\bDivis[aã]o\s+de\s+Arrecada[cç][aã]o,\s*Auditoria\s+e\s+Fiscaliza[cç][aã]o\s*-\s*DIAAF\b",
        r"^\s*DIAAF\s*$",
    ]

    cleaned = line
    for pattern in known_noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.I)

    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip(" -–—|•\t")


def _is_repeated_margin_noise(line):
    stripped = line.strip()
    key = _header_footer_key(stripped)
    if not key or len(key) < 8:
        return False

    structural = (
        "livro", "título", "titulo", "capítulo", "capitulo", "seção", "secao",
        "art.", "§", "inciso", "anexo",
    )
    if key.startswith(structural):
        return False

    margin_terms = (
        "divisão", "divisao", "secretaria", "prefeitura", "município",
        "municipio", "diário oficial", "diario oficial", "estado do",
        "auditoria", "fiscalização", "fiscalizacao",
    )
    return any(term in key for term in margin_terms)


def remove_duplicate_document_restart(content):
    """Remover segunda cópia quando a conversão concatena o documento inteiro."""
    patterns = [
        r"(?m)^DECRETO\s+N[ºO]\s*0?19\s+DE\s+30\s+DE\s+MAR[ÇC]O\s+DE\s+2023\.?$",
        r"(?m)^REGULAMENTO\s+DA\s+Lei\s+Complementar\s+n[ºo]\s+0?05\s+DE\s+30\s+DE\s+DEZEMBRO\s+DE\s+2022\.?$",
    ]

    for pattern in patterns:
        matches = list(re.finditer(pattern, content, flags=re.I))
        if len(matches) < 2:
            continue

        first_start = matches[0].start()
        second_start = matches[1].start()
        first_block = content[first_start:second_start].strip()
        second_block = content[second_start:].strip()
        if not first_block or not second_block:
            continue

        # A segunda cópia costuma ter tamanho semelhante e reiniciar a estrutura.
        size_ratio = min(len(first_block), len(second_block)) / max(len(first_block), len(second_block))
        if size_ratio >= 0.65:
            return content[:second_start].rstrip()

    return content


def remove_prefix_duplicates(lines):
    """Remove linhas consecutivas ou próximas que são prefixos de linhas mais completas (glitch comum de PDFs)."""
    cleaned = []
    for i in range(len(lines)):
        current = lines[i].strip()
        if not current:
            cleaned.append(lines[i])
            continue
        is_prefix = False
        # Verificar se alguma das próximas 3 linhas não-vazias começa com esta linha
        for j in range(i + 1, min(len(lines), i + 4)):
            nxt = lines[j].strip()
            if nxt:
                curr_clean = re.sub(r'\s+', '', current).lower()
                nxt_clean = re.sub(r'\s+', '', nxt).lower()
                if nxt_clean.startswith(curr_clean) and len(nxt_clean) > len(curr_clean):
                    is_prefix = True
                break
        if not is_prefix:
            cleaned.append(lines[i])
    return cleaned


def clean_pdf_headers_footers(content):
    """Remover cabeçalhos e rodapés repetidos da extração de PDFs."""
    content = remove_duplicate_document_restart(content)
    pages = [page for page in re.split(r"\f+", content) if page.strip()]

    if len(pages) < 2:
        lines = content.splitlines()
        frequency = {}
        for line in lines:
            key = _header_footer_key(line)
            if key:
                frequency[key] = frequency.get(key, 0) + 1

        cleaned = []
        for line in lines:
            original_line = line
            line = _remove_known_pdf_margin_noise(line)
            if original_line.strip() and not line.strip():
                continue

            key = _header_footer_key(line)
            repeated_noise = (
                frequency.get(key, 0) >= 5 and _is_repeated_margin_noise(line)
            )
            if _is_page_number_line(line) or repeated_noise:
                continue
            cleaned.append(line)

        cleaned = remove_prefix_duplicates(cleaned)
        return compact_markdown("\n".join(cleaned))

    zones_by_page = []
    frequency = {}

    for page in pages:
        lines = page.splitlines()
        non_empty_indexes = [idx for idx, line in enumerate(lines) if line.strip()]
        zone_indexes = set(non_empty_indexes[:3] + non_empty_indexes[-3:])
        page_keys = set()

        for idx in zone_indexes:
            key = _header_footer_key(lines[idx])
            if key and len(key) > 2:
                page_keys.add(key)

        for key in page_keys:
            frequency[key] = frequency.get(key, 0) + 1
        zones_by_page.append((lines, zone_indexes))

    threshold = max(2, (len(pages) + 1) // 2)
    repeated_keys = {key for key, count in frequency.items() if count >= threshold}

    cleaned_pages = []
    for lines, zone_indexes in zones_by_page:
        cleaned_lines = []
        for idx, line in enumerate(lines):
            original_line = line
            line = _remove_known_pdf_margin_noise(line)
            if original_line.strip() and not line.strip():
                continue

            key = _header_footer_key(line)
            is_repeated_margin = idx in zone_indexes and key in repeated_keys
            is_page_number_margin = idx in zone_indexes and _is_page_number_line(line)
            if is_repeated_margin or is_page_number_margin:
                continue
            cleaned_lines.append(line.rstrip())

        cleaned_lines = remove_prefix_duplicates(cleaned_lines)
        cleaned_pages.append("\n".join(cleaned_lines).strip())

    return compact_markdown("\n\n".join(page for page in cleaned_pages if page))


def clean_planalto_encoding_glitches(content):
    glitches = {
        '\u015f': '\u00ba', # ş -> º
        '\u015e': '\u00aa', # Ş -> ª
        '\u0119': '\u00ea', # ę -> ê
        '\u0118': '\u00ca', # Ę -> Ê
        '\u0103': '\u00e3', # ă -> ã
        '\u0102': '\u00c3', # Ă -> Ã
        '\u0155': '\u00e0', # ŕ -> à
        '\u0154': '\u00c0', # Ŕ -> À
        '\u0151': '\u00f5', # ő -> õ
        '\u0150': '\u00d5', # Ő -> Õ
    }
    for glitch, fixed in glitches.items():
        content = content.replace(glitch, fixed)
    return content


def _extract_html_charset(raw_bytes):
    match = re.search(
        br'<meta[^>]+charset=["\']?\s*([A-Za-z0-9._-]+)',
        raw_bytes[:4096],
        re.I,
    )
    if not match:
        return None
    try:
        return match.group(1).decode("ascii", errors="ignore").strip().lower()
    except Exception:
        return None


def _normalize_legacy_portuguese_encoding(encoding):
    if not encoding:
        return None
    normalized = encoding.strip().lower().replace("_", "-")
    if normalized in {"iso-8859-1", "latin-1", "latin1", "windows-1252"}:
        return "cp1252"
    return normalized


def decode_html_bytes(raw_bytes, default_encoding=None, prefer_cp1252=False):
    """Decode HTML while avoiding mojibake from guessing valid UTF-8 as Cyrillic."""
    try:
        return raw_bytes.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    candidates = []
    if prefer_cp1252:
        candidates.append("cp1252")

    candidates.extend([
        _normalize_legacy_portuguese_encoding(_extract_html_charset(raw_bytes)),
        _normalize_legacy_portuguese_encoding(default_encoding),
    ])

    try:
        import charset_normalizer
        detection = charset_normalizer.from_bytes(raw_bytes).best()
        candidates.append(_normalize_legacy_portuguese_encoding(detection.encoding if detection else None))
    except Exception:
        pass

    candidates.extend(["cp1252", "latin-1"])

    tried = set()
    for encoding in candidates:
        if not encoding or encoding in tried:
            continue
        tried.add(encoding)
        try:
            return raw_bytes.decode(encoding), encoding
        except Exception:
            continue

    return raw_bytes.decode("utf-8", errors="replace"), "utf-8"


def strip_relative_and_internal_links(content):
    def repl(match):
        text = match.group(1)
        url = match.group(2)
        if match.group(0).startswith('!'):
            return match.group(0)
        
        is_relative = not (url.startswith("http://") or url.startswith("https://") or url.startswith("mailto:"))
        is_internal = "planalto.gov.br" in url
        if is_relative or is_internal:
            return text
        return match.group(0)
    
    content = re.sub(r'(?<!\!)\[([^\]]+)\]\(([^)]+)\)', repl, content)
    return content


def split_planalto_document(content):
    lines = content.splitlines()
    header_lines = []
    body_lines = []

    if re.search(r"CONSTITUI[ÇC][ÃA]O\s+DA\s+REP[ÚU]BLICA", content, re.I):
        preamble_pattern = re.compile(r"^\s*(?:\*\*)?PRE[ÂA]MBULO(?:\*\*)?\s*$", re.I)
        for idx, line in enumerate(lines):
            if preamble_pattern.match(line):
                return "\n".join(lines[:idx]), "\n".join(lines[idx:])
    
    promulgation_pattern = re.compile(
        r'^\s*(?:\*\*|\*|)?(?:O\s+PRESIDENTE\s+DA\s+REP[ÚU]BLICA|O\s+CONGRESSO\s+NACIONAL|O\s+GOVERNADOR|O\s+PREFEITO|A\s+ASSEMBL[ÉE]IA\s+LEGISLATIVA|A\s+C[ÂA]MARA\s+MUNICIPAL)\b',
        re.I
    )
    
    promulgation_idx = -1
    for idx, line in enumerate(lines):
        lookahead_line = " ".join(lines[idx:idx + 3])
        clean_line = re.sub(r'^\s*(?:\*\*|\*)?', '', lookahead_line).lstrip()
        if clean_line[:1] in ("O", "A") and promulgation_pattern.match(lookahead_line):
            promulgation_idx = idx
            break
            
    if promulgation_idx != -1:
        header_lines = lines[:promulgation_idx]
        body_lines = lines[promulgation_idx:]
    else:
        if len(lines) > 3:
            header_lines = lines[:3]
            body_lines = lines[3:]
        else:
            header_lines = lines
            body_lines = []
            
    return "\n".join(header_lines), "\n".join(body_lines)


def generate_premium_header(header_text):
    # Clean encoding glitches first
    header_text = clean_planalto_encoding_glitches(header_text)
    header_text = header_text.replace("\xa0", " ")
    
    # Strip links
    header_text = strip_relative_and_internal_links(header_text)
    searchable_header = re.sub(r'[*_`]+', '', header_text)
    
    # Try to find the title: LEI Nº ... or DECRETO Nº ...
    title_match = re.search(
        r'\b(LEI|DECRETO|MEDIDA PROVISÓRIA|LEI COMPLEMENTAR)\s+(?:Nº|Nş|N[°o])\s*([\d.]+)(?:\s*,\s*DE\s+([^|.\n]+))?',
        searchable_header,
        re.I
    )
    
    # Try to find the ementa
    ementa = ""
    if "|" in header_text:
        parts = [p.strip() for p in header_text.split("|")]
        if len(parts) >= 2:
            last_cell = parts[-1]
            if len(last_cell) > 20:
                ementa = last_cell.strip(" |")
                
    if not ementa:
        ementa_match = re.search(r'\b(dispõe|institui|altera|regula|cria|estabelece|autoriza)\b.*$', searchable_header, re.I)
        if ementa_match:
            ementa = ementa_match.group(0).strip(" |")
            
    ementa = re.sub(r'\s+', ' ', ementa).strip()
    
    # Reconstruct premium header
    title_str = ""
    if title_match:
        type_lbl = title_match.group(1).upper()
        num_lbl = title_match.group(2)
        date_lbl = title_match.group(3)
        if date_lbl:
            date_lbl = re.sub(r'\s+', ' ', date_lbl).strip(" .*|")
            title_str = f"{type_lbl} Nº {num_lbl}, DE {date_lbl}"
        else:
            title_str = f"{type_lbl} Nº {num_lbl}"
    else:
        title_str = "LEGISLAÇÃO FEDERAL"
        
    # Append code descriptor if present (e.g. Código Tributário Nacional)
    if "código" in searchable_header.lower():
        code_match = re.search(
            r'([cC][óo]digo\s+[A-Za-zÀ-ÿ\s]+?)(?=\s+(?:Vig[êe]ncia|Vide|Produ[çc][ãa]o|Disp[õo]e)\b|$)',
            searchable_header,
        )
        if code_match:
            code_name = code_match.group(1).strip()
            title_str = f"{title_str} ({code_name})"
            
    premium_header_lines = [
        f"# {title_str}",
        "",
        "> **Presidência da República**",
        "> *Secretaria-Geral - Subchefia para Assuntos Jurídicos*",
        ">"
    ]
    
    if ementa:
        premium_header_lines.append(f"> **Ementa:** {ementa}")
        
    premium_header_lines.append("")
    return "\n".join(premium_header_lines)


@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(_error):
    limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({
        "success": False,
        "error": f"Arquivo muito grande. O limite atual é {limit_mb} MB.",
    }), 413


@app.after_request
def add_no_cache_headers(response):
    if request.path == "/":
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.route("/")
def index():
    """Servir a interface HTML"""
    return send_from_directory(BASE_DIR, "interface.html")


@app.route("/image/<path:filename>")
def serve_image(filename):
    """Servir arquivos da pasta image"""
    return send_from_directory(os.path.join(BASE_DIR, "image"), filename)


@app.route("/api/convert", methods=["POST"])
@login_required
def convert():
    """Converter arquivo ou URL para Markdown"""
    temp_dir = None
    try:
        option = request.form.get("option", "standard")
        url = request.form.get("url", "").strip()
        
        if url:
            # Se não começar com http:// ou https://, mas também não contiver outro protocolo (://), assume https://
            if not (url.startswith("http://") or url.startswith("https://")):
                if "://" not in url:
                    url = "https://" + url
                else:
                    return jsonify({
                        "success": False,
                        "error": "URL inválida. O link deve começar com http:// ou https://",
                    }), 400
            
            import requests
            from urllib.parse import urlparse
            
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                except requests.exceptions.SSLError:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    response = requests.get(url, headers=headers, timeout=15, verify=False)
                response.raise_for_status()
            except Exception as req_err:
                return jsonify({
                    "success": False,
                    "error": f"Erro ao baixar a URL: {str(req_err)}",
                }), 400
                
            parsed_url = urlparse(url)
            url_path = parsed_url.path
            url_filename = os.path.basename(url_path) if url_path else ""
            
            content_type = ""
            if hasattr(response, "headers") and hasattr(response.headers, "get"):
                try:
                    val = response.headers.get("Content-Type")
                    if isinstance(val, str):
                        content_type = val.lower()
                except Exception:
                    pass
            
            detected_ext = None
            if "application/pdf" in content_type:
                detected_ext = "pdf"
            elif "text/html" in content_type:
                detected_ext = "html"
            elif "application/json" in content_type:
                detected_ext = "json"
            elif "application/msword" in content_type:
                detected_ext = "doc"
            elif "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type:
                detected_ext = "docx"
            elif "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_type:
                detected_ext = "xlsx"
            elif "application/vnd.openxmlformats-officedocument.presentationml.presentation" in content_type:
                detected_ext = "pptx"
            elif "text/plain" in content_type:
                detected_ext = "txt"

            default_ext = detected_ext if detected_ext else "html"
            
            if not url_filename or "." not in url_filename:
                filename = f"documento.{default_ext}"
            else:
                filename = secure_filename(url_filename)
                if not filename or "." not in filename:
                    filename = f"documento.{default_ext}"
            
            if not allowed_file(filename):
                filename = filename + f".{default_ext}"
                if not allowed_file(filename):
                    return jsonify({
                        "success": False,
                        "error": f"Formato não suportado: {url_filename}",
                    }), 400
            
            orig_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else default_ext
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            temp_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"upload-{uuid4().hex}")
            os.makedirs(temp_dir, exist_ok=False)
            temp_path = os.path.join(temp_dir, filename)
            
            if orig_ext in ("html", "htm"):
                html_str, _encoding = decode_html_bytes(
                    response.content,
                    default_encoding=response.encoding,
                    prefer_cp1252="planalto.gov.br" in url.lower(),
                )
                
                # Inject <meta charset="utf-8"> to force MarkItDown/BeautifulSoup to parse it as UTF-8
                if "<head>" in html_str.lower():
                    html_str = re.sub(r'(<head\b[^>]*>)', r'\1<meta charset="utf-8">', html_str, flags=re.I)
                else:
                    html_str = '<meta charset="utf-8">' + html_str
                    
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(html_str)
            else:
                with open(temp_path, "wb") as f:
                    f.write(response.content)
        else:
            if "file" not in request.files:
                return jsonify({"success": False, "error": "Nenhum arquivo ou URL fornecido."}), 400
                
            file = request.files["file"]
            if file.filename == "":
                return jsonify({"success": False, "error": "Arquivo não selecionado."}), 400
            
            if not allowed_file(file.filename):
                return jsonify({
                    "success": False,
                    "error": f"Formato não suportado: {file.filename}",
                }), 400
            
            orig_ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
            filename = secure_filename(file.filename)
            if not filename or "." not in filename:
                filename = f"upload-{uuid4().hex}.{orig_ext}" if orig_ext else f"upload-{uuid4().hex}"
    
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            temp_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"upload-{uuid4().hex}")
            os.makedirs(temp_dir, exist_ok=False)
            temp_path = os.path.join(temp_dir, filename)
            file.save(temp_path)
            filepath = temp_path

        # If the file is HTML, sanitize it to prevent truncation by premature </body> tags
        if temp_path.lower().endswith((".html", ".htm")):
            try:
                from bs4 import BeautifulSoup
                
                # First read the raw bytes to detect encoding
                with open(temp_path, "rb") as f:
                    raw_bytes = f.read()
                
                html_content, _encoding = decode_html_bytes(raw_bytes, default_encoding="utf-8")
                
                # First strip body/html tags to prevent premature termination when BeautifulSoup parses it
                html_content = re.sub(r'</?(body|html)[^>]*>', '', html_content, flags=re.IGNORECASE)
                # Parse with BeautifulSoup + lxml to rebuild/close nested structures correctly
                soup = BeautifulSoup(html_content, "lxml")
                html_sanitized = str(soup)
                # Strip body/html tags again to ensure clean body content for downstream converters
                html_sanitized = re.sub(r'</?(body|html)[^>]*>', '', html_sanitized, flags=re.IGNORECASE)
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(html_sanitized)
            except Exception as e:
                print("Error sanitizing HTML:", e)

        if temp_path.lower().endswith(".pdf"):
            # Extração direta com pdfplumber + detecção de colunas para PDFs.
            # Isso garante qualidade consistente independente do tamanho do PDF,
            # evitando o fallback do PdfConverter para pdfminer em PDFs >15 páginas.
            import pdfplumber
            content_parts = []
            with pdfplumber.open(temp_path) as pdf:
                for page in pdf.pages:
                    page_text = extract_text_with_layout_and_columns(page) or ""
                    if page_text.strip():
                        content_parts.append(page_text.strip())
                    page.close()
            content = "\f".join(content_parts)
        elif temp_path.lower().endswith((".html", ".htm")):
            result = md_converter.convert(
                temp_path,
                stream_info=StreamInfo(
                    mimetype="text/html",
                    extension=os.path.splitext(temp_path)[1],
                    charset="utf-8",
                ),
            )
            content = result.text_content
        else:
            result = md_converter.convert(temp_path)
            content = result.text_content
        extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

        # Aplicar formatação de alta fidelidade para PDFs e também para documentos convertidos via URL/HTML
        is_legal_or_pdf = (extension == "pdf" or bool(request.form.get("url", "").strip()) or extension in ("html", "htm"))
        is_legal = False

        if is_legal_or_pdf:
            is_planalto = "presid" in content.lower() and ("casa civil" in content.lower() or "subchefia" in content.lower())
            
            # Check if it actually looks like a legal document before applying legal formatting
            is_legal = is_planalto or (
                "art. 1" in content.lower() or 
                "art.1" in content.lower() or 
                "decreto" in content.lower() or 
                "lei complementar" in content.lower() or 
                "lei nº" in content.lower() or 
                "lei no" in content.lower() or
                "portaria" in content.lower() or
                "resolução" in content.lower()
            )
            
            if is_legal:
                if is_planalto:
                    # Clean encoding glitches and strip relative/internal links on the entire document first
                    content = clean_planalto_encoding_glitches(content)
                    content = strip_relative_and_internal_links(content)
                    
                    # Split and extract header
                    header_text, body_text = split_planalto_document(content)
                    premium_header = generate_premium_header(header_text)
                    
                    # Format body using the standard legal formatter
                    body_text = clean_pdf_headers_footers(body_text)
                    formatted_body = format_pdf_markdown_model2(body_text)
                    
                    # Reassemble the beautiful document
                    content = premium_header + "\n\n" + formatted_body
                else:
                    content = clean_pdf_headers_footers(content)
                    content = format_pdf_markdown_model2(content)

        if option == "compact":
            content = compact_markdown(content)
        elif option == "abnt":
            if is_legal_or_pdf and is_legal:
                content = polish_legal_markdown_model2(content)
            else:
                content = normalize_abnt_markdown(content)
            
        original_length = len(content)
        truncated = False
        if original_length > 10_000_000:
            content = content[:10_000_000] + "\n\n... [conteúdo truncado]"
            truncated = True
            
        return jsonify({
            "success": True,
            "content": content,
            "filename": filename,
            "mode": option,
            "characters": len(content),
            "originalCharacters": original_length,
            "truncated": truncated,
        })
    
    except Exception as e:
        print(f"Erro na conversão: {e}")
        return jsonify({
            "success": False,
            "error": f"Erro ao converter arquivo: {str(e)}",
        }), 500
    finally:
        if temp_dir and os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/api/gazette/index", methods=["POST"])
@login_required
def gazette_index():
    cleanup_gazette_cache()
    
    # Suportar JSON e Form data
    url = ""
    if request.is_json:
        url = request.json.get("url", "").strip()
    else:
        url = request.form.get("url", "").strip()
        
    if not url:
        return jsonify({"success": False, "error": "URL não fornecida."}), 400
        
    if not (url.startswith("http://") or url.startswith("https://")):
        if "://" not in url:
            url = "https://" + url
        else:
            return jsonify({
                "success": False,
                "error": "URL inválida. O link deve começar com http:// ou https://",
            }), 400
            
    import requests
    from urllib.parse import urlparse
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.SSLError:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
    except Exception as req_err:
        return jsonify({
            "success": False,
            "error": f"Erro ao baixar a URL: {str(req_err)}",
        }), 400
        
    # Detectar se é PDF pela extensão da URL ou pelo Content-Type da resposta
    content_type = response.headers.get("Content-Type", "").lower()
    is_pdf_by_content_type = "application/pdf" in content_type or "application/octet-stream" in content_type

    parsed_url = urlparse(url)
    url_path = parsed_url.path
    url_filename = os.path.basename(url_path) if url_path else ""
    if not url_filename or "." not in url_filename:
        filename = "diario.pdf" if is_pdf_by_content_type else ""
    else:
        filename = secure_filename(url_filename)
        if not filename or "." not in filename:
            filename = "diario.pdf" if is_pdf_by_content_type else ""

    if not filename.lower().endswith(".pdf"):
        if is_pdf_by_content_type:
            filename = "diario.pdf"
        else:
            return jsonify({
                "success": False,
                "error": "O arquivo da URL deve ser um PDF (verifique a extensão ou o tipo de conteúdo retornado pelo servidor).",
            }), 400

    # Salvar em cache no disco (compatível com multi-worker)
    os.makedirs(GAZETTE_CACHE_DIR, exist_ok=True)
    cache_id = f"gazette-{uuid4().hex}"
    pdf_path = os.path.join(GAZETTE_CACHE_DIR, f"{cache_id}.pdf")

    with open(pdf_path, "wb") as f:
        f.write(response.content)

    try:
        scan_result = scan_gazette_index(pdf_path)
        gazette_cache_set(
            cache_id,
            pdf_path,
            scan_result["norms"],
            scan_result["total_pages"],
            scan_result.get("index_text", ""),
            scan_result.get("index_entries", []),
        )

        return jsonify({
            "success": True,
            "cache_id": cache_id,
            "total_pages": scan_result["total_pages"],
            "norms": scan_result["norms"],
            "index_text": scan_result.get("index_text", ""),
            "index_entries": scan_result.get("index_entries", []),
        })
    except Exception as e:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        return jsonify({
            "success": False,
            "error": f"Erro ao escanear o Diário Oficial: {str(e)}"
        }), 500


@app.route("/api/gazette/extract", methods=["POST"])
@login_required
def gazette_extract():
    cleanup_gazette_cache()
    
    # Suportar JSON e Form data
    data = {}
    if request.is_json:
        data = request.json
    else:
        data = request.form
        
    cache_id = data.get("cache_id", "")
    norm_id_raw = data.get("norm_id")
    option = data.get("option", "standard")
    
    if not cache_id or norm_id_raw is None:
        return jsonify({"success": False, "error": "cache_id e norm_id são obrigatórios."}), 400

    # Sanitizar cache_id para prevenir path traversal
    if not re.fullmatch(r'gazette-[0-9a-f]{32}', cache_id):
        return jsonify({"success": False, "error": "cache_id inválido."}), 400
        
    try:
        norm_id = int(norm_id_raw)
    except ValueError:
        return jsonify({"success": False, "error": "norm_id deve ser um inteiro."}), 400
        
    cache_item = gazette_cache_get(cache_id)
    if not cache_item:
        return jsonify({"success": False, "error": "Documento não encontrado no cache ou expirado."}), 404
        
    norms = cache_item["norms"]
    if norm_id < 0 or norm_id >= len(norms):
        return jsonify({"success": False, "error": "Norma inválida."}), 400
        
    selected_norm = norms[norm_id]
    start_page = selected_norm["start_page"]
    end_page = selected_norm["end_page"]
    
    # Extrair as páginas do PDF para um arquivo temporário
    from pypdf import PdfReader, PdfWriter
    
    temp_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"extract-{uuid4().hex}")
    os.makedirs(temp_dir, exist_ok=True)
    extracted_pdf_path = os.path.join(temp_dir, "extracted.pdf")
    
    try:
        reader = PdfReader(cache_item["pdf_path"])
        writer = PdfWriter()
        
        # start_page e end_page são 1-indexed.
        for page_idx in range(start_page - 1, min(end_page, len(reader.pages))):
            writer.add_page(reader.pages[page_idx])
            
        with open(extracted_pdf_path, "wb") as f:
            writer.write(f)
            
        # Converter o PDF extraído para Markdown usando extração por colunas diretamente
        import pdfplumber
        content_parts = []
        with pdfplumber.open(extracted_pdf_path) as pdf:
            for page in pdf.pages:
                page_text = extract_text_with_layout_and_columns(page) or ""
                if page_text.strip():
                    content_parts.append(page_text.strip())
        content = "\f".join(content_parts)
        
        # Aplicar limpeza e formatação legal padrão
        content = clean_pdf_headers_footers(content)
        content = format_pdf_markdown_model2(content)
        
        # Delimitação Exata (Fatiamento)
        current_pattern = get_norm_title_pattern(
            selected_norm["tipo"], selected_norm["numero"], selected_norm.get("title")
        )
        
        next_pattern = None
        next_norm_id = _next_linked_gazette_norm_id(cache_item.get("index_entries", []), norm_id)
        if next_norm_id is not None and 0 <= next_norm_id < len(norms):
            next_norm = norms[next_norm_id]
            next_pattern = get_norm_title_pattern(
                next_norm["tipo"], next_norm["numero"], next_norm.get("title")
            )
            
        sliced = slice_norm_markdown(content, current_pattern, next_pattern)
        if sliced is None:
            # Título não localizado no Markdown após conversão — exibe o trecho completo com aviso
            content = (
                f"> **Aviso:** O título da norma não foi localizado com precisão no texto extraído. "
                f"Exibindo o conteúdo completo das páginas {start_page}–{end_page}.\n\n"
                + content
            )
        else:
            content = sliced

        # Deduplicar título da norma que pode aparecer repetido (cabeçalho + corpo)
        tipo_esc = r'\s+'.join(re.escape(w) for w in selected_norm['tipo'].split())
        num_esc = re.escape(selected_norm['numero'])
        if selected_norm["numero"]:
            dup_title_re = re.compile(
                r'('
                + tipo_esc + r'\s+(?:Nº|N[°ºo]\.?)\s*' + num_esc
                + r'[^\n]*\n)'
                + r'\s*'
                + tipo_esc + r'\s+(?:Nº|N[°ºo]\.?)\s*' + num_esc,
                re.IGNORECASE
            )
            content = dup_title_re.sub(r'\1', content)

        # Gerar cabeçalho premium com banner para a norma extraída
        norm_title = selected_norm.get("title") or f"{selected_norm['tipo']} Nº {selected_norm['numero']}"
        norm_ementa = selected_norm.get('ementa', '')
        premium_banner = f"# {norm_title}\n\n"
        if norm_ementa:
            premium_banner += f"> **Ementa:** {norm_ementa}\n\n"
        premium_banner += "---\n\n"

        # Verificar se o conteúdo já começa com o título da norma para evitar duplicação com o banner
        first_line = content.lstrip().split('\n', 1)[0] if content.strip() else ''
        title_already_present = re.search(current_pattern, first_line, re.IGNORECASE)
        if title_already_present:
            # Remover a primeira linha (título cru) pois o banner já o inclui formatado
            lines = content.lstrip().split('\n', 1)
            content = lines[1].lstrip() if len(lines) > 1 else ''

        content = premium_banner + content

        # Aplicar as opções de formatação solicitadas
        if option == "compact":
            content = compact_markdown(content)
        elif option == "abnt":
            content = polish_legal_markdown_model2(content)
            
        original_length = len(content)
        truncated = False
        if original_length > 10_000_000:
            content = content[:10_000_000] + "\n\n... [conteúdo truncado]"
            truncated = True
            
        # Nome do arquivo de saída
        filename = f"{selected_norm['tipo']}_{selected_norm['numero'].replace('/', '_')}.md"
        
        return jsonify({
            "success": True,
            "content": content,
            "filename": filename,
            "norm_title": norm_title,
            "mode": option,
            "characters": len(content),
            "originalCharacters": original_length,
            "truncated": truncated
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Erro ao extrair/converter a norma: {str(e)}"
        }), 500
        
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.route("/api/health", methods=["GET"])
def health():
    """Verificar saúde do servidor"""
    return jsonify({
        "status": "ok",
        "markitdown": "ready",
        "maxUploadMb": app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
        "formats": sorted(ALLOWED_EXTENSIONS),
    })


def get_singular_candidates(word):
    word = word.lower().strip()
    if not word or len(word) <= 2:
        return []

    candidates = []

    exceptions = _load_plural_exceptions()
    clean_word = word.rstrip("s")
    if word in exceptions:
        candidates.append(exceptions[word].lower())
    if clean_word in exceptions:
        exc = exceptions[clean_word].lower()
        if exc not in candidates:
            candidates.append(exc)

    if word.endswith("\u00f5es"):
        candidates.append(word[:-3] + "\u00e3o")
    elif word.endswith("\u00e3es"):
        candidates.append(word[:-3] + "\u00e3o")
        candidates.append(word[:-3] + "\u00e3")
    elif word.endswith("ns"):
        candidates.append(word[:-2] + "m")
    elif word.endswith("ais"):
        candidates.append(word[:-3] + "al")
    elif word.endswith("\u00e9is") or word.endswith("eis"):
        candidates.append(word[:-3] + "el")
    elif word.endswith("\u00f3is") or word.endswith("ois"):
        candidates.append(word[:-3] + "ol")
    elif word.endswith("uis"):
        candidates.append(word[:-3] + "ul")
    elif word.endswith("is"):
        candidates.append(word[:-2] + "il")
    elif word.endswith("res") or word.endswith("zes") or word.endswith("ses") or word.endswith("nes"):
        candidates.append(word[:-2])

    if word.endswith("s") and not word.endswith("ss"):
        candidate = word[:-1]
        if candidate not in candidates:
            candidates.append(candidate)

    # Adicionar candidatos morfológicos extras (particípios e gênero)
    extra_candidates = []
    all_current = [word] + list(candidates)
    for c in all_current:
        # 1. Normalização de gênero (feminino -> masculino)
        if c.endswith("ada"):
            masc = c[:-3] + "ado"
            if masc not in candidates and masc != word:
                extra_candidates.append(masc)
        elif c.endswith("adas"):
            masc = c[:-4] + "ado"
            if masc not in candidates and masc != word:
                extra_candidates.append(masc)
        elif c.endswith("ida"):
            masc = c[:-3] + "ido"
            if masc not in candidates and masc != word:
                extra_candidates.append(masc)
        elif c.endswith("idas"):
            masc = c[:-4] + "ido"
            if masc not in candidates and masc != word:
                extra_candidates.append(masc)

        # 2. Derivação de infinitivo verbal a partir de particípios
        # Verbos em -ar
        if c.endswith("ado") or c.endswith("ada"):
            verb = c[:-3] + "ar"
            if verb not in candidates and verb != word:
                extra_candidates.append(verb)
        elif c.endswith("ados") or c.endswith("adas"):
            verb = c[:-4] + "ar"
            if verb not in candidates and verb != word:
                extra_candidates.append(verb)

        # Verbos em -er / -ir
        elif c.endswith("ido") or c.endswith("ida"):
            verb_er = c[:-3] + "er"
            verb_ir = c[:-3] + "ir"
            for v in [verb_er, verb_ir]:
                if v not in candidates and v != word:
                    extra_candidates.append(v)
        elif c.endswith("idos") or c.endswith("idas"):
            verb_er = c[:-4] + "er"
            verb_ir = c[:-4] + "ir"
            for v in [verb_er, verb_ir]:
                if v not in candidates and v != word:
                    extra_candidates.append(v)

    for ec in extra_candidates:
        if ec not in candidates:
            candidates.append(ec)

    return candidates


WIKTIONARY_API = "https://pt.wiktionary.org/w/api.php"
DICIO_BASE_URL = "https://www.dicio.com.br"

_WIKT_GRAMMAR_VALID = {
    "substantivo", "adjetivo", "verbo", "adverbio",
    "pronome", "preposicao", "conjuncao", "interjeicao",
    "artigo", "numeral", "sigla", "locucao", "expressao", "abreviatura",
}
_WIKT_SKIP = {
    "pronuncia", "traducao", "traducoes",
    "verbetes derivados", "etimologia",
    "paronimos", "homofonos", "referencias",
    "ligacoes externas", "expressoes", "expressoes com",
    "no wikcionario", "categoria", "abreviacoes", "forma",
    "combinacao", "hiperonimos", "hiponimos", "meronimos",
    "acronimos", "gentilicos", "gentilico", "locucao substantiva",
    "substantivo derivado", "verbo auxiliar", "ver tambem",
}


def _wikt_parse_grammar(heading):
    h = heading.lower().strip("=").strip()
    for key in _WIKT_GRAMMAR_VALID:
        if key in h:
            return key
    return None


def _wikt_fetch_and_parse(w):
    wikt_headers = {
        "User-Agent": "DocFlow/1.0 (https://github.com; docflow@example.com) Python-requests"
    }
    titles_to_try = [w, w.lower(), w.capitalize()]

    for title in titles_to_try:
        try:
            params = {
                "action": "query", "prop": "revisions",
                "rvprop": "content", "rvslots": "main",
                "format": "json", "titles": title,
            }
            resp = requests.get(WIKTIONARY_API, params=params, headers=wikt_headers, timeout=8)
            if resp.status_code != 200:
                continue

            pages = resp.json().get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    continue
                revisions = page_data.get("revisions", [])
                if not revisions:
                    continue
                wikitext = revisions[0].get("slots", {}).get("main", {}).get("*", "")
                if not wikitext:
                    continue

                pt_section = re.split(r"\{\{-pt-\}\}", wikitext, maxsplit=1)
                if len(pt_section) < 2:
                    continue
                pt_text = pt_section[1]
                next_lang = re.search(r"\{\{-\w{2,4}-\}\}", pt_text)
                if next_lang:
                    pt_text = pt_text[:next_lang.start()]

                headings = re.findall(r"^(={1,2})(.+?)\1\s*$", pt_text, re.MULTILINE)
                sections = re.split(r"^(?:={1,2})(?:.+?)(?:={1,2})\s*$", pt_text, flags=re.MULTILINE)

                def _should_skip_heading(hdr_text):
                    normalized = unicodedata.normalize("NFKD", hdr_text.lower()).encode("ASCII", "ignore").decode("ASCII").strip().strip("=")
                    for s in _WIKT_SKIP:
                        if s in normalized:
                            return True
                    return False

                def _is_syn_ant(hdr_text):
                    norm = unicodedata.normalize("NFKD", hdr_text.lower()).encode("ASCII", "ignore").decode("ASCII").strip().strip("=")
                    if "sinonimo" in norm:
                        return "syn"
                    if "antonimo" in norm:
                        return "ant"
                    return None

                found_entries = []
                all_synonyms = []
                all_antonyms = []
                for i, section in enumerate(sections):
                    if i == 0:
                        gram = None
                        scope_match = re.search(r"^\s*\{\{([^|}]+)\|pt\}\}", section)
                        if scope_match:
                            gram = _wikt_parse_grammar(scope_match.group(1))
                        syn_ant = None
                    else:
                        hdr_info = headings[i - 1] if i - 1 < len(headings) else ("==", "")
                        hdr_text = hdr_info[1].strip()
                        gram = _wikt_parse_grammar(hdr_text)
                        syn_ant = _is_syn_ant(hdr_text)
                        if gram is None and syn_ant is None:
                            if _should_skip_heading(hdr_text):
                                continue

                    def_lines = re.findall(r"^[#*]+(.+?)$", section, re.MULTILINE)
                    if not def_lines:
                        continue

                    if syn_ant:
                        words = []
                        for line in def_lines:
                            cleaned = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", line)
                            cleaned = re.sub(r"\{\{[^}]+\}\}", "", cleaned)
                            cleaned = cleaned.strip(" .;-\t\n\r,:\"=")
                            if cleaned and len(cleaned) > 1:
                                words.append(cleaned)
                        if syn_ant == "syn":
                            all_synonyms.extend(words)
                        else:
                            all_antonyms.extend(words)
                        continue

                    defs = []
                    for line in def_lines:
                        cleaned = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", line)
                        cleaned = re.sub(r"\{\{[^}]+\}\}", "", cleaned)
                        cleaned = re.sub(r"'''(.+?)'''", r"\1", cleaned)
                        cleaned = cleaned.strip(" .;-\t\n\r,:\"")
                        if cleaned and len(cleaned) > 2 and not cleaned.startswith("="):
                            defs.append(cleaned)

                    if defs:
                        if gram is None:
                            short_word_count = sum(1 for d in defs if " " not in d and len(d) < 30)
                            if short_word_count > max(1, len(defs) * 0.5) and len(defs) < 5:
                                continue
                        found_entries.append({
                            "gram": gram or "",
                            "class": gram or "",
                            "definitions": defs,
                            "meanings": defs,
                            "etym": "",
                            "etymology": "",
                            "orth": title,
                            "synonyms": [],
                            "antonyms": []
                        })

                if found_entries:
                    if all_synonyms:
                        for fe in found_entries:
                            fe["synonyms"] = all_synonyms
                    if all_antonyms:
                        for fe in found_entries:
                            fe["antonyms"] = all_antonyms
                    etym_text = ""
                    etym_match = re.search(r"\{\{etimologia\|pt\}\}\s*\n+:(.+?)(?:\n\n|\n\{\{|\Z)", pt_text, re.DOTALL)
                    if not etym_match:
                        etym_match = re.search(r"==\s*[Ee]timologia\s*==\s*\n+(.+?)(?:\n\n|\n==|\Z)", pt_text, re.DOTALL)
                    if etym_match:
                        etym_text = etym_match.group(1).strip()
                        etym_text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", etym_text)
                        etym_text = re.sub(r"\{\{[^}]+\}\}", "", etym_text)
                        for fe in found_entries:
                            fe["etym"] = etym_text
                            fe["etymology"] = etym_text

                    return found_entries

            break
        except Exception as exc:
            print(f"Wiktionary fetch error for '{title}': {exc}")
            continue

    return None


def _dicio_fetch_and_parse(w):
    try:
        url = f"{DICIO_BASE_URL}/{w.lower()}"
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        })
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        sig_p = soup.find("p", class_=lambda c: c and "significado" in c)
        if not sig_p:
            return None

        sig_spans = sig_p.find_all("span")
        if not sig_spans:
            sig_text = sig_p.get_text(" ", strip=True)
            if not sig_text:
                return None
            sig_spans = [BeautifulSoup(f"<span>{sig_text}</span>", "html.parser").span]

        gram = ""
        first_text = sig_spans[0].get_text(strip=True) if sig_spans else ""
        if re.search(r"substantivo|adjetivo|verbo|adv[eé]rbio|pronome|conjun[cç][aã]o|interjei[cç][aã]o|artigo|numeral", first_text, re.IGNORECASE):
            gram = first_text
            def_spans = sig_spans[1:]
        else:
            def_spans = sig_spans

        gram_el = soup.find("p", class_=lambda c: c and "adicional" in c)
        if not gram and gram_el:
            gram_b = gram_el.find("b")
            if gram_b:
                gram = gram_b.get_text(strip=True)
            else:
                match = re.search(r"Classe gramatical:\s*(.+)", gram_el.get_text(" ", strip=True), re.IGNORECASE)
                if match:
                    gram = match.group(1).strip()

        defs = []
        for span in def_spans:
            txt = span.get_text(" ", strip=True)
            if txt and len(txt) > 5:
                txt = re.sub(r"^\s*\[[^\]]+\]\s*", "", txt)
                if txt and not re.search(r"^(substantivo|adjetivo|verbo|adv[eé]rbio|pronome|conjun[cç][aã]o|interjei[cç][aã]o|numeral|artigo|locu[cç][aã]o|express[aã]o)", txt, re.IGNORECASE):
                    if not re.search(r"^(Etimologia|origem da palavra)", txt, re.IGNORECASE):
                        defs.append(txt)

        etym = ""
        etym_full = soup.find(string=re.compile(r"Etimologia", re.IGNORECASE))
        if etym_full:
            parent = etym_full.parent
            if parent:
                raw = parent.get_text(" ", strip=True)
                etym = re.sub(r"^.*?Etimologia\s*(?:\(origem da palavra[^)]*\))?[.\s]*", "", raw, flags=re.IGNORECASE).strip()

        found_entry = {
            "gram": gram,
            "class": gram,
            "definitions": defs,
            "meanings": defs,
            "etym": etym,
            "etymology": etym,
            "orth": w,
            "synonyms": [],
            "antonyms": []
        }

        syn_p = soup.find("p", class_="adicional sinonimos")
        if syn_p:
            syn_links = syn_p.find_all("a")
            found_entry["synonyms"] = [a.get_text(strip=True) for a in syn_links if a.get_text(strip=True)]

        if defs:
            return [found_entry]
        return None
    except Exception as exc:
        print(f"Dicio fetch error for '{w}': {exc}")
        return None


SINONIMOS_BASE_URL = "https://www.sinonimos.com.br"


def _sinonimos_fetch(w):
    try:
        url = f"{SINONIMOS_BASE_URL}/{w.lower()}"
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        })
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        subtitle_divs = soup.find_all("div", class_="content-detail--subtitle")
        if not subtitle_divs:
            return None

        grouped_synonyms = []
        for div in subtitle_divs:
            sense = div.get_text(" ", strip=True).rstrip(":")
            parent = div.parent
            siblings = list(parent.children)
            try:
                idx = siblings.index(div)
            except ValueError:
                continue
            if idx + 1 >= len(siblings):
                continue
            next_el = siblings[idx + 1]
            syn_text = ""
            if hasattr(next_el, "get_text"):
                syn_text = next_el.get_text(" ", strip=True)
            else:
                syn_text = str(getattr(next_el, "string", "") or "")

            words = re.split(r"[,\s]+", syn_text)
            cleaned = []
            for wrd in words:
                wrd = wrd.strip(" .;,\t\n\r0123456789()-")
                if wrd and len(wrd) > 1:
                    cleaned.append(wrd)
            if cleaned:
                grouped_synonyms.append({
                    "sense": sense,
                    "synonyms": cleaned
                })

        if grouped_synonyms:
            all_synonyms = []
            for g in grouped_synonyms:
                all_synonyms.extend(g["synonyms"])
            all_synonyms = list(dict.fromkeys(all_synonyms))
            return {
                "grouped": grouped_synonyms,
                "all": all_synonyms
            }
        return None
    except Exception as exc:
        print(f"Sinonimos fetch error for '{w}': {exc}")
        return None


@app.route("/api/dictionary", methods=["GET"])
@login_required
def get_dictionary_definition():
    word = request.args.get("word", "").strip()
    if not word:
        return jsonify({"success": False, "error": "Nenhuma palavra fornecida."}), 400

    word_clean = re.sub(r"[^\w\s-]", "", word).strip()
    if not word_clean:
        return jsonify({"success": False, "error": "Nenhuma palavra válida fornecida."}), 400

    is_compound = " " in word_clean
    words_to_try = word_clean.split() if is_compound else [word_clean]

    GRAM_MAP = {
        "m": "substantivo masculino", "m.": "substantivo masculino",
        "f": "substantivo feminino", "f.": "substantivo feminino",
        "s.m.": "substantivo masculino", "s.f.": "substantivo feminino",
        "adj": "adjetivo", "adj.": "adjetivo",
        "v": "verbo", "v.": "verbo",
        "adv": "adverbio", "adv.": "adverbio",
        "num": "numeral", "num.": "numeral",
        "prep": "preposicao", "prep.": "preposicao",
        "conj": "conjuncao", "conj.": "conjuncao",
        "pron": "pronome", "pron.": "pronome",
        "interj": "interjeicao", "interj.": "interjeicao",
        "art": "artigo", "art.": "artigo",
        "s2g": "substantivo de dois generos",
    }

    def _gram_friendly(gram):
        key = gram.lower().strip(" .")
        return GRAM_MAP.get(key, gram)

    def _parse_xml_entries(entries_data, matched_word, source="api"):
        parsed_entries = []
        for entry in entries_data:
            if not entry.get("xml"):
                continue
            try:
                soup = BeautifulSoup(entry["xml"], "xml")
                orth_el = soup.find("orth")
                orth = orth_el.text.strip() if orth_el else entry.get("word", matched_word)
                gram_el = soup.find("gramGrp")
                gram = gram_el.text.strip() if gram_el else ""
                gram_friendly = _gram_friendly(gram)
                etym_el = soup.find("etym")
                etym = etym_el.text.strip() if etym_el else ""
                etym = re.sub(r"_(.+?)_", r"*\1*", etym)
                def_el = soup.find("def")
                defs = []
                if def_el:
                    lines = def_el.text.strip().split("\n")
                    for line in lines:
                        cleaned_line = line.strip(" .;-\t\n\r")
                        if cleaned_line:
                            defs.append(cleaned_line)
                parsed_entries.append({
                    "orth": orth,
                    "gram": gram_friendly,
                    "class": gram_friendly,
                    "definitions": defs,
                    "meanings": defs,
                    "etym": etym,
                    "etymology": etym
                })
            except Exception as parse_err:
                print(f"Error parsing dictionary XML: {parse_err}")
                continue
        
        enriched = _enrich_synonyms(parsed_entries, matched_word)
        return {
            "success": True,
            "word": word_clean,
            "singular": matched_word if matched_word != word_clean else None,
            "definitions": enriched,
            "results": enriched,
            "source": source
        }

    def _lookup_offline(w):
        offline = _load_offline_dict()
        key = w.lower().strip()
        if key in offline:
            entry = offline[key]
            return [{
                "orth": key,
                "gram": _gram_friendly(entry["gram"]),
                "class": _gram_friendly(entry["gram"]),
                "definitions": entry["definitions"],
                "meanings": entry["definitions"],
                "etym": entry.get("etym", ""),
                "etymology": entry.get("etymology", entry.get("etym", ""))
            }]
        return None

    def _fetch_word_from_api(w):
        cached = dict_cache_get(w.lower())
        if cached is not None:
            return cached, w, "cache"

        w_url = f"{DICT_API_BASE_URL}/{w.lower()}"

        last_error = None
        for attempt in range(DICT_API_MAX_RETRIES + 1):
            try:
                res = requests.get(w_url, headers=headers, timeout=DICT_API_TIMEOUT)
                if res.status_code == 200:
                    try:
                        raw_text = res.content.decode("utf-8")
                        data = json.loads(raw_text)
                    except Exception:
                        data = res.json()
                    if data and isinstance(data, list):
                        dict_cache_set(w.lower(), data)
                        return data, w, "api"
                    last_error = "empty_response"
                elif res.status_code == 404:
                    last_error = "not_found"
                    break
                elif res.status_code >= 500:
                    last_error = f"server_error_{res.status_code}"
                else:
                    last_error = f"http_{res.status_code}"
            except requests.exceptions.Timeout:
                last_error = "timeout"
            except requests.exceptions.ConnectionError:
                last_error = "connection_error"
                break
            except Exception as exc:
                last_error = f"network_error: {exc}"

            if attempt < DICT_API_MAX_RETRIES:
                time.sleep(0.5)

        return None, w, f"error:{last_error}"

    def _try_wiktionary(w, source_label="wiktionary"):
        cached = dict_cache_get(f"wikt:{w.lower()}")
        if cached is not None:
            return [{
                "orth": w,
                "gram": cached.get("gram", ""),
                "class": cached.get("class", ""),
                "definitions": cached.get("definitions", []),
                "meanings": cached.get("definitions", []),
                "etym": cached.get("etym", ""),
                "etymology": cached.get("etymology", ""),
                "synonyms": cached.get("synonyms", []),
                "antonyms": cached.get("antonyms", [])
            }] if cached.get("definitions") else None

        entries = _wikt_fetch_and_parse(w)
        if entries and entries[0].get("definitions"):
            dict_cache_set(f"wikt:{w.lower()}", entries[0])
            return entries
        return None

    def _try_dicio(w, source_label="dicio"):
        cached = dict_cache_get(f"dicio:{w.lower()}")
        if cached is not None:
            return [{
                "orth": w,
                "gram": cached.get("gram", ""),
                "class": cached.get("class", ""),
                "definitions": cached.get("definitions", []),
                "meanings": cached.get("definitions", []),
                "etym": cached.get("etym", ""),
                "etymology": cached.get("etymology", ""),
                "synonyms": cached.get("synonyms", []),
                "antonyms": cached.get("antonyms", [])
            }] if cached.get("definitions") else None

        entries = _dicio_fetch_and_parse(w)
        if entries and entries[0].get("definitions"):
            dict_cache_set(f"dicio:{w.lower()}", entries[0])
            return entries
        return None

    def _make_dict_response(entries, matched_word, source):
        enriched = _enrich_synonyms(entries, matched_word) if entries else entries
        return {
            "success": True,
            "word": word_clean,
            "singular": matched_word if matched_word != word_clean else None,
            "definitions": enriched,
            "results": enriched,
            "source": source
        }

    def _enrich_synonyms(entries, w):
        if app.config.get("TESTING") or not entries or len(entries) == 0:
            return entries
        cached = dict_cache_get(f"syn:{w.lower()}")
        syn_data = None
        if cached is not None:
            syn_data = cached
        else:
            syn_data = _sinonimos_fetch(w)
            if syn_data:
                dict_cache_set(f"syn:{w.lower()}", syn_data)
        if not syn_data:
            return entries
        for entry in entries:
            existing = set(entry.get("synonyms", []))
            for sym in syn_data["all"]:
                if sym not in existing:
                    existing.add(sym)
            entry["synonyms"] = list(existing)
            entry["synonym_groups"] = syn_data.get("grouped", [])
        return entries

    try:

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        for w in words_to_try:
            entries_data, matched_word, source = _fetch_word_from_api(w)
            if entries_data:
                return jsonify(_parse_xml_entries(entries_data, matched_word, source))

            candidates = get_singular_candidates(w)
            for cand in candidates:
                entries_data, matched_word, source = _fetch_word_from_api(cand)
                if entries_data:
                    return jsonify(_parse_xml_entries(entries_data, matched_word, source))

        for w in words_to_try:
            dicio_entries = _try_dicio(w)
            if dicio_entries:
                return jsonify(_make_dict_response(dicio_entries, w, "dicio"))

            candidates = get_singular_candidates(w)
            for cand in candidates:
                dicio_entries = _try_dicio(cand)
                if dicio_entries:
                    return jsonify(_make_dict_response(dicio_entries, cand, "dicio"))

        for w in words_to_try:
            wikt_entries = _try_wiktionary(w)
            if wikt_entries:
                return jsonify(_make_dict_response(wikt_entries, w, "wiktionary"))

            candidates = get_singular_candidates(w)
            for cand in candidates:
                wikt_entries = _try_wiktionary(cand)
                if wikt_entries:
                    return jsonify(_make_dict_response(wikt_entries, cand, "wiktionary"))

        offline_data = _lookup_offline(word_clean)
        if offline_data:
            return jsonify({
                "success": True,
                "word": word_clean,
                "singular": None,
                "definitions": _enrich_synonyms(offline_data, word_clean),
                "results": _enrich_synonyms(offline_data, word_clean),
                "source": "offline"
            })

        if is_compound:
            all_results = []
            for w in words_to_try:
                offline = _lookup_offline(w)
                if offline:
                    all_results.extend(offline)
            if all_results:
                return jsonify({
                    "success": True,
                    "word": word_clean,
                    "singular": None,
                    "definitions": _enrich_synonyms(all_results, word_clean),
                    "results": _enrich_synonyms(all_results, word_clean),
                    "source": "offline"
                })

            return jsonify({
                "success": True,
                "word": word_clean,
                "definitions": [],
                "message": f"A expressao '{word_clean}' nao foi encontrada no dicionario."
            })

        return jsonify({
            "success": True,
            "word": word_clean,
            "definitions": [],
            "message": f"A palavra '{word_clean}' nao foi encontrada no dicionario."
        })

    except Exception as e:
        offline_data = _lookup_offline(word_clean)
        if offline_data:
            return jsonify({
                "success": True,
                "word": word_clean,
                "singular": None,
                "definitions": offline_data,
                "results": offline_data,
                "source": "offline"
            })

        print(f"Error in dictionary proxy: {e}")
        return jsonify({
            "success": False,
            "error": f"Erro ao acessar o dicionario: {str(e)}"
        }), 500


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """Realizar login do usuário"""
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    
    if username == APP_USER and password == APP_PASSWORD:
        session["logged_in"] = True
        session.permanent = True
        return jsonify({"success": True, "message": "Autenticado com sucesso."})
    
    return jsonify({"success": False, "message": "Usuário ou senha incorretos."}), 401


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Realizar logout do usuário"""
    session.clear()
    return jsonify({"success": True, "message": "Sessão encerrada com sucesso."})


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Verificar se o usuário está autenticado"""
    return jsonify({"authenticated": session.get("logged_in", False)})


@app.route("/api/saved_docs", methods=["POST"])
@login_required
def save_document():
    """Salva o estado atual de um documento convertido (incluindo marcações HTML)."""
    try:
        data = request.get_json()
        if not data or "html" not in data or "markdown" not in data:
            return jsonify({"success": False, "error": "Dados incompletos."}), 400
        
        filename = data.get("filename", "documento")
        
        doc_id = data.get("doc_id")
        if not doc_id:
            # Remove extensão original se presente
            if '.' in filename:
                filename = filename.rsplit('.', 1)[0]
            
            # Cria um nome de arquivo seguro e único
            safe_filename = secure_filename(filename) or "doc"
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            doc_id = f"{safe_filename}_{timestamp}.json"
        
        filepath = os.path.join(SAVED_DOCS_DIR, doc_id)
        
        # Salva o arquivo
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "id": doc_id,
                "original_filename": filename,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": data.get("mode", "standard"),
                "format": data.get("format", "markdown"),
                "markdown": data["markdown"],
                "html": data["html"]
            }, f, ensure_ascii=False, indent=2)
            
        return jsonify({"success": True, "id": doc_id, "message": "Documento salvo com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/saved_docs", methods=["GET"])
@login_required
def list_saved_documents():
    """Lista todos os documentos salvos."""
    try:
        docs = []
        for filename in os.listdir(SAVED_DOCS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(SAVED_DOCS_DIR, filename)
                try:
                    # Lê apenas para pegar os metadados (para não pesar)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        docs.append({
                            "id": data.get("id", filename),
                            "filename": data.get("original_filename", filename),
                            "timestamp": data.get("timestamp", ""),
                            "mode": data.get("mode", "standard"),
                            "format": data.get("format", "markdown"),
                            "size": os.path.getsize(filepath)
                        })
                except Exception:
                    continue
        
        # Ordena por mais recente primeiro
        docs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return jsonify({"success": True, "documents": docs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/saved_docs/<doc_id>", methods=["GET"])
@login_required
def get_saved_document(doc_id):
    """Retorna um documento salvo específico."""
    try:
        safe_id = secure_filename(doc_id)
        filepath = os.path.join(SAVED_DOCS_DIR, safe_id)
        
        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": "Documento não encontrado."}), 404
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return jsonify({"success": True, "document": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/saved_docs/<doc_id>", methods=["DELETE"])
@login_required
def delete_saved_document(doc_id):
    """Exclui um documento salvo específico."""
    try:
        safe_id = secure_filename(doc_id)
        filepath = os.path.join(SAVED_DOCS_DIR, safe_id)
        
        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": "Documento não encontrado."}), 404
            
        os.remove(filepath)
        return jsonify({"success": True, "message": "Documento excluído com sucesso."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def get_local_ip():
    """Obter o endereço de IP local da LAN para acesso externo na rede."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    debug_enabled = os.getenv("FLASK_DEBUG", "0") == "1"
    local_ip = get_local_ip()

    print(f"""
    ========================================
         DocFlow
    ========================================
    
    Acesso Local:     http://localhost:5000
    Acesso na Rede:   http://{local_ip}:5000
    
    Pressione Ctrl+C para parar o servidor.
    """)
    
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )
