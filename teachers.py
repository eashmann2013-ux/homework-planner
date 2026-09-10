"""
teachers.py
The list of teachers the planner knows about, grouped by subject. Each
entry says which page to read and which parsing strategy to use on it
(see scraper.py for what each parser does).

To add a teacher: add an entry here with a unique id, then make sure a
parser exists in scraper.py that matches how their page is formatted.
"""

TEACHERS = [
    {
        "id": "larcher-geometry",
        "name": "Ms. Larcher",
        "course": "Accelerated Math (Geometry)",
        "subject": "math",
        "url": "https://sites.google.com/cusdk8.org/mslarcher/ccgeometry/ccgeometry-first-semester",
        "parser": "google_doc_table",
    },
    {
        "id": "villagec-math8",
        "name": "Mr. Kampp & Mrs. Hsu",
        "course": "Math 8 (Village C)",
        "subject": "math",
        "url": "https://sites.google.com/cusdk8.org/kennedy-village-c-2021/mrs-mcgrath/math-8",
        "parser": "classwork_homework_log",
    },
    {
        "id": "dalvand-science",
        "name": "Ms. Dalvand",
        "course": "8th Grade Science",
        "subject": "science",
        "url": "https://sites.google.com/cusdk8.org/8th-grade-science-dalvand/homework",
        "parser": "weekday_due",
    },
    {
        "id": "greene-la",
        "name": "Mr. Greene",
        "course": "Language Arts",
        "subject": "language_arts",
        "url": "https://sites.google.com/a/cusdk8.org/mr-greene-s-language-arts-class/home/home-work",
        "parser": "date_prefix_line",
    },
]


def by_id(teacher_id):
    return next((t for t in TEACHERS if t["id"] == teacher_id), None)


def by_subject(subject):
    return [t for t in TEACHERS if t["subject"] == subject]


def all_grouped():
    return {
        "math": by_subject("math"),
        "science": by_subject("science"),
        "language_arts": by_subject("language_arts"),
    }
