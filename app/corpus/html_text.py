"""HTML helpers for Groww snapshot parsing (Phase 2.2)."""

from __future__ import annotations

import json
import re
import unicodedata
from html import unescape
from html.parser import HTMLParser

NON_GROWW_URL = re.compile(
    r"https?://(?:www\.)?(?!groww\.in)[\w.-]+\.[a-z]{2,}(?:/[^\s\"'<>]*)?",
    re.IGNORECASE,
)
WHITESPACE = re.compile(r"[ \t]+")
MULTI_NL = re.compile(r"\n{3,}")

SKIP_TAGS = frozenset({"script", "style", "noscript", "svg", "iframe", "canvas"})
CHROME_TAGS = frozenset({"nav", "footer", "header"})
CHROME_CLASS_HINTS = (
    "footer",
    "navbar",
    "cookie",
    "banner",
    "cta",
    "investnow",
    "downloadapp",
    "bottomnav",
)
BOILERPLATE_LINE = (
    "download the app",
    "invest now",
    "start sip",
    "start investing",
    "was the answer helpful",
    "all rights reserved",
    "vaishnavi tech park",
    "open demat",
    "groww terminal",
    "get the app",
    "continue with google",
    "by continuing, you agree",
    "trust & safety",
    "investor relations",
)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_stack: list[bool] = []
        self.parts: list[str] = []

    def _skipping(self) -> bool:
        return any(self._skip_stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        skip = tag in SKIP_TAGS or tag in CHROME_TAGS or _chrome_attrs(attrs)
        self._skip_stack.append(skip)
        if skip:
            return
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack:
            self._skip_stack.pop()
        if tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "tr"} and not self._skipping():
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skipping():
            return
        text = unescape(data)
        if text.strip():
            self.parts.append(text)


def _chrome_attrs(attrs: list[tuple[str, str | None]]) -> bool:
    classes = " ".join(value or "" for key, value in attrs if key == "class").lower()
    return any(hint in classes.replace("-", "").replace("_", "") or hint in classes for hint in CHROME_CLASS_HINTS)


def extract_next_data(html: str) -> dict | None:
    marker = 'id="__NEXT_DATA__"'
    start = html.find(marker)
    if start < 0:
        return None
    gt = html.find(">", start)
    end = html.find("</script>", gt)
    if gt < 0 or end < 0:
        return None
    try:
        return json.loads(html[gt + 1 : end])
    except json.JSONDecodeError:
        return None


def html_to_text(html: str) -> str:
    parser = VisibleTextParser()
    parser.feed(html)
    parser.close()
    return normalize_text("".join(parser.parts))


def strip_non_groww_urls(text: str) -> str:
    return NON_GROWW_URL.sub("", text)


def drop_boilerplate_lines(text: str) -> str:
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            kept.append("")
            continue
        lower = line.lower()
        if any(token in lower for token in BOILERPLATE_LINE):
            continue
        if len(line) <= 2:
            continue
        kept.append(line)
    return "\n".join(kept)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = unescape(text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = strip_non_groww_urls(text)
    text = WHITESPACE.sub(" ", text)
    text = drop_boilerplate_lines(text)
    text = MULTI_NL.sub("\n\n", text)
    return text.strip()
