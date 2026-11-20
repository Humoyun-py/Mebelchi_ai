"""PDF and Excel exports. Every export carries a professional-review notice."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NOTICE = "FOR PROFESSIONAL REVIEW - not verified for manufacture. Check dimensions, grain, hardware and machine limits before cutting."
HEAD = ["#", "Part", "Width (mm)", "Height (mm)", "Thick. (mm)", "Qty", "Material", "Edge banding"]


def _rows(cl):
    return [[i, p.name, float(p.width), float(p.height), float(p.thickness), p.quantity, p.material, p.edge_note or "-"]
            for i, p in enumerate(cl.parts.all(), 1)]


def to_xlsx(cl, run=None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cutting list"
    ws.append([f"MEBELCHI AI - {cl.name}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([NOTICE])
    ws["A2"].font = Font(italic=True, color="B45309")
    ws.append([])
    ws.append(HEAD)
    fill = PatternFill("solid", fgColor="2563EB")
    for c in ws[4]:
        c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), fill, Alignment(horizontal="center")
    for r in _rows(cl):
        ws.append(r)
    n = ws.max_row
    ws.append(["", "TOTAL pieces", "", "", "", f"=SUM(F5:F{n})"])
    ws.append(["", "TOTAL area (m2)", "", "", "", f"=SUMPRODUCT(C5:C{n},D5:D{n},F5:F{n})/1000000"])
    for c in ws[ws.max_row - 1]:
        c.font = Font(bold=True)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for i, w in enumerate([5, 24, 12, 12, 12, 7, 12, 28], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if run:
        s = wb.create_sheet("Optimization")
        s.append(["Material group", "Sheets", "Sheet size (mm)", "Utilization %", "Waste %", "Est. cost"])
        for c in s[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), fill
        for g in run.result["groups"]:
            r = g["result"]
            s.append([g["key"], r["summary"]["sheet_count"], f'{r["sheet"]["length"]} x {r["sheet"]["width"]}',
                      r["summary"]["utilization_pct"], r["summary"]["waste_pct"], g["estimated_cost"] if g["estimated_cost"] is not None else "n/a"])
        t = run.result["summary"]
        s.append([])
        s.append(["TOTAL", t["sheet_count"], "", t["utilization_pct"], t["waste_pct"], t["estimated_cost"] if t["estimated_cost"] is not None else "n/a"])
        for c in s[s.max_row]:
            c.font = Font(bold=True)
        for i, w in enumerate([24, 9, 18, 14, 10, 12], 1):
            s.column_dimensions[get_column_letter(i)].width = w
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sheet_drawing(sheet: dict, layout: dict, max_w: float, max_h: float) -> Drawing:
    sl, sw = sheet["length"], sheet["width"]
    k = min(max_w / sl, max_h / sw)
    d = Drawing(sl * k, sw * k)
    d.add(Rect(0, 0, sl * k, sw * k, fillColor=colors.HexColor("#f1f5f9"), strokeColor=colors.HexColor("#334155")))
    palette = ["#bfdbfe", "#bbf7d0", "#fde68a", "#fecaca", "#ddd6fe", "#fed7aa", "#a5f3fc"]
    names: dict[str, str] = {}
    for pl in layout["placements"]:
        col = names.setdefault(pl["name"], palette[len(names) % len(palette)])
        x, y = (sheet["trim"] + pl["x"]) * k, (sheet["trim"] + pl["y"]) * k
        d.add(Rect(x, y, pl["w"] * k, pl["h"] * k, fillColor=colors.HexColor(col), strokeColor=colors.HexColor("#1e293b"), strokeWidth=0.4))
        if pl["w"] * k > 40 and pl["h"] * k > 9:
            d.add(String(x + 2, y + pl["h"] * k / 2 - 2, f'{pl["name"][:14]} {pl["w"]:g}x{pl["h"]:g}', fontSize=5.5))
    return d


def to_pdf(cl, run=None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm,
                            title=f"Cutting list - {cl.name}", author="MEBELCHI AI")
    st = getSampleStyleSheet()
    warn = st["Normal"].clone("warn", textColor=colors.HexColor("#b45309"), fontSize=8)
    el = [Paragraph(f"MEBELCHI AI - Cutting list: {cl.name}", st["Title"]), Paragraph(NOTICE, warn), Spacer(1, 6 * mm)]
    data = [HEAD] + _rows(cl)
    t = Table(data, repeatRows=1, colWidths=[10 * mm, 55 * mm, 26 * mm, 26 * mm, 24 * mm, 14 * mm, 28 * mm, 60 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563EB")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#94a3b8")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                           ("ALIGN", (2, 1), (5, -1), "RIGHT")]))
    el.append(t)
    parts = list(cl.parts.all())
    area = sum(float(p.width) * float(p.height) * p.quantity for p in parts) / 1e6
    el += [Spacer(1, 4 * mm), Paragraph(f"Total pieces: {sum(p.quantity for p in parts)} &nbsp;&nbsp; Total area: {area:.3f} m2", st["Normal"])]
    if run:
        s = run.result["summary"]
        el += [PageBreak(), Paragraph("Material optimization", st["Heading2"]),
               Paragraph(f'Sheets: {s["sheet_count"]} &nbsp; Utilization: {s["utilization_pct"]}% &nbsp; Waste: {s["waste_pct"]}% &nbsp; '
                         f'Estimated cost: {s["estimated_cost"] if s["estimated_cost"] is not None else "n/a (no sheet price set)"}', st["Normal"])]
        for g in run.result["groups"]:
            r = g["result"]
            for sh in r["sheets"]:
                el += [Spacer(1, 3 * mm), Paragraph(f'{g["key"]} - sheet {sh["index"]} of {r["summary"]["sheet_count"]} '
                                                    f'({r["sheet"]["length"]} x {r["sheet"]["width"]} mm) - used {sh["utilization_pct"]}%', st["Normal"]),
                       _sheet_drawing(r["sheet"], sh, 255 * mm, 120 * mm)]
        if run.result["unplaced"]:
            el += [Spacer(1, 3 * mm), Paragraph("UNPLACED (larger than sheet): " + ", ".join(u["name"] for u in run.result["unplaced"]), warn)]

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#b45309"))
        canvas.drawString(14 * mm, 8 * mm, "MEBELCHI AI - for professional review, not verified for manufacture")
        canvas.drawRightString(landscape(A4)[0] - 14 * mm, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
