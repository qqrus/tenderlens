"""Narrow bilingual intent matching for explicitly labelled procurement-plan fields."""

# ruff: noqa: RUF001  # Bilingual expressions intentionally contain Cyrillic.
import re

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = (
    rf"(?:{MONTH}\s+(?:\d{{1,2}},?\s+)?\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|\d{{2}}\.\d{{2}}\.\d{{4}})"
)
FIELDS = {
    "period": re.compile(
        rf"^[ \t]*(?:Period\s+covered\s+by\s+(?:this\s+)?Procurement\s+Plan|"
        rf"Период\s+плана\s+закупок)[ \t]*:[ \t]*\n?[ \t]*"
        rf"(?P<value>{DATE}\s*(?:–|—|-|to|по)\s*{DATE})[ \t]*\.?[ \t]*(?=\n|$)",
        re.I | re.M,
    ),
    "agreement": re.compile(
        rf"^[ \t]*(?:Procurement\s+Plan\s+agreed\s+as\s+of|"
        rf"План\s+закупок\s+согласован)[ \t]*:?[ \t]*\n?[ \t]*"
        rf"(?P<value>{DATE})[ \t]*\.?[ \t]*(?=\n|$)",
        re.I | re.M,
    ),
}


def plan_intent(question: str) -> str | None:
    if not re.search(r"план\w*.*закуп|procurement\s+plan", question, re.I):
        return None
    if re.search(r"период|period.*cover|cover.*period", question, re.I):
        return "period"
    if re.search(r"согласован|agreed|agreement", question, re.I):
        return "agreement"
    return None


def field_spans(question: str, source: str) -> list[tuple[int, int]]:
    intent = plan_intent(question)
    if intent is None:
        return []
    return [(match.start(), match.end()) for match in FIELDS[intent].finditer(source)]


def field_value(question: str, source: str) -> str:
    intent = plan_intent(question)
    match = FIELDS[intent].search(source) if intent else None
    return " ".join(match.group("value").casefold().split()) if match else ""
