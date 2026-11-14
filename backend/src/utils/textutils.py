"""文本工具：保单号 / 日期 / 身份证校验位 / 文件名归一。"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime

POLICY_RE = re.compile(r"(?<![A-Za-z0-9])(P\d{12})(?![0-9])")
INVOICE_CODE_RE = re.compile(r"发票代码[:：]?\s*(\d{12})")
ID_CANDIDATE_RE = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")
FILENAME_DATE_RE = re.compile(r"(20\d{2})(\d{2})(\d{2})")
TEXT_DATE_RE = re.compile(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})")

_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK = "10X98765432"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def safe_filename(name: str) -> str:
    """去掉路径分隔符与 Windows 非法字符，其余（中文）保留。"""
    cleaned = unicodedata.normalize("NFC", name or "")
    cleaned = cleaned.replace("\\", "_").replace("/", "_")
    cleaned = re.sub(r'[<>:"|?*\x00-\x1f]', "_", cleaned)
    return cleaned.strip() or "unnamed"


def extract_policy_no(text: str) -> tuple[str, str]:
    """返回 (保单号, 来源)。来源：filename/content/''。调用方决定来源标签。"""
    if not text:
        return "", ""
    match = POLICY_RE.search(text)
    return (match.group(1), "hit") if match else ("", "")


def extract_doc_date(text: str) -> date | None:
    if not text:
        return None
    for regex in (FILENAME_DATE_RE, TEXT_DATE_RE):
        for match in regex.finditer(text):
            year, month, day = (int(part) for part in match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                continue
    return None


def id_card_checksum_ok(id_number: str) -> bool:
    """GB 11643-1999 18 位身份证校验位。"""
    if not id_number or len(id_number) != 18:
        return False
    body, check = id_number[:17], id_number[17].upper()
    if not body.isdigit():
        return False
    total = sum(int(body[i]) * _ID_WEIGHTS[i] for i in range(17))
    return _ID_CHECK[total % 11] == check


def extract_id_number(text: str) -> tuple[str, bool]:
    """返回 (身份证号, 校验位是否通过)。"""
    if not text:
        return "", False
    for match in ID_CANDIDATE_RE.finditer(text):
        candidate = match.group(1).upper()
        if id_card_checksum_ok(candidate):
            return candidate, True
        return candidate, False
    return "", False


def extract_invoice_code(text: str) -> str:
    match = INVOICE_CODE_RE.search(text or "")
    return match.group(1) if match else ""


def human_size(size_bytes: int) -> str:
    value = float(max(size_bytes, 0))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def now_stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")
