import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# ---------- Page setup ----------

st.set_page_config(
    page_title="Distributor Financial Analysis Dashboard",
    layout="wide",
)

st.title("Distributor Financial Analysis Dashboard")
st.caption(
    "Earnings quality and cash conversion · Fiscal years 2021–2025"
)

project = Path(__file__).parent
database = project / "research.db"

if not database.exists():
    st.error("Database missing. Run the setup and loading scripts.")
    st.stop()


# ---------- Read the database ----------

try:
    with sqlite3.connect(
        f"{database.as_uri()}?mode=ro", uri=True
    ) as connection:
        records = pd.read_sql_query("""
            SELECT
                f.*,
                c.company_name,
                p.period_start,
                p.period_end
            FROM annual_financials AS f
            JOIN companies AS c
              ON f.ticker = c.ticker
            JOIN fiscal_periods AS p
              ON f.ticker = p.ticker AND f.year = p.year
            WHERE f.year BETWEEN 2021 AND 2025
            ORDER BY f.ticker, f.year
        """, connection)
except (sqlite3.Error, pd.errors.DatabaseError) as error:
    st.error(f"Could not read the financial database: {error}")
    st.stop()

if records.empty:
    st.error("No data found. Run the financial loading scripts.")
    st.stop()

financials = records.pivot(
    index=[
        "ticker", "company_name", "year",
        "period_start", "period_end",
    ],
    columns="metric",
    values="value_usd",
).reset_index()

required = [
    "revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "receivables",
    "inventory",
    "payables",
]

if (
    not set(required).issubset(financials.columns)
    or financials[required].isna().any().any()
):
    st.error(
        "Required figures are missing. Run load_companies.py "
        "and load_working_capital.py."
    )
    st.stop()

financials = financials.sort_values(["ticker", "year"])

for symbol in ["GWW", "MSM", "WCC"]:
    years = financials.loc[
        financials["ticker"] == symbol, "year"
    ].tolist()

    if years != [2021, 2022, 2023, 2024, 2025]:
        st.error(f"Expected five unique annual periods for {symbol}.")
        st.stop()


# ---------- Calculate metrics ----------

revenue = financials["revenue"].where(financials["revenue"] > 0)
income = financials["net_income"].where(financials["net_income"] > 0)

fcf = financials["operating_cash_flow"] - financials["capex"]
trade_wc = (
    financials["receivables"]
    + financials["inventory"]
    - financials["payables"]
)

financials["Revenue ($M)"] = financials["revenue"] / 1_000_000
financials["Free cash flow ($M)"] = fcf / 1_000_000
financials["Operating margin (%)"] = (
    financials["operating_income"] / revenue * 100
)
financials["Cash conversion (x)"] = (
    financials["operating_cash_flow"] / income
)
financials["Free-cash-flow margin (%)"] = fcf / revenue * 100
financials["Receivables / revenue (%)"] = (
    financials["receivables"] / revenue * 100
)
financials["Inventory / revenue (%)"] = (
    financials["inventory"] / revenue * 100
)
financials["Payables / revenue (%)"] = (
    financials["payables"] / revenue * 100
)
financials["Trade working capital / revenue (%)"] = (
    trade_wc / revenue * 100
)

metric_names = [
    "Revenue ($M)",
    "Free cash flow ($M)",
    "Operating margin (%)",
    "Cash conversion (x)",
    "Free-cash-flow margin (%)",
    "Receivables / revenue (%)",
    "Inventory / revenue (%)",
    "Payables / revenue (%)",
    "Trade working capital / revenue (%)",
]

names = financials.set_index("ticker")["company_name"].to_dict()
ciks = {
    "GWW": "277135",
    "MSM": "1003078",
    "WCC": "929008",
}


# ---------- Shared controls ----------

with st.sidebar:
    st.header("Company")
    ticker = st.selectbox(
        "Select a company",
        ["GWW", "MSM", "WCC"],
        format_func=lambda symbol: f"{names[symbol]} ({symbol})",
    )
    st.caption(
        "Controls the company overview and diligence flags. "
        "The comparison chart and research findings cover all three."
    )

company = financials.loc[
    financials["ticker"] == ticker
].sort_values("year")

