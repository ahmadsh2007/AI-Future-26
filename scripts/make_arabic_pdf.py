"""Generate a minimal Arabic PDF (fictional company) with visual-order shaped text, like real-world Arabic PDFs.
    python scripts/make_arabic_pdf.py [out.pdf]
"""
import sys
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONTS = ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"]

# Fictional facts so the LLM cannot know them from pretraining.
LINES = [
    "تقرير شركة الواحة للاستثمار السنوي",
    "تأسست شركة الواحة للاستثمار في مدينة إربد عام ١٩٩٨ على يد السيد خالد المنصور.",
    "بلغت أرباح الشركة خلال عام ٢٠٢٤ مبلغ ٤٥ مليون دينار أردني.",
    "يبلغ عدد موظفي الشركة ٣٢٠ موظفاً يعملون في ثلاثة فروع رئيسية.",
    "قررت الجمعية العمومية توزيع أرباح نقدية بنسبة ١٢ بالمئة على المساهمين.",
    "تخطط الشركة لافتتاح فرع جديد في مدينة العقبة خلال الربع الثالث من عام ٢٠٢٥.",
]


def make(out: Path):
    font = next((f for f in FONTS if Path(f).exists()), None)
    if not font:
        raise SystemExit("No Arabic-capable TTF font found; edit FONTS in this script.")
    pdfmetrics.registerFont(TTFont("AR", font))
    c = canvas.Canvas(str(out))
    c.setFont("AR", 14)
    y = 780
    for line in LINES:
        c.drawRightString(560, y, get_display(arabic_reshaper.reshape(line)))
        y -= 30
    c.save()
    return out


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/test_pdfs/oasis_report.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    print("wrote", make(out))
