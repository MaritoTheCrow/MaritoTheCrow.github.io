# How to add reports to the Merval Analysis section

You do not edit any web page to publish a report. You put files in a folder, run one command, and
the site updates. (These tools run on your computer only; the site itself is plain Jekyll.)

Use `py` on Windows (`python3` on Mac/Linux). Run everything from the repo folder
(`C:\Users\mario\MaritoTheCrow.github.io`).

## 1. Name your files

```
<TICKER>_<YYYY-MM-DD>_<type>.<ext>
```

| Part   | Allowed values |
|--------|----------------|
| TICKER | any ticker in `_data/merval/tickers.yml` (AGRO, ALUA, ...) |
| date   | the report date, `2026-01-30` |
| type   | `initiation`, `update`, `valuation_model`, `financial_data`, `presentation`, `note` |
| ext    | `pdf`, `xlsx`, `docx`, `pptx` |

Examples: `AGRO_2026-01-30_initiation.pdf`, `AGRO_2026-06-30_valuation_model.xlsx`.

Put all the files of a batch in one folder, **outside the repo** (for example `D:\Reports\inbox`).

## 2. Decide who can open each file (access level)

| Access       | What the visitor sees | What happens to the file |
|--------------|-----------------------|--------------------------|
| `free`       | **Download** button   | Copied into the repo (`assets/reports/<TICKER>/`) and published |
| `contact`    | **Request access** (form / email) | Never copied. Only its title, date and size are published |
| `subscriber` | **Subscribers only** (lock) | Never copied. Only its title, date and size are published |

If you do not say anything, a file gets `subscriber` (the safe default: nothing becomes public by accident).

To set the access, titles, summary, rating or target price, make a CSV (Excel can save as CSV, UTF-8)
with these columns; only `filename` is required:

```
filename,access,title_en,title_es,summary_en,summary_es,rating,target_price,currency,language
AGRO_2026-01-30_initiation.pdf,free,Agrometal - Initiation of coverage,Agrometal - Inicio de cobertura,Buy (High Risk) on AGRO,Compra (alto riesgo) en AGRO,Buy (High Risk),64.0,ARS,en
```

`language` is `en`, `es` or `both`. `target_price` uses a dot or comma for decimals.

## 3. Run the tool

First a practice run that changes nothing:

```
py tools/add_reports.py D:\Reports\inbox --csv D:\Reports\inbox\overrides.csv --dry-run
```

If it looks right, run it for real (same command without `--dry-run`):

```
py tools/add_reports.py D:\Reports\inbox --csv D:\Reports\inbox\overrides.csv
```

The tool will:

- check each ticker, date, type and format and tell you about any mistake (and continue with the good files);
- add or update the entry in `_data/merval/reports.yml` (running it twice never creates duplicates);
- copy **free** files byte-for-byte (your original file and its author/last-modified-by data are never touched);
- warn if a file is over 50 MB (GitHub limit is 100 MB): host it elsewhere and paste the link in the `url` field of `reports.yml`;
- print the repo size at the end.

## 4. Preview and publish

```
git status                 # see what changed
git add -A
git commit -m "Add AGRO reports"
git push                   # publishes the site (only when you are ready)
```

When you commit, a safety check runs automatically (`tools/check_gated.py`). It **blocks the commit** if a
`contact` or `subscriber` file, or any stray Excel/Word/PowerPoint file, is about to enter the repo.
It is switched on with `git config core.hooksPath tools/hooks` (already done in this clone; run it once on a new computer).

## 5. Adding or fixing a company

Edit `_data/merval/tickers.yml` (set `status: covered` when you publish the first report, and `verified: true`
once you have checked the name, sector and index), then run:

```
py tools/sync_ticker_pages.py
```

That creates or removes the page for each company in English and Spanish.

## Changing the access of a file later

Edit its `access:` line in `_data/merval/reports.yml`. If you change a `free` file to `contact` or `subscriber`,
also remove the public copy: `git rm "assets/reports/AGRO/<file>"` (a file already pushed stays in git history;
if it was sensitive, tell me and we will clean the history).

## Local preview

```
bundle exec jekyll serve
```

then open http://127.0.0.1:4000 (Ruby + Jekyll were installed for this; see the final report for details).

## Checks you can run any time

```
py tools/check_gated.py --all      # no gated file is tracked
py tools/check_palette.py          # no color outside the locked palette
py tools/check_site.py             # build output: no broken internal links or anchors, EN/ES parity
py tools/sync_ticker_pages.py --check
```
