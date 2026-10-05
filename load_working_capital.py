import json
import sqlite3
from pathlib import Path

import pandas as pd

project = Path(__file__).parent
database = project / "research.db"

# Get the exact fiscal-year dates already established.
with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
    periods = pd.read_sql_query("""
        SELECT ticker, year, period_end
        FROM fiscal_periods
        WHERE year BETWEEN 2021 AND 2025
        ORDER BY ticker, year
    """, connection)

records_to_save = []

for ticker in ["GWW", "MSM", "WCC"]:
    source = project / "data" / "raw" / f"{ticker}_companyfacts.json"
    data = json.loads(source.read_text(encoding="utf-8"))

    tags = {
        "receivables": "AccountsReceivableNetCurrent",
        "inventory": "InventoryNet",
        "payables": "AccountsPayableCurrent",
    }

    # Grainger uses this label for its trade accounts payable.
    if ticker == "GWW":
        tags["payables"] = "AccountsPayableTradeCurrentAndNoncurrent"

    company_periods = periods.loc[periods["ticker"] == ticker]

    if company_periods["year"].tolist() != [2021, 2022, 2023, 2024, 2025]:
        raise ValueError(f"Missing fiscal-year dates for {ticker}")

    for metric, tag in tags.items():
        observations = data["facts"]["us-gaap"][tag]["units"]["USD"]

        for period in company_periods.itertuples():
            # Balance-sheet figures describe one date, not a date range.
            matches = [
                item for item in observations
                if item.get("form") in ["10-K", "10-K/A"]
                and item["end"] == period.period_end
                and "start" not in item
            ]

            if not matches:
                raise ValueError(
                    f"Missing {metric}: {ticker}, {period.period_end}"
                )

            latest = max(
                matches,
                key=lambda item: (item["filed"], item["accn"]),
            )

            records_to_save.append((
                ticker,
                int(period.year),
                metric,
                float(latest["val"]),
                tag,
                latest["filed"],
                latest["accn"],
            ))

    print(f"{ticker}: working-capital data checked")

# Save only after all companies pass the extraction checks.
with sqlite3.connect(database) as connection:
    connection.executemany("""
        INSERT INTO annual_financials
        (ticker, year, metric, value_usd, source_tag, filed, accession)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, year, metric) DO UPDATE SET
            value_usd = excluded.value_usd,
            source_tag = excluded.source_tag,
            filed = excluded.filed,
            accession = excluded.accession
    """, records_to_save)

    check = pd.read_sql_query("""
        SELECT ticker, metric, value_usd
        FROM annual_financials
        WHERE year = 2025
          AND metric IN ('receivables', 'inventory', 'payables')
        ORDER BY ticker
    """, connection)

balances = check.pivot(
    index="ticker", columns="metric", values="value_usd"
)

balances["trade_working_capital"] = (
    balances["receivables"] + balances["inventory"] - balances["payables"]
)

print("\n2025 year-end balances — USD millions\n")
print((balances / 1_000_000).round(3).to_string())
print(f"\nSaved {len(records_to_save)} working-capital observations.")