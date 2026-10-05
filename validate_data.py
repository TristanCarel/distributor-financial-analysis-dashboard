import json
import math
import sqlite3
from pathlib import Path

project = Path(__file__).resolve().parent
database = project / "research.db"

tickers = ["GWW", "MSM", "WCC"]
years = range(2021, 2026)

metrics = [
    "revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "receivables",
    "inventory",
    "payables",
]

balance_metrics = {"receivables", "inventory", "payables"}

# Open the database without changing it.
with sqlite3.connect(
    f"{database.as_uri()}?mode=ro", uri=True
) as connection:
    connection.row_factory = sqlite3.Row

    records = connection.execute(
        "SELECT * FROM annual_financials"
    ).fetchall()

    periods = connection.execute(
        "SELECT * FROM fiscal_periods"
    ).fetchall()

expected = {
    (ticker, year, metric)
    for ticker in tickers
    for year in years
    for metric in metrics
}

actual = {
    (row["ticker"], row["year"], row["metric"])
    for row in records
}

if actual != expected or len(records) != len(expected):
    missing = expected - actual
    extra = actual - expected
    raise ValueError(
        f"Coverage problem. Missing: {missing}. Extra: {extra}. "
        f"Expected {len(expected)} rows; found {len(records)}."
    )

print(f"PASS: All {len(expected)} expected observations are present.")

period_lookup = {
    (row["ticker"], row["year"]): row
    for row in periods
}

expected_periods = {
    (ticker, year)
    for ticker in tickers
    for year in years
}

if (
    set(period_lookup) != expected_periods
    or len(periods) != len(expected_periods)
):
    raise ValueError("Missing, duplicate, or unexpected fiscal periods.")

sources = {
    ticker: json.loads(
        (project / "data" / "raw" / f"{ticker}_companyfacts.json")
        .read_text(encoding="utf-8")
    )
    for ticker in tickers
}

for row in records:
    ticker = row["ticker"]
    year = row["year"]
    metric = row["metric"]
    value = row["value_usd"]
    label = f"{ticker} FY{year} {metric}"

    if value is None or not math.isfinite(value):
        raise ValueError(f"{label}: missing or invalid value.")

    period = period_lookup[(ticker, year)]
    facts = sources[ticker]["facts"]["us-gaap"]
    observations = facts[row["source_tag"]]["units"]["USD"]

    matches = [
        item
        for item in observations
        if item.get("form") in ("10-K", "10-K/A")
        and item.get("end") == period["period_end"]
        and item.get("accn") == row["accession"]
        and item.get("filed") == row["filed"]
        and item.get("val") == value
        and (
            (
                metric in balance_metrics
                and "start" not in item
            )
            or (
                metric not in balance_metrics
                and item.get("start") == period["period_start"]
            )
        )
    ]

    if not matches:
        raise ValueError(
            f"{label}: value, period, or filing reference "
            "does not match the saved SEC source."
        )

print("PASS: All values match their saved SEC observations.")
print("PASS: Fiscal periods and filing references match.")
print("\nValidation complete.")
print(
    "These checks confirm source consistency, not whether "
    "each accounting tag is the best analytical choice."
)