latest = company.iloc[-1]

overview_tab, flags_tab, research_tab = st.tabs([
    "Financial overview",
    "Diligence flags",
    "Research findings",
])


# ---------- Tab 1: Financial overview ----------

with overview_tab:
    st.subheader(f"{names[ticker]} — FY{int(latest['year'])}")
    st.caption(
        f"Reporting period: {latest['period_start']} "
        f"to {latest['period_end']}"
    )

    left, middle, right = st.columns(3)
    left.metric("Revenue", f"${latest['Revenue ($M)']:,.1f}M")
    middle.metric(
        "Free cash flow",
        f"${latest['Free cash flow ($M)']:,.1f}M",
    )
    right.metric(
        "Operating margin",
        f"{latest['Operating margin (%)']:.2f}%",
    )

    st.subheader("Peer comparison")
    selected_metric = st.selectbox(
        "Metric",
        metric_names,
        index=4,
    )

    chart = px.line(
        financials,
        x="year",
        y=selected_metric,
        color="ticker",
        markers=True,
        hover_data=["company_name", "period_start", "period_end"],
        labels={"year": "Fiscal year", "ticker": "Company"},
        color_discrete_map={
            "GWW": "#60A5FA",
            "MSM": "#FBBF24",
            "WCC": "#34D399",
        },
    )
    chart.update_xaxes(dtick=1)
    chart.update_yaxes(rangemode="tozero")
    chart.update_layout(
        legend_title_text="",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    st.plotly_chart(chart)

    st.caption(
        "Fiscal periods and business mixes differ. MSC ends around August "
        "and has a 53-week FY2022; Grainger and Wesco end in December."
    )

    # Transpose the table to avoid nine wide metric columns.
    st.subheader("Annual metrics")
    annual_table = company.set_index("year")[metric_names].T
    annual_table.columns = annual_table.columns.astype(str)
    annual_table.index.name = "Metric"
    st.dataframe(annual_table.round(2))

    st.download_button(
        "Download all company metrics",
        data=financials[
            ["ticker", "company_name", "year", "period_start", "period_end"]
            + metric_names
        ].to_csv(index=False).encode("utf-8"),
        file_name="distributor_metrics.csv",
        mime="text/csv",
    )

    with st.expander("Definitions and methodology"):
        st.markdown(
            """
- **Operating margin:** operating income ÷ revenue.
- **Cash conversion:** operating cash flow ÷ consolidated net income.
- **Free cash flow:** operating cash flow − capital expenditures.
- **Free-cash-flow margin:** free cash flow ÷ revenue.
- **Trade working capital:** receivables + inventory − payables.
- **Working-capital ratios:** fiscal-year-end balances ÷ annual revenue.
            """
        )
        st.write(
            "Net income includes noncontrolling interests. Free cash flow "
            "is before acquisitions and financing. Nonpositive denominators "
            "are unavailable; small positive earnings can distort ratios."
        )
        st.write(
            "Wesco's capital-spending tag includes software and other "
            "productive assets. Grainger and MSC use their property, plant, "
            "and equipment spending tags."
        )
        st.write(
            "The dataset retains the latest annual disclosure for each "
            "metric and period in the downloaded files. Later filings may "
            "revise earlier figures. This is not a point-in-time backtest."
        )
        st.write(
            "Changes in balance-sheet working capital do not directly "
            "reconcile operating cash flow. Acquisitions, disposals, currency "
            "movements, and other adjustments can affect the balances."
        )
        st.caption(
            "Checks for missing values and reporting periods are implemented. "
            "Verification against published statements remains in progress."
        )

    with st.expander("Source records"):
        source_year = st.selectbox(
            "Source fiscal year",
            [2025, 2024, 2023, 2022, 2021],
            key="source_year",
        )

        sources = records.loc[
            (records["ticker"] == ticker)
            & (records["year"] == source_year)
        ]

        # Wrapping text keeps long accounting labels and links readable.
        for item in sources.sort_values("metric").to_dict("records"):
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{ciks[ticker]}/"
                f"{item['accession'].replace('-', '')}/"
                f"{item['accession']}-index.htm"
            )
            with st.container(border=True):
                label = item["metric"].replace("_", " ").title()
                st.markdown(f"**{label}: ${item['value_usd']:,.0f}**")
                st.write(f"Accounting label: {item['source_tag']}")
                st.caption(
                    f"Fiscal year end: {item['period_end']} · "
                    f"Filed: {item['filed']}"
                )
                st.markdown(f"[Open source filing]({filing_url})")


