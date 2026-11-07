"""Collect FLOWER products from Trulieve and MUV (Florida, nearest store to ZIP 32162),
write terpenes.csv / terpenes.xlsx sorted by total terpene % (highest first).

Usage:  python run.py [--zip 32162] [--out .]
"""
import argparse
import sys
from pathlib import Path

from terpene_scraper import muv, trulieve
from terpene_scraper.http import PoliteSession
from terpene_scraper.output import write_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="32162", help="ZIP used to pick the nearest Trulieve store")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent), help="output directory")
    args = ap.parse_args()

    sess = PoliteSession()
    all_rows, report = [], []
    for name, fn in (("Trulieve", lambda: trulieve.collect(sess, args.zip)), ("MUV", lambda: muv.collect(sess))):
        print(f"Collecting {name} ...", flush=True)
        try:
            res = fn()
        except Exception as e:  # one site failing must not lose the other's data
            print(f"  FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            report.append((name, 0, 0, [f"failed: {e}"]))
            continue
        rows, skipped = res[0], res[1]
        notes = res[2] if isinstance(res[2], list) else [f"store: {res[2]}"]
        all_rows += rows
        report.append((name, len(rows), skipped, notes))

    if not all_rows:
        sys.exit("No products collected; nothing written.")
    rows = write_all(all_rows, Path(args.out))

    print("\n=== Summary ===")
    for name, n, skipped, notes in report:
        print(f"{name}: {n} products with terpene data, {skipped} skipped (no terpene %)")
        for note in notes:
            print(f"   note: {note}")
    print(f"Total: {len(rows)} rows -> {Path(args.out) / 'terpenes.csv'} and terpenes.xlsx\n")
    print("Top 10 by total terpene %:")
    for i, r in enumerate(rows[:10], 1):
        thc = f"{r['thc_pct']:g}%" if r["thc_pct"] is not None else "n/a"
        price = r["sale_price"] or r["price"]
        print(f"{i:>2}. {r['terpene_pct']:.2f}% terps | THC {thc} | {r['dispensary']} | "
              f"{r['brand']} - {r['product_name']} ({r['weight']}) | ${price}")


if __name__ == "__main__":
    main()
