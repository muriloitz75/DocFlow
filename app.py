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
from datetime import datetime
from uuid import uuid4
from functools import wraps

# Adicionar o diretório do markitdown ao path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "packages", "markitdown", "src"))

from markitdown import MarkItDown

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
    (2, re.compile(r"^(?:DAS\s+)?DISPOSI[ÇC](?:[ÃA]O|[ÕO]ES)\s+(?:PRELIMINAR(?:ES)?|GERA(?:IS|L)|FINA(?:IS|L)|TRANSIT[ÓO]RIA(?:S)?)\b", re.I)),
    (2, re.compile(r"^T[ÍI]TULO\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    (3, re.compile(r"^CAP[ÍI]TULO\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    (4, re.compile(r"^SE[ÇC][ÃA]O\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
    (5, re.compile(r"^SUBSE[ÇC][ÃA]O\s+(?:[IVXLCDM]+|[0-9]+)\b", re.I)),
]

STRUCTURAL_LINE_PATTERNS = [
    re.compile(r"^#{1,6}\s+\S+"),
    re.compile(r"^Art\.?\s*\d+", re.I),
    re.compile(r"^§\s*\d+"),
    re.compile(r"^[IVXLCDM]+\s*[-–—]", re.I),
    re.compile(r"^[a-z]\)\s+", re.I),
    re.compile(r"^\|"),
    re.compile(r"^```"),
]

CITATION_PATTERN = re.compile(
    r'^\s*(?:Arts?\.?|\u00a7\u00a7?)\s*\d+(?:\.[\u00ba\u00b0\u00aa\u015f]|[\u00ba\u00b0\u00aa\u015foa])?\.?\s*(?:,\s*|da\b|do\b|de\b|e\b|inciso\b|al[\u00edi]nea\b|\s*da\s+Const|dos\b|das\b|s[\u00f4o]bre\b|\bcaput\b)',
    re.IGNORECASE
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
    boundary = r'(?:[).;]|Produ[\u00e7c][\u00e3a]o\s+de\s+efeitos|Vig[\u00eae]ncia|Vide\b)'
    
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
    clean_stripped = re.sub(r"^[\*_]+|[\*_]+$", "", stripped).strip()

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
        
    clean_text = re.sub(r"^[\*_]+", "", text).strip()
    
    if CITATION_PATTERN.match(clean_text):
        return False
    if any(pattern.match(clean_text) for pattern in STRUCTURAL_LINE_PATTERNS[1:]):
        return True
        
    roman_match = re.match(r"^([IVXLCDM]+)\b\s*(?:[-–—]\s*)?(?![.,;:?!\)])", clean_text, flags=re.I)
    if roman_match and roman_match.group(1).upper() in VALID_ROMANS:
        return True
        
    return False


def _format_article_start(text):
    # Regex to match article number and suffix precisely without swallowing letters like 'O' and 'A'
    # Handles optional opening and closing bold/italic markdown wrappers
    article_pattern = re.compile(
        r"^(?:\*\*|\*|)?[Aa]rt\.?\s*(\d+(?:-[A-Z])?)(?:\.?(?:[\u00ba\u00b0\u00aa\u015f]|[oa]\b))?\.?(?:\*\*|\*|)?\s*(.*)$"
    )
    match = article_pattern.match(text)
    if not match:
        # Check and format Parágrafo único
        if re.match(r"^(?:\*\*|\*|)?Par[\u00e1a]grafo\s+[\u00fau]nico\.?(?:\*\*|\*|)?\s*(.*)$", text, re.I):
            rest = re.sub(r"^(?:\*\*|\*|)?Par[\u00e1a]grafo\s+[\u00fau]nico\.?(?:\*\*|\*|)?\s*", "", text, flags=re.I).strip()
            return f"**Parágrafo único.** {rest}".strip()
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
        
    return f"{prefix} {rest}".strip()


def _format_paragraph_start(text):
    paragraph_pattern = re.compile(
        r"^(?:\*\*|\*|)?\u00a7\s*(\d+)(?:\.?(?:[\u00ba\u00b0\u00aa\u015f]|[oa]\b))?\.?(?:\*\*|\*|)?\s*(.*)$"
    )
    match = paragraph_pattern.match(text)
    if not match:
        return text

    num_str = match.group(1)
    rest = match.group(2).strip()
    prefix = f"**§ {num_str}º**"
    return f"{prefix} {rest}".strip()


def _format_inciso_start(text):
    inciso_pattern = re.compile(
        r"^(?:\*\*|\*|)?([IVXLCDM]+)(?:\*\*|\*|)?\b\s*(?:[-–—]\s*)?(?![.,;:?!\)])(.*)$", re.I
    )
    match = inciso_pattern.match(text)
    if not match:
        return text

    roman_num = match.group(1).upper()
    if roman_num not in VALID_ROMANS:
        return text

    rest = match.group(2).strip()
    if not rest:
        return text
        
    return f"{roman_num} - {rest}".strip()


def _join_wrapped_lines(lines):
    paragraph = " ".join(_normalize_text_line(line) for line in lines if _normalize_text_line(line))
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
        
    # Limpar marcações de formatação em negrito/itálico para inspecionar o prefixo limpo
    clean_current = re.sub(r"^[\*_]+|[\*_]+$", "", current).strip()
    
    # Proibir mesclagem se a linha seguinte começar com termos ou símbolos estruturais de leis
    if re.match(r"^(?:Art\.?|\u00a7|Par[\u00e1a]grafo\s+[\u00fau]nico)(?:\s|$)", clean_current, flags=re.I):
        if not CITATION_PATTERN.match(clean_current):
            return False
    if re.match(r"^[IVXLCDM]+\b", clean_current, flags=re.I):
        return False
    if re.match(r"^[a-z]\)", clean_current, flags=re.I):
        return False
    if re.match(r"^[-*+•]", clean_current):
        return False

    previous_has_terminal = bool(re.search(r"[.!?:;]$", previous))
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
            output[-1] = f"{previous.rstrip()} {_normalize_text_line(next_line)}"
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
        line = re.sub(r"\s+([,.;:!?])", r"\1", line)
        line = _split_official_clauses(line)
        output.append(line)
        index += 1

    polished = compact_markdown("\n".join(output))
    polished = _merge_spurious_continuation_breaks(polished)
    polished = _repair_known_pdf_text_dislocations(polished)
    return compact_markdown(polished)


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

        is_art_or_par = (re.match(r"^Art\.?\s*\d+", line, flags=re.I) or re.match(r"^§\s*\d+", line))
        if is_art_or_par and not CITATION_PATTERN.match(line):
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
            append_block(paragraph)
            continue

        is_inciso = False
        roman_match = re.match(r"^([IVXLCDM]+)\b\s*(?:[-–—]\s*)?(?![.,;:?!\)])", line, flags=re.I)
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
        append_block(_join_wrapped_lines(paragraph_lines))

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
    
    promulgation_pattern = re.compile(
        r'^\s*(?:\*\*|\*|)?(?:O\s+PRESIDENTE\s+DA\s+REP[ÚU]BLICA|O\s+CONGRESSO\s+NACIONAL|O\s+GOVERNADOR|O\s+PREFEITO|A\s+ASSEMBL[ÉE]IA\s+LEGISLATIVA|A\s+C[ÂA]MARA\s+MUNICIPAL)\b',
        re.I
    )
    
    promulgation_idx = -1
    for idx, line in enumerate(lines):
        if promulgation_pattern.match(line):
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
    
    # Strip links
    header_text = strip_relative_and_internal_links(header_text)
    
    # Try to find the title: LEI Nº ... or DECRETO Nº ...
    title_match = re.search(
        r'\b(LEI|DECRETO|MEDIDA PROVISÓRIA|LEI COMPLEMENTAR)\s+(?:Nº|Nş|N[°o])\s*([\d.]+)(?:\s*,\s*DE\s+([^|.\n]+))?',
        header_text,
        re.I
    )
    
    # Try to find the ementa
    ementa = ""
    if "|" in header_text:
        parts = [p.strip() for p in header_text.split("|")]
        if len(parts) >= 2:
            last_cell = parts[-1]
            if len(last_cell) > 20:
                ementa = last_cell
                
    if not ementa:
        ementa_match = re.search(r'\b(dispõe|institui|altera|regula|cria|estabelece|autoriza)\b.*$', header_text, re.I)
        if ementa_match:
            ementa = ementa_match.group(0)
            
    ementa = re.sub(r'\s+', ' ', ementa).strip()
    
    # Reconstruct premium header
    title_str = ""
    if title_match:
        type_lbl = title_match.group(1).upper()
        num_lbl = title_match.group(2)
        date_lbl = title_match.group(3)
        if date_lbl:
            date_lbl = date_lbl.strip(" .")
            title_str = f"{type_lbl} Nº {num_lbl}, DE {date_lbl}"
        else:
            title_str = f"{type_lbl} Nº {num_lbl}"
    else:
        title_str = "LEGISLAÇÃO FEDERAL"
        
    # Append code descriptor if present (e.g. Código Tributário Nacional)
    if "código" in header_text.lower():
        code_match = re.search(r'([cC][óo]digo\s+[A-Za-zÀ-ÿ\s]+)', header_text)
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
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
            except Exception as req_err:
                return jsonify({
                    "success": False,
                    "error": f"Erro ao baixar a URL: {str(req_err)}",
                }), 400
                
            parsed_url = urlparse(url)
            url_path = parsed_url.path
            url_filename = os.path.basename(url_path) if url_path else ""
            if not url_filename or "." not in url_filename:
                filename = "documento.html"
            else:
                filename = secure_filename(url_filename)
                if not filename or "." not in filename:
                    filename = "documento.html"
            
            if not allowed_file(filename):
                filename = filename + ".html"
                if not allowed_file(filename):
                    return jsonify({
                        "success": False,
                        "error": f"Formato não suportado: {url_filename}",
                    }), 400
            
            orig_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "html"
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            temp_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"upload-{uuid4().hex}")
            os.makedirs(temp_dir, exist_ok=False)
            temp_path = os.path.join(temp_dir, filename)
            
            # planalto and other Brazilian government pages are typically served in ISO-8859-1 or CP1252
            # Let's decode it correctly and write as UTF-8 to prevent any parsing encoding issues
            encoding = response.encoding
            if "planalto.gov.br" in url.lower():
                encoding = "cp1252"
            elif not encoding or encoding.lower() in ('iso-8859-1', 'latin-1'):
                encoding = "cp1252"
                
            try:
                html_str = response.content.decode(encoding, errors='replace')
            except Exception:
                html_str = response.content.decode('cp1252', errors='replace')
                
            # Inject <meta charset="utf-8"> to force MarkItDown/BeautifulSoup to parse it as UTF-8
            if "<head>" in html_str.lower():
                html_str = re.sub(r'(<head\b[^>]*>)', r'\1<meta charset="utf-8">', html_str, flags=re.I)
            else:
                html_str = '<meta charset="utf-8">' + html_str
                
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(html_str)
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
        
        result = md_converter.convert(temp_path)
        content = result.text_content
        extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

        # Aplicar formatação de alta fidelidade para PDFs e também para documentos convertidos via URL/HTML
        is_legal_or_pdf = (extension == "pdf" or bool(request.form.get("url", "").strip()) or extension in ("html", "htm"))

        if is_legal_or_pdf:
            is_planalto = "presid" in content.lower() and ("casa civil" in content.lower() or "subchefia" in content.lower())
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
            if is_legal_or_pdf:
                content = polish_legal_markdown_model2(content)
            else:
                content = normalize_abnt_markdown(content)
            
        original_length = len(content)
        truncated = False
        if original_length > 1_000_000:
            content = content[:1_000_000] + "\n\n... [conteúdo truncado]"
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


@app.route("/api/health", methods=["GET"])
def health():
    """Verificar saúde do servidor"""
    return jsonify({
        "status": "ok",
        "markitdown": "ready",
        "maxUploadMb": app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
        "formats": sorted(ALLOWED_EXTENSIONS),
    })


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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            doc_id = f"{safe_filename}_{timestamp}.json"
        
        filepath = os.path.join(SAVED_DOCS_DIR, doc_id)
        
        # Salva o arquivo
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "id": doc_id,
                "original_filename": filename,
                "timestamp": datetime.now().isoformat(),
                "mode": data.get("mode", "standard"),
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