# ---------- Tab 2: Diligence flags ----------

def growth_pct(current_value, previous_value):
    if (
        pd.isna(current_value)
        or pd.isna(previous_value)
        or previous_value <= 0
    ):
        return None
    return (current_value / previous_value - 1) * 100


with flags_tab:
    st.subheader(f"{names[ticker]} — automated screening")
    st.caption(
        "Rules identify changes for investigation. "
        "They are not investment ratings or a combined risk score."
    )

    review_year = st.selectbox(
        "Fiscal year to review",
        [2022, 2023, 2024, 2025],
        index=3,
    )

    current = company.loc[company["year"] == review_year].iloc[0]
    previous = company.loc[company["year"] == review_year - 1].iloc[0]

    sales_growth = growth_pct(current["revenue"], previous["revenue"])
    checks = []

    def add_check(rule, triggered, evidence, question):
        status = (
            "Unavailable" if triggered is None
            else "Review" if triggered
            else "Not triggered"
        )
        checks.append({
            "Rule": rule,
            "Status": status,
            "Evidence": evidence,
            "Diligence question": question,
        })

    for metric, title, question in [
        (
            "receivables",
            "Receivables outpace sales",
            "Did collection timing, customer terms, acquisitions, "
            "or receivables sales change?",
        ),
        (
            "inventory",
            "Inventory outpaces sales",
            "Is inventory supporting demand, or moving more slowly? "
            "Check acquisitions and product mix.",
        ),
    ]:
        balance_growth = growth_pct(current[metric], previous[metric])

        if balance_growth is None or sales_growth is None:
            add_check(
                title, None,
                "Growth unavailable: missing value or nonpositive prior base.",
                question,
            )
        else:
            gap = balance_growth - sales_growth
            add_check(
                title,
                gap > 0,
                f"Balance growth {balance_growth:.2f}% versus "
                f"revenue growth {sales_growth:.2f}%. "
                f"Gap: {gap:+.2f} percentage points.",
                question,
            )

    for metric, title, direction, question in [
        (
            "Operating margin (%)",
            "Operating margin declines",
            "down",
            "Did pricing, product mix, operating costs, or special "
            "charges explain the decline?",
        ),
        (
            "Trade working capital / revenue (%)",
            "Working-capital intensity rises",
            "up",
            "Which balance drove the change? Check seasonality, acquisitions, "
            "currency movements, and supplier payment timing.",
        ),
    ]:
        change = current[metric] - previous[metric]

        if pd.isna(change):
            add_check(title, None, "Ratio unavailable.", question)
        else:
            triggered = change < 0 if direction == "down" else change > 0
            add_check(
                title,
                triggered,
                f"{previous[metric]:.2f}% → {current[metric]:.2f}%. "
                f"Change: {change:+.2f} percentage points.",
                question,
            )

    report = pd.DataFrame(checks)
    status_order = {"Review": 0, "Unavailable": 1, "Not triggered": 2}

    st.caption(f"Comparing FY{review_year} with FY{review_year - 1}.")

    for item in sorted(checks, key=lambda row: status_order[row["Status"]]):
        with st.container(border=True):
            st.markdown(f"### {item['Rule']}")

            if item["Status"] == "Review":
                st.error("**TRIGGERED — Review needed**")
            elif item["Status"] == "Unavailable":
                st.warning("**UNAVAILABLE — Check the data**")
            else:
                st.markdown("**Status: Not triggered**")

            st.markdown(f"**Evidence:** {item['Evidence']}")

            # Show a compact chart only when this rule triggers.
            if item["Status"] == "Review":
                rule = item["Rule"]

                if rule == "Receivables outpace sales":
                    labels = ["Revenue growth", "Receivables growth"]
                    values = [
                        sales_growth,
                        growth_pct(
                            current["receivables"],
                            previous["receivables"],
                        ),
                    ]
                    axis_title = "Year-over-year growth (%)"

                elif rule == "Inventory outpaces sales":
                    labels = ["Revenue growth", "Inventory growth"]
                    values = [
                        sales_growth,
                        growth_pct(
                            current["inventory"],
                            previous["inventory"],
                        ),
                    ]
                    axis_title = "Year-over-year growth (%)"

                elif rule == "Operating margin declines":
                    labels = [
                        f"FY{review_year - 1}",
                        f"FY{review_year}",
                    ]
                    values = [
                        previous["Operating margin (%)"],
                        current["Operating margin (%)"],
                    ]
                    axis_title = "Operating margin (%)"

                elif rule == "Working-capital intensity rises":
                    labels = [
                        f"FY{review_year - 1}",
                        f"FY{review_year}",
                    ]
                    values = [
                        previous["Trade working capital / revenue (%)"],
                        current["Trade working capital / revenue (%)"],
                    ]
                    axis_title = "Trade working capital / revenue (%)"

                else:
                    labels = []
                    values = []

                if values and all(pd.notna(value) for value in values):
                    chart_data = pd.DataFrame({
                        "Label": labels,
                        "Value": values,
                        "Role": ["Comparison", "Flagged measure"],
                    })

                    fig = px.bar(
                        chart_data,
                        x="Label",
                        y="Value",
                        color="Role",
                        text="Value",
                        color_discrete_map={
                            "Comparison": "#60A5FA",
                            "Flagged measure": "#F87171",
                        },
                        category_orders={"Label": labels},
                    )

                    fig.update_traces(
                        texttemplate="%{y:.2f}%",
                        textposition="outside",
                        cliponaxis=False,
                        hovertemplate=(
                            "%{x}<br>%{y:.2f}%<extra></extra>"
                        ),
                    )

                    # Include zero and leave space for labels,
                    # including when growth is negative.
                    low = min(0.0, min(values))
                    high = max(0.0, max(values))
                    padding = max((high - low) * 0.20, 0.2)

                    fig.update_layout(
                        height=300,
                        showlegend=False,
                        bargap=0.55,
                        margin=dict(l=20, r=20, t=35, b=20),
                        xaxis_title=None,
                        yaxis_title=axis_title,
                        font=dict(size=14),
                    )

                    fig.update_xaxes(
                        tickangle=0,
                        automargin=True,
                        fixedrange=True,
                    )

                    fig.update_yaxes(
                        range=[
                            low - padding if low < 0 else 0,
                            high + padding,
                        ],
                        ticksuffix="%",
                        automargin=True,
                        fixedrange=True,
                    )

                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key=f"flag_chart_{ticker}_{review_year}_{rule}",
                    )

                    st.caption(
                        f"FY{review_year} versus FY{review_year - 1}. "
                        "Blue = comparison; red = flagged measure. "
                        "Red indicates a screening trigger, not severity."
                    )

            st.markdown(
                f"**Diligence question:** {item['Diligence question']}"
            )


    with st.expander("How to interpret these flags"):
        st.write(
            "Rules use unrounded values and trigger on any change in the "
            "specified direction. Small changes may not be material. "
            "'Not triggered' means only that this rule was not met."
        )
        st.write(
            "Rules can overlap. They do not detect every issue, including "
            "unusual improvements. MSC's extra week in FY2022 affects "
            "growth comparisons."
        )

    st.download_button(
        "Download diligence flags",
        data=report.to_csv(index=False).encode("utf-8"),
        file_name=f"{ticker}_{review_year}_diligence_flags.csv",
        mime="text/csv",
    )


