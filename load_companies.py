import json
import sqlite3
from pathlib import Path

import pandas as pd

project = Path(__file__).parent

metrics = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "operating_income": "OperatingIncomeLoss",
    "net_income": "ProfitLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capex": "PaymentsToAcquirePropertyPlantAndEquipment",
}

financial_records = []
period_records = []

for ticker in ["GWW", "MSM", "WCC"]:
    source = project / "data" / "raw" / f"{ticker}_companyfacts.json"
    data = json.loads(source.read_text(encoding="utf-8"))

    # Use a separate copy so Wesco's change affects only Wesco.
    company_metrics = metrics.copy()
    if ticker == "WCC":
        company_metrics["capex"] = "PaymentsToAcquireProductiveAssets"

    reference_periods = None

    for metric, tag in company_metrics.items():
        observations = data["facts"]["us-gaap"][tag]["units"]["USD"]
        table = pd.DataFrame(observations)

        table["start"] = pd.to_datetime(table["start"])
        table["end"] = pd.to_datetime(table["end"])
        table["days"] = (table["end"] - table["start"]).dt.days

        # Include full years, including MSC's 52- and 53-week years.
        annual = table.loc[
            table["form"].isin(["10-K", "10-K/A"])
            & table["days"].between(360, 371)
            & table["end"].dt.year.between(2021, 2025)
        ].copy()

        annual = (
            annual.sort_values(["filed", "accn"])
            .drop_duplicates(["start", "end"], keep="last")
            .sort_values("end")
        )

        # These three companies label fiscal years by the ending year.
        annual["year"] = annual["end"].dt.year

        if annual["year"].tolist() != [2021, 2022, 2023, 2024, 2025]:
            raise ValueError(f"Check annual periods: {ticker}, {metric}")

        periods = [
            (
                int(row.year),
                row.start.strftime("%Y-%m-%d"),
                row.end.strftime("%Y-%m-%d"),
            )
            for row in annual.itertuples()
        ]

        # All five metrics must cover the same periods.
        if reference_periods is None:
            reference_periods = periods
            period_records.extend(
                (ticker, year, start, end)
                for year, start, end in periods
            )
        elif periods != reference_periods:
            raise ValueError(f"Period mismatch: {ticker}, {metric}")

        for row in annual.itertuples():
            financial_records.append((
                ticker, int(row.year), metric, float(row.val),
                tag, row.filed, row.accn,
            ))

    print(f"{ticker}: five years checked")

# Write only after all three companies pass the checks above.
with sqlite3.connect(project / "research.db") as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_periods (
            ticker TEXT NOT NULL,
            year INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            PRIMARY KEY (ticker, year)
        )
    """)

    connection.executemany("""
        INSERT INTO fiscal_periods
        (ticker, year, period_start, period_end)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ticker, year) DO UPDATE SET
            period_start = excluded.period_start,
            period_end = excluded.period_end
    """, period_records)

    connection.executemany("""
        INSERT INTO annual_financials
        (ticker, year, metric, value_usd, source_tag, filed, accession)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, year, metric) DO UPDATE SET
            value_usd = excluded.value_usd,
            source_tag = excluded.source_tag,
            filed = excluded.filed,
            accession = excluded.accession
    """, financial_records)

    # JOIN connects financial figures to their reporting dates.
    check = pd.read_sql_query("""
        SELECT f.ticker, p.period_end, f.value_usd / 1000000.0 AS revenue_millions
        FROM annual_financials AS f
        JOIN fiscal_periods AS p
          ON f.ticker = p.ticker AND f.year = p.year
        WHERE f.metric = 'revenue' AND f.year = 2025
        ORDER BY f.ticker
    """, connection)

print("\n2025 revenue check:")
print(check.to_string(index=False))
print(f"\nSaved {len(financial_records)} financial observations.")