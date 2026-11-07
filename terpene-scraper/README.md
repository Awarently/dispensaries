# terpene-scraper

Collects FLOWER products from two Florida medical dispensary menus and writes one spreadsheet sorted by total terpene % (highest first).

| Site | Store | Source |
|---|---|---|
| Trulieve | Nearest to ZIP 32162 (resolved via Trulieve's store API; currently Summerfield) | Trulieve's own storefront GraphQL feed `/api/graphql` (what the site itself calls) |
| MÜV (Verano) | Lady Lake, 929 US-441 Hwy Ste 202 (nearest MÜV to 32162) | Server-rendered HTML of `muvfl.com/locations/lady-lake/menu/menu/flower-3485` (no JSON feed is exposed; the Sweed menu is rendered into the page) |

No login, no cart/checkout/account URLs, no access-control bypass. Requests are 1-2 s apart with the User-Agent `terpene-scraper/1.0 (personal price comparison; ...)`.

## robots.txt findings (checked 2026-11-07)

- **trulieve.com**: Disallows `/*page=*`, `/*search*`, `/*sort=*`, `/*filter=*`, `/*brand=*` etc. on HTML pages, so the tool does **not** scrape paginated category pages. It explicitly has `Allow: /*graphql`, and the tool uses only `/api/graphql` (POST). Allowed.
- **muvfl.com**: `Disallow: /*?*` for all agents, i.e. any URL with a query string. The flower menu paginates with `?page=2`, `?page=3`. **The tool only fetches page 1 (24 products) and refuses pages 2+.** Result: MÜV data is incomplete (page 1 of 3, in the site's default "Most Popular" order). I found no robots-compliant route to the rest (sitemaps contain no menu product URLs). Getting the full menu would need MÜV's permission; the robots check is built into every request and has no override flag.

## Setup (Windows)

```bat
cd C:\dev\terpene-scraper
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Output: `terpenes.csv` and `terpenes.xlsx` in the project folder (overwritten each run; use `--out DIR` to change, `--zip` to change the ZIP for the Trulieve store lookup; the MÜV store is set by `STORE_SLUG` in `terpene_scraper/muv.py`).

Columns: dispensary, store location, brand, product name, subcategory, strain type, weight, price, sale price, THC %, total terpene %, in stock, product URL, date collected. The xlsx has a filter row and a frozen header.

Notes on the data:
- Trulieve flower includes whole flower, minis, ground and pre-rolls (the site's Flower category). Terp % is the batch (variant) shown on the tile; in-stock batches are preferred.
- MÜV THC/terp ranges (`26.50 - 27.72%`) are stored as the upper value. MÜV shows the price for the default size; other sizes cost different amounts.
- Products without a terpene % are skipped and counted in the summary.

## Daily run with Windows Task Scheduler

1. `run_daily.bat` is included. It `cd`s to its own folder and appends output to `run.log`. If you use the venv, change its last line to `".venv\Scripts\python.exe" run.py >> run.log 2>&1`.
2. Open **Task Scheduler** > **Create Task...** (not "Basic Task").
3. **General**: name `Terpene scraper`; choose "Run only when user is logged on" (simplest).
4. **Triggers** > New: Daily, pick a time (e.g. 7:30 AM). Menus change during the day, so once daily is plenty.
5. **Actions** > New: Start a program. Program: `C:\dev\terpene-scraper\run_daily.bat`. Start in: `C:\dev\terpene-scraper`.
6. **Settings**: tick "Run task as soon as possible after a scheduled start is missed".
7. Test: right-click the task > Run, then check `run.log` and the updated `terpenes.xlsx`. Close the xlsx in Excel before a run, or the write will fail.

Command-line equivalent:

```bat
schtasks /Create /SC DAILY /ST 07:30 /TN "Terpene scraper" /TR "C:\dev\terpene-scraper\run_daily.bat"
```

## Maintenance

- Trulieve's GraphQL schema and MÜV's HTML markup can change without notice. If a site breaks, the other still runs and the summary shows `FAILED`.
- Each run makes roughly 10 requests per site's worth of traffic, spaced 1-2 s apart.