# ---------- Tab 3: Research findings ----------

case_studies = [
    {
        "title": "Wesco · FY2025 · Growth absorbed cash",
        "facts": (
            "Operating cash flow fell from $1,101.2 million in 2024 "
            "to $125.0 million in 2025."
        ),
        "explanation": (
            "Management identified unfavorable year-over-year cash-flow "
            "effects of $507.3 million from trade receivables and "
            "$428.1 million from inventory. It cited sales growth, customer "
            "receipt timing, and inventory supporting large projects."
        ),
        "interpretation": (
            "Growth tied up funding. The movements do not establish customer "
            "defaults or inventory impairment; the timing and reliability "
            "of cash recovery need investigation."
        ),
        "question": (
            "Will collections and deliveries release this working capital, "
            "or will continued growth require further funding?"
        ),
        "limit": (
            "The cited effects are changes in cash-flow contributions, "
            "not simple balance-sheet differences."
        ),
        "source": "FY2025 Form 10-K · MD&A, cash-flow discussion, page 40",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/929008/"
            "000092900826000008/wcc-20251231.htm"
        ),
    },
    {
        "title": "MSC Industrial · FY2023 · Receivables sales boosted cash",
        "facts": (
            "Operating cash flow increased from approximately $246.2 million "
            "in FY2022 to $699.6 million in FY2023."
        ),
        "explanation": (
            "MSC attributed much of the increase to a new $300 million "
            "receivables-sale program. Sold receivables left the balance "
            "sheet, while the proceeds entered operating cash flow."
        ),
        "interpretation": (
            "The cash-conversion spike and lower receivables partly reflect "
            "this transaction. They should not be attributed solely to "
            "faster collections or repeatable operating improvement."
        ),
        "question": (
            "How much cash generation remains after separating the initial "
            "benefit? Review ongoing balances, fees, and renewal terms."
        ),
        "limit": (
            "The dashboard retains reported figures; no adjusted "
            "cash-flow estimate replaces them."
        ),
        "source": "FY2023 Form 10-K · Operating Activities and Note 5",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/1003078/"
            "000100307823000102/msm-20230902.htm"
        ),
    },
    {
        "title": "Grainger · FY2025 · Special charges affected margins",
        "facts": (
            "Reported operating margin declined from 15.36% in 2024 "
            "to 13.91% in 2025."
        ),
        "explanation": (
            "Management excluded $196 million associated with the Cromwell "
            "sale and Zoro U.K. closure in 2025, versus $16 million of "
            "restructuring costs in 2024. Adjusted operating earnings were "
            "$2,691 million and $2,653 million, respectively."
        ),
        "interpretation": (
            "Dividing those adjusted earnings by reported revenue gives "
            "margins of about 15.00% in 2025 and 15.45% in 2024. Special "
            "charges explain much, but not all, of the margin decline."
        ),
        "question": (
            "What explains the remaining pressure, and are management's "
            "exclusions appropriate for evaluating future earnings?"
        ),
        "limit": (
            "Adjusted margins are analyst calculations using management's "
            "adjusted earnings. They do not hold the business perimeter "
            "constant. Dashboard charts retain reported results."
        ),
        "source": "FY2025 Form 10-K · Non-GAAP reconciliation, page 33",
        "url": (
            "https://www.sec.gov/Archives/edgar/data/277135/"
            "000027713526000011/gww-20251231.htm"
        ),
    },
]

with research_tab:
    st.subheader("Research findings")
    st.caption(
        "All three case studies appear here, independent of the sidebar "
        "selection. These are manually researched notes, not automated conclusions."
    )

    st.markdown("**Priority for further cash-conversion diligence: Wesco**")
    st.write(
        "Among these selected cases, prioritize whether Wesco's FY2025 "
        "working-capital investment converts into cash as projects progress. "
        "Review collections, inventory commitments, and project cash timing."
    )
    st.caption(
        "A research priority is not a buy/sell recommendation or an "
        "acquisition valuation. These cases cover different fiscal periods."
    )

    for case in case_studies:
        with st.expander(case["title"]):
            st.markdown(f"**Reported facts:** {case['facts']}")
            st.markdown(f"**Filing explanation:** {case['explanation']}")
            st.markdown(
                f"**Our interpretation — preliminary:** {case['interpretation']}"
            )
            st.markdown(f"**Next diligence question:** {case['question']}")
            st.caption(case["limit"])
            st.markdown(f"[Source: {case['source']}]({case['url']})")

    st.caption(
        "Coverage: Wesco FY2025, MSC FY2023, and Grainger FY2025. "
        "Other company-years have not received a written review. "
        "These notes require manual review when the data is refreshed."
    )
