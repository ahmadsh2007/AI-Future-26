"""Load + clean the 12 service files and split them into the 9 official fields.
Cleaning never changes facts: it only drops website menu lines, tabs, blank/duplicate lines."""
import re
from pathlib import Path

from text_utils import clean_text

DATA_DIR = Path(__file__).resolve().parent / "data"

DOCS = {"passport": "جواز السفر", "family_book": "دفتر العائلة", "id_card": "البطاقة الذكية"}
SITUATIONS = {"first_issue": "لأول مرة", "renewal": "تجديد", "lost": "بدل فاقد", "damaged": "بدل تالف"}

# canonical field name -> regex of the label at the start of a line
FIELDS = {
    "الفئة المستفيدة": r"الفئة المستفيدة",
    "أماكن تقديم الخدمة": r"أماكن تقديم الخدمة",
    "شروط تقديم الخدمة": r"شروط تقديم الخدمة",
    "الوثائق المطلوبة": r"الوثائق المطلوبة(?: للحصول على الخدمة)?",
    "إجراءات تقديم الخدمة": r"إجراءات تقديم الخدمة",
    "الزمن المستغرق": r"الزمن المستغرق(?: لتقديم الخدمة)?",
    "شركاء الخدمة": r"شركاء الخدمة",
    "ملاحظات": r"ملاحظات",
    "الرسوم": r"الرسوم",
}
_LABEL_RE = re.compile(r"^(?:%s)\b" % "|".join(f"(?P<f{i}>{p})" for i, p in enumerate(FIELDS.values())))
_MENU = {"الرئيسية", "الخدمات", "دليل الخدمات", "شارك"}
_FIELD_NAMES = list(FIELDS)


def service_title(doc: str, situation: str) -> str:
    d = DOCS[doc]
    return {"first_issue": f"{d} لأول مرة", "renewal": f"تجديد {d}",
            "lost": f"{d} بدل فاقد", "damaged": f"{d} بدل تالف"}[situation]


def parse_service(path: Path) -> dict:
    doc, situation = None, None
    stem = path.stem
    for d in DOCS:
        if stem.startswith(d + "_"):
            doc, situation = d, stem[len(d) + 1:]
    assert doc and situation in SITUATIONS, f"unexpected file name {path.name}"

    lines = []
    for raw in clean_text(path.read_text(encoding="utf-8-sig")).splitlines():
        line = re.sub(r"\s+", " ", raw.replace("\t", " ")).strip()
        if line and line not in _MENU:
            lines.append(line)

    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        m = _LABEL_RE.match(line)
        if m:
            idx = int(m.lastgroup[1:])
            current = _FIELD_NAMES[idx]
            rest = line[m.end():].strip()
            sections.setdefault(current, [])
            if rest:
                sections[current].append(rest)
        elif current:
            if line not in sections[current]:  # drop exact duplicate lines
                sections[current].append(line)
        # lines before the first label are the page title / breadcrumb

    return {"id": stem, "doc": doc, "situation": situation, "title": service_title(doc, situation),
            "sections": {k: "\n".join(v) for k, v in sections.items()}}


def load_services(data_dir: Path = DATA_DIR) -> dict[str, dict]:
    services = {}
    for p in sorted(Path(data_dir).glob("*.txt")):
        s = parse_service(p)
        services[s["id"]] = s
    return services


def section_context(service: dict, field: str) -> str:
    """The text we hand to the LLM and return as `contexts` (same format as the brief's example)."""
    return f"{service['title']} - {field}: {service['sections'][field]}"


if __name__ == "__main__":
    for s in load_services().values():
        miss = [f for f in FIELDS if f not in s["sections"]]
        print(f"{s['id']:<26} {len(s['sections'])}/9 fields  missing={miss}")
