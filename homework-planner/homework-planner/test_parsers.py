"""Offline test of the parsing logic using real text pulled from the three
teacher sites (sandbox network can't reach sites.google.com, so this
verifies the regex/parsing logic directly instead of the HTTP calls)."""

import scraper

LA_SAMPLE = """The most recent assignment will be posted at the TOP of this page.
9/1 Bring a charged device for NWEA Wednesday-Friday.
8/27 Revisit the story and mark the unfamiliar words and confusing moments for Friday. Presentations continue Friday.
8/25 A&P second read plus annotations due Wednesday.
8/24 Bring IR book Thursday.
8/18 Philosophy Presentations begin Monday.
8/17 Signed Course Outline due Tuesday. Donate tissue to the class. Bring IR book Thursday*."""

SCI_SAMPLE = """Homework is discussed in class, and rarely due the next day. Please pay attention to due dates listed below.
Week #4
Monday, 8-31-26
Observation/Inference -See Google Classroom for the directions
Complete in your science notebook
Due: 9-4-26
Week #3
Tuesday, 8-25-26
Mole Reading
Due: 8-26-26
Thursday, 8-27-26
Nature of Science Cover Page in Notebook
Due: 9-1-26
Week #1 & 2
Thursday, August 13, 2026
-"All About Me" Paper
Due: Thursday, August 20, 2026
Thursday, August 13, 2026
-Composition Notebook
Thursday, August 20, 2026
Friday, August 14, 2026
-Signed Green Sheet from Course syllabus
Due: Friday, August 21, 2026
Tuesday, August 18, 2026
-Signed Safety Contract
Due: Monday, August 24, 2026"""


def test_language_arts():
    print("=== Language Arts ===")
    entries = []
    for line in LA_SAMPLE.split("\n"):
        m = scraper.LA_LINE.match(line.strip())
        if not m:
            continue
        month, day, desc = m.groups()
        posted = scraper._safe_parse_date(f"{month}/{day}/{scraper.CURRENT_YEAR}")
        entries.append({"posted": posted, "text": desc.strip()})
    for e in entries:
        print(e)
    assert len(entries) == 6
    assert entries[0]["posted"] == "2026-09-01"
    print("OK -", len(entries), "entries parsed\n")


def test_science():
    print("=== Science ===")
    lines = [ln.strip() for ln in SCI_SAMPLE.split("\n") if ln.strip()]
    current = None
    entries = []
    for line in lines:
        if scraper.SCI_WEEK_HEADER.match(line):
            continue
        header_match = scraper.SCI_DATE_HEADER.match(line)
        due_match = scraper.SCI_DUE.match(line)
        if header_match:
            if current and current["text"]:
                entries.append(current)
            posted = scraper._safe_parse_date(header_match.group(2))
            current = {"date": None, "posted": posted, "text": ""}
        elif due_match and current is not None:
            current["date"] = scraper._safe_parse_date(due_match.group(1)) or current["date"]
        elif current is not None:
            current["text"] = (current["text"] + " " + line).strip() if current["text"] else line
    if current and current["text"]:
        entries.append(current)
    for e in entries:
        print(e)
    assert len(entries) == 7
    assert entries[0]["posted"] == "2026-08-31"
    assert entries[0]["date"] == "2026-09-04"
    print("OK -", len(entries), "entries parsed\n")


if __name__ == "__main__":
    test_language_arts()
    test_science()
    print("All parser tests passed.")
