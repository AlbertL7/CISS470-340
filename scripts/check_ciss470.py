#!/usr/bin/env python3
"""Fast, dependency-free structural checks for the public CISS 470 pages.

Run: python3 scripts/check_ciss470.py
Checks every CISS 470 page (Antonucci chapters 1-9 and the standards pages) for:
  - basic document hygiene (lang, title, viewport, single h1, unique ids)
  - inline handlers that call functions the page does not define
  - getElementById / querySelector('#...') targets that do not exist
  - checkAnswer quizzes with zero or more than one option keyed correct
  - broken internal links and a few copy regressions
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = [ROOT / f"chapter{number}.html" for number in range(1, 10)]
STANDARDS = [
    ROOT / name
    for name in (
        "fips199.html",
        "fips200.html",
        "nist800-53.html",
        "nist800-70.html",
        "nist800-60.html",
        "nist800-30r1.html",
        "governance-framework.html",
        "cobit.html",
        "core-components.html",
    )
]
PAGES = [ROOT / "index.html", *CHAPTERS, *STANDARDS]

EXPECTED_CHAPTER_TITLES = {
    "chapter1.html": "Introduction",
    "chapter2.html": "Board Cyber Risk Oversight",
    "chapter3.html": "Principles Behind Cyber Risk Management",
    "chapter4.html": "Cybersecurity Policies and Procedures",
    "chapter5.html": "Cyber Strategic Performance Management",
    "chapter6.html": "Standards and Frameworks for Cybersecurity",
    "chapter7.html": "Identifying, Analyzing, and Evaluating Cyber Risks",
    "chapter8.html": "Treating Cyber Risks",
    "chapter9.html": "Treating Cyber Risks Using Process Capabilities",
}

# Pages whose quizzes are expected; each must keep at least this many keyed questions.
MIN_QUIZ_QUESTIONS = {
    "chapter1.html": 5,
    "chapter2.html": 5,
    "chapter3.html": 5,
    "chapter4.html": 3,
    "chapter5.html": 3,
    "chapter6.html": 4,
    "chapter7.html": 4,
    "chapter8.html": 4,
    "chapter9.html": 4,
    "nist800-70.html": 5,
    "core-components.html": 3,
}
# cobit.html keys its 10-question quiz through selectOption()/checkAnswer(id) rather than per-option flags.

REGRESSION_GUARDS = {
    "index.html": {
        "forbidden": ("Remidiate", "Frameworks into context"),
        "required": ('id="ciss470"', "chapter9.html", "nist800-30r1.html", "core-components.html"),
    },
    "nist800-53.html": {
        "forbidden": ("function showBaseline(",),
        "required": ("detailed-baseline-display",),
    },
    "chapter6.html": {"forbidden": (), "required": ('id="knowledge-check"', "function checkAnswer")},
    "chapter7.html": {"forbidden": (), "required": ('id="knowledge-check"', "function checkAnswer", "IRAM2")},
    "chapter8.html": {"forbidden": (), "required": ('id="knowledge-check"', "function checkAnswer", "risk appetite")},
    "chapter9.html": {"forbidden": (), "required": ('id="knowledge-check"', "function checkAnswer", "EDM")},
}

BANNED_COPY = ("Remidiate", "Retreive", "Summerize", "Lorem ipsum", "TODO:")
JS_GLOBALS = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "function",
    "event", "alert", "confirm", "prompt", "window", "document", "location", "this", "parseInt",
    "parseFloat", "setTimeout", "clearTimeout", "console", "history", "print", "open", "close",
    "stopPropagation", "preventDefault", "Number", "String", "Math", "JSON", "Date",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []
        self.handlers: list[str] = []
        self.h1_count = 0
        self.has_title = False
        self.has_viewport = False
        self.html_lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        if tag == "meta" and (values.get("name") or "").lower() == "viewport":
            self.has_viewport = True
        if tag == "h1":
            self.h1_count += 1
        if tag == "title":
            self.has_title = True
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        for name, value in attrs:
            if name.startswith("on") and value:
                self.handlers.append(value)


def local_target(href: str) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    route = parsed.path
    if not route or route == "/":
        return ROOT / "index.html"
    if route.startswith("/"):
        route = route[1:]
    candidate = ROOT / route
    return candidate if candidate.suffix else candidate.with_suffix(".html")


def scripts_of(text: str) -> str:
    return "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", text, re.S))


def defined_functions(script: str) -> set[str]:
    names = set(re.findall(r"function\s+([A-Za-z_]\w*)\s*\(", script))
    names |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_]\w*)\s*=>", script))
    names |= set(re.findall(r"window\.([A-Za-z_]\w*)\s*=", script))
    return names


def called_functions(handlers: list[str]) -> set[str]:
    calls: set[str] = set()
    for handler in handlers:
        for match in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*\(", handler):
            calls.add(match.group(1))
    return calls


def quiz_keys(text: str) -> dict[str, int]:
    """Map quiz id -> number of options keyed correct.

    Handles checkAnswer(this, true|false, 'id') and, for pages that key options with a
    string instead, checkAnswer(this, 'correct'|'incorrect', ...), where each 'correct'
    option is treated as its own question.
    """
    keys: dict[str, int] = {}
    for is_correct, quiz_id in re.findall(r"checkAnswer\(\s*this\s*,\s*(true|false)\s*,\s*['\"]([^'\"]+)['\"]", text):
        keys.setdefault(quiz_id, 0)
        if is_correct == "true":
            keys[quiz_id] += 1
    for index, _ in enumerate(re.findall(r"checkAnswer\(\s*this\s*,\s*['\"]correct['\"]", text)):
        keys[f"string-keyed-{index + 1}"] = 1
    return keys


def js_syntax_errors(label: str, script: str) -> list[str]:
    """Run each page's inline JavaScript through `node --check` when Node is available."""
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node or not script.strip():
        return []
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        temp_path = handle.name
    try:
        result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True, timeout=30)
    finally:
        Path(temp_path).unlink(missing_ok=True)
    if result.returncode == 0:
        return []
    first_line = (result.stderr.strip().splitlines() or ["syntax error"])[-1]
    return [f"{label}: inline JavaScript does not parse ({first_line[:160]})"]


