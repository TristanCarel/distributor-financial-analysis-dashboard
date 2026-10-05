import json
from pathlib import Path

import pandas as pd

project_folder = Path(__file__).parent

# Read the data we already downloaded. No new SEC request.
source_file = project_folder / "data" / "raw" / "GWW_companyfacts.json"
data = json.loads(source_file.read_text(encoding="utf-8"))

# This is the revenue label used in Grainger's recent filings.
revenue_tag = "RevenueFromContractWithCustomerExcludingAssessedTax"
records = data["facts"]["us-gaap"][revenue_tag]["units"]["USD"]

# Turn the list of financial observations into a table.
table = pd.DataFrame(records)

# Convert date text into dates Python can calculate with.
table["start"] = pd.to_datetime(table["start"])
table["end"] = pd.to_datetime(table["end"])
table["days"] = (table["end"] - table["start"]).dt.days

# Keep full calendar years from annual reports.
# This calendar-year rule is specific to Grainger.
annual = table.loc[
    table["form"].isin(["10-K", "10-K/A"])
    & table["days"].between(364, 365)
    & (table["start"].dt.month == 1)
    & (table["start"].dt.day == 1)
    & (table["end"].dt.month == 12)
    & (table["end"].dt.day == 31)
].copy()

# Keep the latest disclosure for each annual period.
annual = (
    annual.sort_values(["filed", "accn"])
    .drop_duplicates(subset=["start", "end"], keep="last")
    .sort_values("end")
)

# Use the period end—not the filing's fiscal-year label.
annual["year"] = annual["end"].dt.year
annual = annual.loc[annual["year"].between(2021, 2025)].copy()

if annual["year"].tolist() != [2021, 2022, 2023, 2024, 2025]:
    raise ValueError("Expected one annual revenue value for each year, 2021–2025.")

annual["revenue_millions"] = annual["val"] / 1_000_000
annual["growth_pct"] = annual["val"].pct_change(fill_method=None) * 100

# Preserve filing references alongside the results.
result = annual[
    ["year", "revenue_millions", "growth_pct", "filed", "accn"]
]

output_folder = project_folder / "data" / "processed"
output_folder.mkdir(parents=True, exist_ok=True)
result.to_csv(output_folder / "GWW_revenue.csv", index=False)

print(
    result[["year", "revenue_millions", "growth_pct"]].to_string(
        index=False,
        float_format=lambda value: f"{value:,.2f}",
        na_rep="N/A",
    )
)

print("\nSaved: data/processed/GWW_revenue.csv")