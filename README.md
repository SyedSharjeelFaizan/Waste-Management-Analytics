# Waste Management Analytics System

A Streamlit dashboard for analysing municipal solid-waste management data across Indian states, years and waste
categories. It validates the dataset, stores it in a local SQLite database, and calculates:

- **Collection efficiency** = Collected ÷ Generated × 100
- **Treatment efficiency** = Treated ÷ Collected × 100
- **Recycling rate** = Recycled ÷ Treated × 100

Aggregate rates are always calculated from summed quantities (never an average of percentages). On top of these it
provides state, year and waste-category comparisons, a head-to-head comparison of any two states, a priority
classification with explanations, rule-based insight cards, and PDF / CSV / ZIP exports.

> **About the data:** the dataset in this project has unverified provenance and appears to be synthetic. It is not
> official government data. Quantities are in TPD (tonnes per day); sums of TPD are summed daily rates, not annual
> tonnage.

## Technologies

Python · pandas · SQLite (Python's built-in `sqlite3`) · Streamlit · Plotly · pytest (tests only)

## Requirements

- **Python 3.11 or newer.** The pinned `streamlit` and `pandas` versions require it. The project was developed and
  tested on Python 3.12.10 on Windows 11; other versions and operating systems have not been tested.
- Internet access once, to install the packages listed in `requirements.txt`
  (`streamlit==1.66.1`, `plotly==7.1.0`, `pandas==3.1.0`, `pytest==9.2.0`).
- No database server, API keys, accounts or environment variables are needed.

## Setup and run

Run all commands from the project's root folder (the folder that contains this README).

**1. Create a virtual environment** (Windows):

```bash
python -m venv .venv
```

**2. Install the dependencies:**

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**3. Start the dashboard:**

```bash
.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

**4. Open http://localhost:8501 in your browser.** The browser does not open by itself, because
`.streamlit/config.toml` sets `headless = true`. To stop the app, press `Ctrl+C` in the terminal.

macOS / Linux (not tested): use `python3 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt`
and `.venv/bin/python -m streamlit run app/streamlit_app.py`.

If port 8501 is busy, add `--server.port 8502` to the run command and open that port instead.

## The dataset and the database

- The original dataset is `data/raw/Waste_Management_Analytics_300_Records.csv` (300 rows: 10 states × 3 years
  (2020–2022) × 10 waste categories). The code reads it from exactly this path. Do not edit or rename it.
- On the first start the app validates the CSV and creates the SQLite database `data/waste.db` automatically.
  This file is generated; you can delete it at any time and it will be recreated.
- To rebuild the database yourself (this also writes the cleaned data to `data/processed/waste_clean.csv`):

```bash
.venv\Scripts\python.exe scripts/build_database.py
```

## Dashboard pages

Overview · State Comparison (ranking, head-to-head, performance heatmap) · Year Trends · Waste Categories ·
Priority (classification and explanations) · Insights (rule-based insight cards, with a focused analysis by state, waste
type, year and indicator on top of the sidebar filters) · Reports (a short summary of what will be exported, and PDF, CSV
and ZIP downloads). The sidebar filters (year, state, waste category) and the analysis settings (rule thresholds,
priority quantiles) apply across the pages. Downloads are generated from the current selection and are saved by your browser.

## Configuration

Nothing needs to be configured to run the project.

- `.streamlit/config.toml`: the colour theme, `headless = true`, and usage-statistics collection turned off. Streamlit
  reads it from the folder where you start the app, so start it from the project root.
- `src/waste_analytics/config.py`: file paths and the default rule thresholds and priority quantiles (all of them can
  also be changed in the dashboard sidebar).

## Tests

```bash
.venv\Scripts\python.exe -m pytest
```

Six of the test files read the SQLite database, so `data/waste.db` must exist first: either start the dashboard once
or run `scripts/build_database.py` (see above) before running the tests. If you run the tests before the database
exists, those tests fail and an empty `data/waste.db` is left behind; the dashboard then shows "The analytics database
could not be loaded". Run `scripts/build_database.py` to fix it.

## Project structure

```
Waste_Management_Analytics_Shared/
├── README.md
├── requirements.txt               Python dependencies (pinned)
├── .streamlit/config.toml         Streamlit theme and server settings
├── app/
│   ├── streamlit_app.py           the dashboard
│   └── style.css                  dashboard styling
├── src/waste_analytics/           analytics code
│   ├── config.py                  paths, column names, default thresholds
│   ├── preprocessing.py           CSV loading, validation and cleaning
│   ├── database.py                SQLite storage and queries
│   ├── indicators.py              collection / treatment / recycling and aggregation
│   ├── priority.py                composite score and priority classification
│   ├── insights.py                rule-based insights (rules R1–R5)
│   ├── insight_cards.py           insight cards built from the rule results
│   ├── insight_focus.py           focused analysis: narrows the data for the Insights selectors
│   ├── compare.py                 head-to-head state comparison
│   ├── explain.py                 priority explanations and suggestions
│   ├── reports.py                 CSV / ZIP / PDF report data
│   ├── pdf_report.py              PDF writer (no extra library)
│   └── charts.py                  Plotly charts
├── data/raw/                      the original dataset (CSV)
├── scripts/build_database.py      rebuilds the SQLite database from the CSV
├── tests/                         automated tests (pytest)
└── docs/methodology.md            methodology: validation, formulas, priority classification, rules, exports
```

Generated locally (not included in this folder): `.venv/`, `data/waste.db`, `data/processed/waste_clean.csv`.

## Troubleshooting

- **"DLL load failed ... The filename or extension is too long" (Windows)**: the folder is nested too deeply. Unzip it
  to a short path such as `C:\Projects\` or your Desktop, and create the virtual environment there.
- **`ModuleNotFoundError`**: run the commands from the project root and use the virtual environment's Python
  (`.venv\Scripts\python.exe`), not the system Python.
- **Dashboard shows "analytics database could not be loaded"**: run `scripts/build_database.py`, then reload the page.
- **The dashboard shows Streamlit's default dark theme instead of the green theme**: you started Streamlit from a
  different folder; start it from the project root so that `.streamlit/config.toml` is found.