def main() -> int:
    import sys

    errors: list[str] = []
    selected = set(sys.argv[1:])
    pages = [page for page in PAGES if not selected or page.name in selected]

    for page in pages:
        label = page.name
        if not page.is_file():
            errors.append(f"missing required page: {label}")
            continue
        text = page.read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)
        script = scripts_of(text)

        if parser.html_lang.lower() != "en":
            errors.append(f"{label}: missing lang=en")
        if not parser.has_title:
            errors.append(f"{label}: missing title")
        if not parser.has_viewport:
            errors.append(f"{label}: missing viewport meta")
        expected_h1 = 2 if label == "index.html" else 1  # the portal has one h1 per course tab
        if parser.h1_count != expected_h1:
            errors.append(f"{label}: expected {expected_h1} h1 element(s), found {parser.h1_count}")
        duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
        if duplicates:
            errors.append(f"{label}: duplicate ids {duplicates}")

        for typo in BANNED_COPY:
            if typo in text:
                errors.append(f"{label}: contains banned copy {typo!r}")

        # House style: no em-dashes or en-dashes in student-facing CISS 470 copy.
        dash_scope = text[: text.find('id="ciss340"')] if label == "index.html" else text
        for dash, name in (("—", "em-dash"), ("–", "en-dash")):
            if dash in dash_scope:
                errors.append(f"{label}: contains {name} ({dash_scope.count(dash)}x); use a comma, period, or hyphen")

        if label in EXPECTED_CHAPTER_TITLES and EXPECTED_CHAPTER_TITLES[label] not in text:
            errors.append(f"{label}: missing chapter title {EXPECTED_CHAPTER_TITLES[label]!r}")

        errors.extend(js_syntax_errors(label, script))

        defined = defined_functions(script)
        for name in sorted(called_functions(parser.handlers)):
            if name not in defined and name not in JS_GLOBALS:
                errors.append(f"{label}: handler calls undefined function {name}()")

        ids = set(parser.ids)
        referenced = set(re.findall(r"getElementById\(\s*['\"]([^'\"$`+]+)['\"]\s*\)", script))
        referenced |= set(re.findall(r"querySelector\(\s*['\"]#([^'\"\s.>$`+]+)['\"]\s*\)", script))
        for target in sorted(referenced):
            if target not in ids:
                errors.append(f"{label}: script references missing element id {target!r}")

        keys = quiz_keys(text)
        for quiz_id, correct in sorted(keys.items()):
            if correct != 1:
                errors.append(f"{label}: quiz {quiz_id!r} has {correct} options keyed correct")
        minimum = MIN_QUIZ_QUESTIONS.get(label)
        if minimum and len(keys) < minimum:
            errors.append(f"{label}: expected at least {minimum} keyed quiz questions, found {len(keys)}")

        guards = REGRESSION_GUARDS.get(label, {})
        for phrase in guards.get("forbidden", ()):
            if phrase in text:
                errors.append(f"{label}: contains forbidden regression phrase {phrase!r}")
        for phrase in guards.get("required", ()):
            if phrase not in text:
                errors.append(f"{label}: missing required phrase {phrase!r}")

        for href in parser.links:
            target = local_target(href)
            if target is not None and not target.exists():
                errors.append(f"{label}: broken internal link {href!r}")

    if errors:
        print("CISS 470 smoke checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"CISS 470 smoke checks passed for {len(pages)} pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
