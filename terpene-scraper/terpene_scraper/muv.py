"""MUV (Verano) Florida: Sweed-powered menu rendered server-side on muvfl.com.

NOTE: muvfl.com/robots.txt has `Disallow: /*?*` for all crawlers. Pagination of the menu uses `?page=N`,
so only page 1 (no query string) may be fetched. The PoliteSession enforces robots.txt on every request,
so pages 2+ are refused and reported in the summary instead of fetched.
"""
import re
from datetime import date

from bs4 import BeautifulSoup

from .http import RobotsDisallowed

BASE = "https://muvfl.com"
STORE_SLUG = "lady-lake"  # nearest MUV store to ZIP 32162 (The Villages); 929 US-441 Hwy Ste 202, Lady Lake, FL 32159
STORE_LOCATION = "Lady Lake - 929 US-441 Hwy Ste 202, Lady Lake, FL 32159"
FLOWER_PATH = f"/locations/{STORE_SLUG}/menu/menu/flower-3485"
NUM = re.compile(r"(\d+(?:\.\d+)?)")


def _range_max(text):
    nums = [float(n) for n in NUM.findall(text or "")]
    return max(nums) if nums else None


def _money(text):
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", text or "")
    return float(m.group(1).replace(",", "")) if m else None


def _parse_card(card, today):
    link = card.select_one('[data-testid="product-card-title-link"]') or card.select_one("a[href*='/flower-']")
    if not link:
        return None
    text = card.get_text("|", strip=True)
    name = link.get_text(strip=True)
    href = link["href"]
    thc = re.search(r"THC\W*\|?\W*:\W*\|?([\d.\s\-]+)%", text)
    terp = re.search(r"TERP\w*\W*:\W*\|?([\d.\s\-]+)%", text)
    terp_txt = terp.group(1).strip() if terp else ""
    # Strain type + brand: chips before the title; "by | Brand" appears just before the name.
    strain = ""
    for t in ("Indica", "Sativa", "Hybrid"):
        if re.search(rf"\b{t}\b", text.split(name)[0]):
            strain = t
            break
    brand = ""
    m = re.search(r"\|by\|([^|]+)\|" + re.escape(name), text)
    if m:
        brand = m.group(1).strip()
    # Weight: the bold chip is the selected size; fall back to the URL slug.
    weight = ""
    for sp in card.select("span"):
        cls = " ".join(sp.get("class", []))
        if "font-extrabold" in cls and re.fullmatch(r"[\d./]+\s?(g|oz|mg)", sp.get_text(strip=True)):
            weight = sp.get_text(strip=True)
            break
    if not weight:
        m = re.search(r"-([\d.]+g)-\d+$", href) or re.search(r"-([\d.]+g)-", href)
        weight = m.group(1) if m else ""
    cur = card.find(string=re.compile("Currently"))
    cur_p = _money(cur.parent.parent.get_text("", strip=True)) if cur else None
    old = card.find(string=re.compile("Formerly"))
    old_p = _money(old.parent.parent.get_text("", strip=True)) if old else None
    if cur_p is None:
        cur_p = _money(text)
    price, sale = (old_p, cur_p) if old_p and cur_p and cur_p < old_p else (cur_p, None)
    return {
        "dispensary": "MUV", "store_location": STORE_LOCATION, "brand": brand, "product_name": name,
        "subcategory": "", "strain_type": strain, "weight": weight, "price": price, "sale_price": sale,
        "thc_pct": _range_max(thc.group(1)) if thc else None,
        "terpene_pct": _range_max(terp_txt), "in_stock": True,
        "url": BASE + href, "date_collected": today,
    }, bool(terp_txt)


def collect(sess):
    today = date.today().isoformat()
    rows, skipped, notes = [], 0, []
    r = sess.request("GET", BASE + FLOWER_PATH)
    soup = BeautifulSoup(r.text, "lxml")
    for card in soup.select('[data-testid="product-card"]'):
        parsed = _parse_card(card, today)
        if not parsed:
            continue
        row, has_terp = parsed
        if not has_terp or not row["terpene_pct"]:
            skipped += 1
        else:
            rows.append(row)
    pages = [int(m) for m in re.findall(r'aria-label="Page \d+ of (\d+)"', r.text)]
    total_pages = max(pages) if pages else 1
    if total_pages > 1:
        nxt = f"{BASE}{FLOWER_PATH}?page=2"
        try:
            sess.request("GET", nxt)  # refused by robots check; if the site ever relaxes robots.txt this proceeds
            notes.append("robots.txt now allows ?page=; extend muv.collect to walk pages")
        except RobotsDisallowed:
            notes.append(f"muvfl.com robots.txt disallows '?page=' URLs; only page 1 of {total_pages} "
                         f"was collected (menu is incomplete).")
    return rows, skipped, notes
