"""
scraper.py
Pulls homework listings from the three teacher sites and normalizes them
into a common format:

    {
        "subject": "math" | "science" | "language_arts",
        "date": "2026-09-04" or None,     # due date if we could find one, ISO format
        "posted": "2026-08-31" or None,   # date the entry was posted, ISO format
        "text": "Observation/Inference - see Google Classroom for directions",
        "source": "https://..."
    }

Each site is formatted differently, so each has its own small parser.
If a site changes its layout and a parser stops finding dates, it falls
back to returning the raw text so nothing silently disappears.
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

SITES = {
    "math": "https://sites.google.com/cusdk8.org/mslarcher/ccgeometry/ccgeometry-first-semester",
    "language_arts": "https://sites.google.com/a/cusdk8.org/mr-greene-s-language-arts-class/home/home-work",
    "science": "https://sites.google.com/cusdk8.org/8th-grade-science-dalvand/homework",
}

WEEKDAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"


def _get_page_text(url):
    """Fetch a page and return its visible text, one chunk of text per line."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Drop obvious non-content chrome
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    text = soup.get_text("\n")
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    return lines


def _safe_parse_date(raw):
    """Try to turn a fuzzy date string into an ISO date. Returns None on failure
    or if the result is an implausible school-year date."""
    try:
        dt = dateparser.parse(raw, fuzzy=True, default=datetime.datetime(CURRENT_YEAR, 1, 1))
        if dt.year < CURRENT_YEAR - 1 or dt.year > CURRENT_YEAR + 1:
            return None
        return dt.date().isoformat()
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Language Arts — simple "M/D  description" lines, most recent at the top
# ---------------------------------------------------------------------------
LA_LINE = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(.*)$")


def scrape_language_arts():
    url = SITES["language_arts"]
    entries = []
    try:
        lines = _get_page_text(url)
    except requests.RequestException as e:
        return [{"subject": "language_arts", "date": None, "posted": None,
                  "text": f"Couldn't reach the Language Arts site ({e}).", "source": url}]

    for line in lines:
        m = LA_LINE.match(line)
        if not m:
            continue
        month, day, desc = m.groups()
        posted = _safe_parse_date(f"{month}/{day}/{CURRENT_YEAR}")
        entries.append({
            "subject": "language_arts",
            "date": None,        # this site doesn't separate "due date" from "posted date"
            "posted": posted,
            "text": desc.strip(),
            "source": url,
        })
    return entries


# ---------------------------------------------------------------------------
# Science — "Weekday, M-D-YY" header, description lines, then "Due: ..."
# ---------------------------------------------------------------------------
SCI_DATE_HEADER = re.compile(rf"^({WEEKDAYS}),\s*(.+)$")
SCI_DUE = re.compile(r"^Due:\s*(.*)$", re.IGNORECASE)
SCI_WEEK_HEADER = re.compile(r"^Week\s*#?\d+.*$", re.IGNORECASE)


def scrape_science():
    url = SITES["science"]
    entries = []
    try:
        lines = _get_page_text(url)
    except requests.RequestException as e:
        return [{"subject": "science", "date": None, "posted": None,
                  "text": f"Couldn't reach the Science site ({e}).", "source": url}]

    current = None
    for line in lines:
        if SCI_WEEK_HEADER.match(line):
            continue

        header_match = SCI_DATE_HEADER.match(line)
        due_match = SCI_DUE.match(line)

        if header_match:
            if current and current["text"]:
                entries.append(current)
            posted = _safe_parse_date(header_match.group(2))
            current = {"subject": "science", "date": None, "posted": posted,
                       "text": "", "source": url}
        elif due_match and current is not None:
            current["date"] = _safe_parse_date(due_match.group(1)) or current["date"]
        elif current is not None:
            current["text"] = (current["text"] + " " + line).strip() if current["text"] else line

    if current and current["text"]:
        entries.append(current)
    return entries


# ---------------------------------------------------------------------------
# Math — the homework itself lives in a linked Google Doc, not the page.
# We find the doc link on the page, then pull the doc as plain text and
# look for date-like lines to split it into entries. If no dates are found
# (doc formatted differently than expected), we fall back to returning the
# whole document as one entry so nothing is lost.
# ---------------------------------------------------------------------------
DOC_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)|[?&]id=([a-zA-Z0-9_-]+)")
DATE_LINE = re.compile(
    r"^(?:(" + WEEKDAYS + r"),?\s*)?"
    r"(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?|[A-Za-z]+\s+\d{1,2}(,?\s*\d{2,4})?)\b[:\-]?\s*(.*)$"
)


def scrape_math():
    page_url = SITES["math"]
    entries = []
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        doc_link = None
        for a in soup.find_all("a", href=True):
            if "docs.google.com/document" in a["href"] or "drive.google.com" in a["href"]:
                doc_link = a["href"]
                break
        if not doc_link:
            return [{"subject": "math", "date": None, "posted": None,
                      "text": "No homework document link found on the Math page right now.",
                      "source": page_url}]

        m = DOC_ID_RE.search(doc_link)
        doc_id = next((g for g in (m.groups() if m else []) if g), None)
        if not doc_id:
            return [{"subject": "math", "date": None, "posted": None,
                      "text": "Found a link on the Math page but couldn't read its document ID.",
                      "source": doc_link}]

        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        doc_resp = requests.get(export_url, headers=HEADERS, timeout=15)
        doc_resp.raise_for_status()
        doc_lines = [ln.strip() for ln in doc_resp.text.split("\n") if ln.strip()]

        current = None
        for line in doc_lines:
            dm = DATE_LINE.match(line)
            if dm and len(line) < 60:  # date headers are short; long lines are body text
                if current and current["text"]:
                    entries.append(current)
                date_str = dm.group(2)
                rest = dm.group(5) or ""
                posted = _safe_parse_date(date_str)
                current = {"subject": "math", "date": posted, "posted": posted,
                           "text": rest.strip(), "source": doc_link}
            elif current is not None:
                current["text"] = (current["text"] + " " + line).strip() if current["text"] else line
            else:
                current = {"subject": "math", "date": None, "posted": None,
                           "text": line, "source": doc_link}

        if current and current["text"]:
            entries.append(current)

        if not entries:
            full_text = " ".join(doc_lines)[:2000]
            entries = [{"subject": "math", "date": None, "posted": None,
                        "text": full_text or "The homework document appears to be empty.",
                        "source": doc_link}]
        return entries

    except requests.RequestException as e:
        return [{"subject": "math", "date": None, "posted": None,
                  "text": f"Couldn't reach the Math site or its homework document ({e}).",
                  "source": page_url}]


def scrape_all():
    return {
        "math": scrape_math(),
        "science": scrape_science(),
        "language_arts": scrape_language_arts(),
    }
