"""
scraper.py
A small library of parsing strategies for teacher homework pages, plus a
single entry point — fetch_homework_for_teacher(teacher) — that looks up
a teacher's "parser" field (see teachers.py) and runs the matching one.

Each parser takes a teacher dict and returns a list of entries shaped like:

    {
        "subject": "math" | "science" | "language_arts",
        "date": "2026-09-04" or None,     # due date, ISO format
        "posted": "2026-08-31" or None,   # date the entry was posted, ISO format
        "text": "Observation/Inference - see Google Classroom for directions",
        "source": "https://..."
    }

If a parser can't confidently find structured entries, it falls back to
returning the raw page text rather than silently returning nothing.
"""

import re
import datetime
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

TODAY = datetime.date.today()
CURRENT_YEAR = TODAY.year
WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"


def _school_year_start():
    """The calendar year the CURRENT school year began in. School years run
    roughly Aug-June, so Jan-Jun dates belong to the year AFTER this."""
    return TODAY.year if TODAY.month >= 7 else TODAY.year - 1


def _year_for_month(month):
    start = _school_year_start()
    return start if month >= 7 else start + 1


MD_ONLY_RE = re.compile(r"^(\d{1,2})[/-](\d{1,2})$")


def _safe_parse_date(raw):
    """Turn a fuzzy date string into an ISO date, or None on failure.
    Bare 'M/D' strings (no year) get the correct school year inferred,
    instead of always assuming the current calendar year."""
    if not raw:
        return None
    raw = raw.strip().rstrip(",")

    m = MD_ONLY_RE.match(raw)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        try:
            return datetime.date(_year_for_month(month), month, day).isoformat()
        except ValueError:
            return None

    try:
        dt = dateparser.parse(raw, fuzzy=True, default=datetime.datetime(CURRENT_YEAR, 1, 1))
        if dt.year < CURRENT_YEAR - 1 or dt.year > CURRENT_YEAR + 1:
            return None
        return dt.date().isoformat()
    except (ValueError, OverflowError):
        return None


