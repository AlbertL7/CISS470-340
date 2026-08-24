#!/usr/bin/env python3
"""Fast, dependency-free structural checks for the public CISS 340 pages."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ROOT / "index.html",
    *(ROOT / f"ciss340-chapter{number}.html" for number in range(1, 7)),
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
    "MySQL-Workbench.html": {
        "forbidden": ("Solid line 1:n (Identifying)", "clicking parent first, then child"),
        "required": ("CHILD/many table first", "Place a Relationship Using Existing Columns"),
    },
    "index.html": {
        "forbidden": (),
        "required": ("13 + quiz", "19 + quiz", "#ciss340", "ShopFlow-Project.html"),
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        if tag == "meta" and values.get("name", "").lower() == "viewport":
            self.has_viewport = True
        if tag == "h1":
            self.has_h1 = True
        if tag == "title":
            self.has_title = True
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")


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
