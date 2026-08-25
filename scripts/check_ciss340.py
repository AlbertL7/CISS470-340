#!/usr/bin/env python3
"""Fast, dependency-free structural checks for the public CISS 340 pages."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ROOT / "index.html",
    *(ROOT / f"ciss340-chapter{number}.html" for number in range(1, 12)),
    ROOT / "MySQL-Workbench.html",
    ROOT / "ShopFlow-Project.html",
    ROOT / "ciss340" / "index.html",
    ROOT / "404.html",
]

EXPECTED_CHAPTER_TITLES = {
    "ciss340-chapter1.html": "An introduction to relational databases",
    "ciss340-chapter2.html": "How to use MySQL Workbench and other development tools",
    "ciss340-chapter3.html": "How to retrieve data from a single table",
    "ciss340-chapter4.html": "How to retrieve data from two or more tables",
    "ciss340-chapter5.html": "How to insert, update, and delete data",
    "ciss340-chapter6.html": "How to code summary queries",
    "ciss340-chapter7.html": "How to code subqueries",
    "ciss340-chapter8.html": "How to work with data types",
    "ciss340-chapter9.html": "How to use functions",
    "ciss340-chapter10.html": "How to design a database",
    "ciss340-chapter11.html": "How to create databases, tables, and indexes",
}

REGRESSION_GUARDS = {
    "ciss340-chapter1.html": {
        "forbidden": ("only one NULL", "only once"),
        "required": ("can contain multiple NULL values",),
    },
    "ciss340-chapter2.html": {
        "forbidden": ("correctAnswers * 5", "Qcache_hits"),
        "required": ("correctAnswers / questions.length", "Cumulative Practice Quiz"),
    },
    "ciss340-chapter3.html": {
        "forbidden": ("PostgreSQL || treats NULL", "avoid IN with nullable"),
        "required": ("NOT IN with NULL Values",),
    },
    "ciss340-chapter5.html": {
        "forbidden": ("VALUES(last_name)", "TRUNCATE (not logged"),
        "required": ("first generated ID", "implicit commit; cannot be rolled back"),
    },
    "ciss340-chapter6.html": {
        "forbidden": ("PERCENTILE_CONT", "0.6745", "price_variance"),
        "required": ("price_stddev", "SUM returns NULL"),
    },
    "ciss340-chapter7.html": {
        "forbidden": ("subqueries are always slower", "LIMIT 1 fixes"),
        "required": ("NOT EXISTS", "One-value subqueries", "WITH RECURSIVE"),
    },
    "ciss340-chapter8.html": {
        "forbidden": ("FORMAT() returns a number",),
        "required": ("DECIMAL", "VARCHAR", "FLOAT(M,D)", "deprecated", "implicit conversion"),
    },
    "ciss340-chapter9.html": {
        "forbidden": ("LENGTH returns characters", "CONCAT skips NULL"),
        "required": ("CHAR_LENGTH", "CONCAT_WS", "DENSE_RANK"),
    },
    "ciss340-chapter10.html": {
        "forbidden": ("crow’s foot means zero or more", "crow's foot means zero or more"),
        "required": ("One row represents", "child/many side", "third normal form"),
    },
    "ciss340-chapter11.html": {
        "forbidden": ("SET foreign_key_checks = 0", "utf8mb3 is recommended"),
        "required": ("ap_sandbox", "SHOW CREATE TABLE", "utf8mb4"),
    },
    "MySQL-Workbench.html": {
        "forbidden": ("Solid line 1:n (Identifying)", "clicking parent first, then child"),
        "required": ("CHILD/many table first", "Place a Relationship Using Existing Columns"),
    },
    "index.html": {
        "forbidden": (),
        "required": (
            "13 + quiz",
            "19 + quiz",
            "#ciss340",
            "ShopFlow-Project.html",
            "ciss340-chapter7.html",
            "ciss340-chapter8.html",
            "ciss340-chapter9.html",
            "ciss340-chapter10.html",
            "ciss340-chapter11.html",
        ),
    },
    "ShopFlow-Project.html": {
        "forbidden": (
            "real business data",
            "real-world data",
            "free trial",
            "Digital Ocean",
            "defaultdb",
            "750-word",
            "publicly access your database",
        ),
        "required": (
            "realistic, instructor-provided fictional data",
            "MySQL 8.4 LTS",
            "shopflow_reader",
            "AI may produce drafts, but students must test, correct, document, and explain every submitted result.",
            "The ten required business queries",
            "Required project total",
        ),
    },
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []
        self.has_h1 = False
        self.has_title = False
        self.has_viewport = False
        self.html_lang = ""
        self.main_count = 0
        self.table_count = 0
        self.caption_count = 0
        self.th_without_scope = 0
        self.lesson_section_count = 0
        self.quick_check_count = 0
        self.has_skip_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        if tag == "meta" and values.get("name", "").lower() == "viewport":
            self.has_viewport = True
        if tag == "h1":
            self.has_h1 = True
        if tag == "main":
            self.main_count += 1
        if tag == "table":
            self.table_count += 1
        if tag == "caption":
            self.caption_count += 1
        if tag == "th" and values.get("scope") not in {"col", "row", "colgroup", "rowgroup"}:
            self.th_without_scope += 1
        if tag == "title":
            self.has_title = True
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        classes = set((values.get("class") or "").split())
        if tag == "section" and "lesson-section" in classes:
            self.lesson_section_count += 1
        if "quick-check" in classes:
            self.quick_check_count += 1
        if tag == "a" and "skip-link" in classes and values.get("href") == "#main-content":
            self.has_skip_link = True


def local_target(href: str) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "tel:", "javascript:")):
        return None
    route = parsed.path
    if not route or route == "/":
        return ROOT / "index.html"
    if route == "/ciss340" or route == "/ciss340/":
        return ROOT / "ciss340" / "index.html"
    if route.startswith("/"):
        route = route[1:]
    candidate = ROOT / route
    if candidate.suffix:
        return candidate
    return candidate.with_suffix(".html")


def main() -> int:
    errors: list[str] = []
    banned_copy = ("Retreive", "Summerize", "orgainzise")

    for page in PAGES:
        if not page.is_file():
            errors.append(f"missing required page: {page.relative_to(ROOT)}")
            continue
        text = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)

        label = str(page.relative_to(ROOT))
        if parser.html_lang.lower() != "en":
            errors.append(f"{label}: missing lang=en")
        if not parser.has_title:
            errors.append(f"{label}: missing title")
        if not parser.has_viewport:
            errors.append(f"{label}: missing viewport meta")
        if not parser.has_h1:
            errors.append(f"{label}: missing h1")
        duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        if duplicates:
            errors.append(f"{label}: duplicate ids {duplicates}")
        for typo in banned_copy:
            if typo in text:
                errors.append(f"{label}: contains typo {typo!r}")
        if label in EXPECTED_CHAPTER_TITLES and EXPECTED_CHAPTER_TITLES[label] not in text:
            errors.append(f"{label}: missing official Murach chapter title")
        if label in {f"ciss340-chapter{number}.html" for number in range(7, 12)}:
            if parser.main_count != 1:
                errors.append(f"{label}: expected exactly one main landmark")
            if not parser.has_skip_link:
                errors.append(f"{label}: missing skip link to #main-content")
            if parser.lesson_section_count != 9:
                errors.append(f"{label}: expected 9 lesson sections, found {parser.lesson_section_count}")
            if parser.quick_check_count < 2:
                errors.append(f"{label}: expected at least 2 quick checks")
            if parser.table_count != parser.caption_count:
                errors.append(
                    f"{label}: every table needs a caption "
                    f"({parser.table_count} tables, {parser.caption_count} captions)"
                )
            if parser.th_without_scope:
                errors.append(f"{label}: {parser.th_without_scope} table headers lack scope")
        guards = REGRESSION_GUARDS.get(label, {})
        for phrase in guards.get("forbidden", ()):
            if phrase in text:
                errors.append(f"{label}: contains forbidden regression phrase {phrase!r}")
        for phrase in guards.get("required", ()):
            if phrase not in text:
                errors.append(f"{label}: missing required regression phrase {phrase!r}")
        for href in parser.links:
            target = local_target(href)
            if target is not None and not target.exists():
                errors.append(f"{label}: broken internal link {href!r}")

    if errors:
        print("CISS 340 smoke checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"CISS 340 smoke checks passed for {len(PAGES)} pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
