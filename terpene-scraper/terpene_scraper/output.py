import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

COLUMNS = [
    ("dispensary", "Dispensary", 12), ("store_location", "Store location", 42), ("brand", "Brand", 18),
    ("product_name", "Product name", 38), ("subcategory", "Subcategory", 16), ("strain_type", "Strain type", 11),
    ("weight", "Weight", 8), ("price", "Price", 9), ("sale_price", "Sale price", 10), ("thc_pct", "THC %", 8),
    ("terpene_pct", "Total terpene %", 14), ("in_stock", "In stock", 9), ("url", "Product URL", 50),
    ("date_collected", "Date collected", 14),
]


def write_all(rows, out_dir: Path):
    rows = sorted(rows, key=lambda r: r["terpene_pct"], reverse=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "terpenes.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([c[1] for c in COLUMNS])
        for r in rows:
            w.writerow(["" if r[c[0]] is None else r[c[0]] for c in COLUMNS])
    wb = Workbook()
    ws = wb.active
    ws.title = "Terpenes"
    ws.append([c[1] for c in COLUMNS])
    for r in rows:
        ws.append([r[c[0]] for c in COLUMNS])
    for i, (key, _, width) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
        ws.cell(1, i).font = Font(bold=True)
        for cell in ws.iter_cols(min_col=i, max_col=i, min_row=2):
            for c in cell:
                if key in ("price", "sale_price"):
                    c.number_format = '"$"#,##0.00'
                elif key in ("thc_pct", "terpene_pct"):
                    c.number_format = "0.00"
    for r_idx, r in enumerate(rows, 2):
        ws.cell(r_idx, 13).hyperlink = r["url"]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions  # filter row on
    wb.save(out_dir / "terpenes.xlsx")
    return rows