def _get_page_text(url):
    """Fetch a page and return its visible text as a list of non-empty lines."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = soup.get_text("\n")
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _error_entry(teacher, message):
    return [{
        "subject": teacher["subject"], "date": None, "posted": None,
        "text": message, "source": teacher["url"],
    }]


# ---------------------------------------------------------------------------
# Parser: date_prefix_line
# Simple "M/D  description" lines, e.g. Mr. Greene's Language Arts page.
# ---------------------------------------------------------------------------
DATE_PREFIX_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(.*)$")


def parse_date_prefix_line(teacher):
    try:
        lines = _get_page_text(teacher["url"])
    except requests.RequestException as e:
        return _error_entry(teacher, f"Couldn't reach {teacher['name']}'s site ({e}).")

    entries = []
    for line in lines:
        m = DATE_PREFIX_RE.match(line)
        if not m:
            continue
        month, day, desc = m.groups()
        posted = _safe_parse_date(f"{month}/{day}")
        entries.append({
            "subject": teacher["subject"], "date": None, "posted": posted,
            "text": desc.strip(), "source": teacher["url"],
        })
    return entries


# ---------------------------------------------------------------------------
# Parser: weekday_due
# "Weekday, date" header, description lines, then "Due: date" — e.g. Dalvand's
# Science page.
# ---------------------------------------------------------------------------
WEEKDAY_HEADER_RE = re.compile(rf"^({WEEKDAYS}),\s*(.+)$")
DUE_RE = re.compile(r"^Due:\s*(.*)$", re.IGNORECASE)
WEEK_HEADER_RE = re.compile(r"^Week\s*#?\d+.*$", re.IGNORECASE)


def parse_weekday_due(teacher):
    try:
        lines = _get_page_text(teacher["url"])
    except requests.RequestException as e:
        return _error_entry(teacher, f"Couldn't reach {teacher['name']}'s site ({e}).")

    entries = []
    current = None
    for line in lines:
        if WEEK_HEADER_RE.match(line):
            continue
        header_match = WEEKDAY_HEADER_RE.match(line)
        due_match = DUE_RE.match(line)
        if header_match:
            if current and current["text"]:
                entries.append(current)
            posted = _safe_parse_date(header_match.group(2))
            current = {"subject": teacher["subject"], "date": None, "posted": posted,
                       "text": "", "source": teacher["url"]}
        elif due_match and current is not None:
            current["date"] = _safe_parse_date(due_match.group(1)) or current["date"]
        elif current is not None:
            current["text"] = (current["text"] + " " + line).strip() if current["text"] else line
    if current and current["text"]:
        entries.append(current)
    return entries


# ---------------------------------------------------------------------------
# Parser: classwork_homework_log
# "Weekday, M/D" header, then "Classwork: ..." and "Homework: ..." lines,
# repeated daily — the CPM-style log used by several CUSD math teachers,
# e.g. Village C's Math 8 page.
# ---------------------------------------------------------------------------
CH_HEADER_RE = re.compile(rf"^(?:(?:{WEEKDAYS}),?\s*)?(\d{{1,2}}/\d{{1,2}})$")
HOMEWORK_LINE_RE = re.compile(r"^Homework(?:\s*(?:and|&)\s*Classwork)?:\s*(.*)$", re.IGNORECASE)
SKIP_TEXT = {"none", "none.", "n/a", "na", ""}


def parse_classwork_homework_log(teacher):
    try:
        lines = _get_page_text(teacher["url"])
    except requests.RequestException as e:
        return _error_entry(teacher, f"Couldn't reach {teacher['name']}'s site ({e}).")

    entries = []
    current_date = None
    for line in lines:
        header_match = CH_HEADER_RE.match(line)
        if header_match:
            current_date = _safe_parse_date(header_match.group(1))
            continue
        hw_match = HOMEWORK_LINE_RE.match(line)
        if hw_match and current_date:
            text = hw_match.group(1).strip()
            if text.lower().rstrip(".") not in SKIP_TEXT:
                entries.append({
                    "subject": teacher["subject"], "date": current_date, "posted": current_date,
                    "text": text, "source": teacher["url"],
                })
    return entries


# ---------------------------------------------------------------------------
# Parser: google_doc_table
# The teacher's page links to a Google Doc with a TABLE inside it (columns
# like "Date Assigned" / "Date Due" / "Assignment") — e.g. Ms. Larcher's
# Geometry page. Falls back to a line-by-line date scan, then to raw text,
# if no usable table is found.
# ---------------------------------------------------------------------------
DOC_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)|[?&]id=([a-zA-Z0-9_-]+)")
DATE_LINE_RE = re.compile(
    r"^(?:(" + WEEKDAYS + r"),?\s*)?"
    r"(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?|[A-Za-z]+\s+\d{1,2}(,?\s*\d{2,4})?)\b[:\-]?\s*(.*)$"
)
ASSIGNED_HEADER_HINTS = ("assign", "posted", "given", "start")
DUE_HEADER_HINTS = ("due",)
DESC_HEADER_HINTS = ("assignment", "homework", "topic", "description", "notes", "task", "work")


def _extract_table_entries(doc_soup, teacher):
    entries = []
    for table in doc_soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        header_lower = [h.lower() for h in header_cells]
        if not header_cells:
            continue

        assigned_idx = due_idx = desc_idx = None
        for i, h in enumerate(header_lower):
            if assigned_idx is None and any(hint in h for hint in ASSIGNED_HEADER_HINTS):
                assigned_idx = i
            elif due_idx is None and any(hint in h for hint in DUE_HEADER_HINTS):
                due_idx = i
            elif desc_idx is None and any(hint in h for hint in DESC_HEADER_HINTS):
                desc_idx = i

        if assigned_idx is None and due_idx is None:
            continue
        if desc_idx is None:
            used = {i for i in (assigned_idx, due_idx) if i is not None}
            remaining = [i for i in range(len(header_cells)) if i not in used]
            desc_idx = remaining[0] if remaining else None

        for row in rows[1:]:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            if not cells or not any(cells):
                continue
            posted = (_safe_parse_date(cells[assigned_idx])
                      if assigned_idx is not None and assigned_idx < len(cells) else None)
            due = (_safe_parse_date(cells[due_idx])
                   if due_idx is not None and due_idx < len(cells) else None)
            text = (cells[desc_idx].strip()
                    if desc_idx is not None and desc_idx < len(cells) else " ".join(cells).strip())
            if not text:
                continue
            entries.append({
                "subject": teacher["subject"], "date": due, "posted": posted,
                "text": text, "source": teacher["url"],
            })
    return entries


def _extract_line_entries(doc_text, teacher):
    entries = []
    lines = [ln.strip() for ln in doc_text.split("\n") if ln.strip()]
    current = None
    for line in lines:
        dm = DATE_LINE_RE.match(line)
        if dm and len(line) < 60:
            if current and current["text"]:
                entries.append(current)
            posted = _safe_parse_date(dm.group(2))
            current = {"subject": teacher["subject"], "date": posted, "posted": posted,
                       "text": (dm.group(5) or "").strip(), "source": teacher["url"]}
        elif current is not None:
            current["text"] = (current["text"] + " " + line).strip() if current["text"] else line
        else:
            current = {"subject": teacher["subject"], "date": None, "posted": None,
                       "text": line, "source": teacher["url"]}
    if current and current["text"]:
        entries.append(current)
    return entries, lines


def parse_google_doc_table(teacher):
    try:
        resp = requests.get(teacher["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        doc_link = None
        for a in soup.find_all("a", href=True):
            if "docs.google.com/document" in a["href"] or "drive.google.com" in a["href"]:
                doc_link = a["href"]
                break
        if not doc_link:
            return _error_entry(teacher, "No homework document link found on this page right now.")

        m = DOC_ID_RE.search(doc_link)
        doc_id = next((g for g in (m.groups() if m else []) if g), None)
        if not doc_id:
            return _error_entry(teacher, "Found a link but couldn't read its document ID.")

        html_url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
        html_resp = requests.get(html_url, headers=HEADERS, timeout=15)
        html_resp.raise_for_status()
        doc_soup = BeautifulSoup(html_resp.text, "html.parser")

        entries = _extract_table_entries(doc_soup, teacher)
        if entries:
            return entries

        txt_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        txt_resp = requests.get(txt_url, headers=HEADERS, timeout=15)
        txt_resp.raise_for_status()
        entries, lines = _extract_line_entries(txt_resp.text, teacher)
        if entries:
            return entries

        full_text = " ".join(lines)[:2000]
        return _error_entry(teacher, full_text or "The homework document appears to be empty.")

    except requests.RequestException as e:
        return _error_entry(teacher, f"Couldn't reach the homework document ({e}).")


PARSERS = {
    "date_prefix_line": parse_date_prefix_line,
    "weekday_due": parse_weekday_due,
    "classwork_homework_log": parse_classwork_homework_log,
    "google_doc_table": parse_google_doc_table,
}


def fetch_homework_for_teacher(teacher):
    parser = PARSERS.get(teacher["parser"])
    if not parser:
        return _error_entry(teacher, f"No parser configured for '{teacher['parser']}'.")
    return parser(teacher)
