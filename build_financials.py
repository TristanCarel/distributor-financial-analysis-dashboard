import json
import sqlite3
from pathlib import Path

import pandas as pd

project = Path(__file__).parent
source = project / "data" / "raw" / "GWW_companyfacts.json"
data = json.loads(source.read_text(encoding="utf-8"))

# Translate readable metric names into SEC accounting labels.
metrics = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "operating_income": "OperatingIncomeLoss",
    "net_income": "ProfitLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capex": "PaymentsToAcquirePropertyPlantAndEquipment",
}


def extract_annual(tag):
    """Extract Grainger's five annual values for one metric."""
    records = data["facts"]["us-gaap"][tag]["units"]["USD"]
    table = pd.DataFrame(records)

    table["start"] = pd.to_datetime(table["start"])
    table["end"] = pd.to_datetime(table["end"])
    days = (table["end"] - table["start"]).dt.days

    # Grainger uses calendar years. Other companies may not.
    annual = table.loc[
        table["form"].isin(["10-K", "10-K/A"])
        & days.between(364, 365)
        & (table["start"].dt.month == 1)
        & (table["start"].dt.day == 1)
        & (table["end"].dt.month == 12)
        & (table["end"].dt.day == 31)
    ].copy()

    annual = (
        annual.sort_values(["filed", "accn"])
        .drop_duplicates(["start", "end"], keep="last")
        .sort_values("end")
    )

    annual["year"] = annual["end"].dt.year
    annual = annual.loc[annual["year"].between(2021, 2025)].copy()

    if annual["year"].tolist() != [2021, 2022, 2023, 2024, 2025]:
        raise ValueError(f"Missing or duplicate annual values for {tag}")

    return annual


# Prepare records, keeping a source reference for every value.
records_to_save = []

for metric, tag in metrics.items():
    annual = extract_annual(tag)

    for row in annual.itertuples():
        records_to_save.append((
            "GWW",
            int(row.year),
            metric,
            float(row.val),
            tag,
            row.filed,
            row.accn,
        ))

# Save the financial observations in our existing database.
with sqlite3.connect(project / "research.db") as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS annual_financials (
            ticker TEXT NOT NULL,
            year INTEGER NOT NULL,
            metric TEXT NOT NULL,
            value_usd REAL NOT NULL,
            source_tag TEXT NOT NULL,
            filed TEXT NOT NULL,
            accession TEXT NOT NULL,
            PRIMARY KEY (ticker, year, metric)
        )
    """)

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

    # Retrieve the saved figures using SQL.
    saved = pd.read_sql_query("""
        SELECT year, metric, value_usd
        FROM annual_financials
        WHERE ticker = 'GWW'
        ORDER BY year, metric
    """, connection)

# Rearrange the records into one row per year.
summary = saved.pivot(
    index="year", columns="metric", values="value_usd"
)

summary["free_cash_flow"] = (
    summary["operating_cash_flow"] - summary["capex"]
)

# Store actual dollars; display millions for readability.
display = summary[
    ["revenue", "operating_income", "net_income",
     "operating_cash_flow", "capex", "free_cash_flow"]
] / 1_000_000

print("\nGrainger financials — USD millions\n")
print(display.to_string(float_format=lambda value: f"{value:,.0f}"))
print(f"\nSaved {len(records_to_save)} financial observations to research.db")
# Calculate ratios using the dollar amounts in summary.
ratios = pd.DataFrame(index=summary.index)

positive_revenue = summary["revenue"].where(summary["revenue"] > 0)
positive_income = summary["net_income"].where(summary["net_income"] > 0)

ratios["operating_margin_pct"] = (
    summary["operating_income"] / positive_revenue * 100
)

ratios["cash_conversion_x"] = (
    summary["operating_cash_flow"] / positive_income
)

ratios["fcf_margin_pct"] = (
    summary["free_cash_flow"] / positive_revenue * 100
)

print("\nGrainger financial ratios\n")
print(
    ratios.to_string(
        float_format=lambda value: f"{value:.2f}",
        na_rep="N/A",
    )
)

output_folder = project / "data" / "processed"
output_folder.mkdir(parents=True, exist_ok=True)
ratios.to_csv(output_folder / "GWW_ratios.csv")

print("\nSaved: data/processed/GWW_ratios.csv")