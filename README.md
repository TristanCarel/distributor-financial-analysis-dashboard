# Distributor Research
**[Open the live dashboard](https://tristan-distributor-research.streamlit.app/)**
A financial research dashboard comparing W.W. Grainger (GWW),
MSC Industrial (MSM), and Wesco International (WCC) across
fiscal years 2021–2025.

## Research question

How effectively do these distributors convert reported earnings
into operating cash flow, and which changes warrant further
investigation?

## What the project does

- Downloads public financial data from SEC Company Facts.
- Stores financial observations and filing references in SQLite.
- Compares profitability, cash conversion, and working capital.
- Flags receivables and inventory growth above revenue growth,
  declining operating margins, and rising working-capital intensity.
- Displays charts explaining triggered flags.
- Connects quantitative findings with research from annual filings.
- Checks database values against saved SEC observations.

## Selected research findings

- **Wesco:** FY2025 operating cash flow fell as receivables and
  inventory absorbed cash. Management's explanation helps distinguish
  funding needs from conclusions about credit or inventory quality.
- **MSC Industrial:** A receivables-sale program contributed to the
  FY2023 cash-conversion improvement. Higher cash conversion does
  not necessarily reflect faster customer collections.
- **Grainger:** Special charges explain much, but not all, of the
  FY2025 reported operating-margin decline.

The dashboard includes source links and limitations for these findings.

## Tools

Python · pandas · SQLite / SQL · Streamlit · Plotly · SEC Company Facts API

## Run locally

Requires Python and the packages listed in requirements.txt.

Create a virtual environment:

    python -m venv .venv

Activate it on macOS:

    source .venv/bin/activate

Or on Windows PowerShell:

    .venv\Scripts\Activate.ps1

Install packages:

    python -m pip install -r requirements.txt

Launch the dashboard using the included dataset:

    python -m streamlit run app.py --server.address localhost

If your computer uses the command python3 instead of python,
use python3 to create the virtual environment.

## Rebuild and validate the dataset

Run:

    python run_pipeline.py

Enter a contact email when prompted for SEC requests.

The pipeline prepares the database, checks downloads, loads
financial observations, and runs validation. Existing source
files are reused; this is not a live refresh service.

To run validation separately:

    python validate_data.py

Validation checks completeness and consistency with saved
source observations, including values, periods, and filing
references. It does not independently establish whether every
accounting tag is the best analytical choice.

## Metric definitions

- Operating margin = operating income / revenue.
- Cash conversion = operating cash flow / consolidated net income.
- Free cash flow = operating cash flow − capital expenditures.
- Free-cash-flow margin = free cash flow / revenue.
- Trade working capital = receivables + inventory − trade payables.
- Working-capital intensity = year-end trade working capital / revenue.

Percentage metrics are multiplied by 100.

## Important limitations

- Fiscal years differ: MSC ends around August, while Grainger
  and Wesco end in December. MSC FY2022 includes 53 weeks.
- Business mixes and capital-expenditure definitions differ.
- Year-end working-capital balances are snapshots, not annual averages.
- Balance-sheet changes do not directly reconcile operating cash flow.
- Flags identify questions for investigation, not investment ratings.
  Small changes can trigger a rule without being material.
- The dataset uses selected annual observations from saved SEC files;
  it is not a point-in-time backtesting dataset.
- Research findings are manually written and do not update automatically.

## Scope

An independent portfolio research project using public information.
It is a historical screening and research tool, not a valuation
or prediction model.
