import sqlite3
import subprocess
import sys
from pathlib import Path

project = Path(__file__).resolve().parent

steps = [
    ("Prepare company database", "setup_database.py"),
    ("Check SEC downloads", "fetch_financials.py"),
    ("Load annual financials", "load_companies.py"),
    ("Load working-capital data", "load_working_capital.py"),
    ("Validate the dataset", "validate_data.py"),
]

# Check that every script exists before starting.
for description, filename in steps:
    if not (project / filename).is_file():
        raise SystemExit(f"Missing script: {filename}")

# Ensure the financial table exists, including on a fresh setup.
with sqlite3.connect(project / "research.db") as connection:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS annual_financials (
            ticker TEXT NOT NULL,
            year INTEGER NOT NULL,
            metric TEXT NOT NULL,
            value_usd REAL,
            source_tag TEXT,
            filed TEXT,
            accession TEXT,
            PRIMARY KEY (ticker, year, metric)
        )
    """)

for number, (description, filename) in enumerate(steps, start=1):
    print(
        f"\n[{number}/{len(steps)}] {description}",
        flush=True,
    )

    result = subprocess.run(
        [sys.executable, str(project / filename)],
        cwd=project,
    )

    if result.returncode != 0:
        raise SystemExit(
            f"\nStopped: {filename} did not finish successfully. "
            "Check the error above before continuing."
        )

print("\nSUCCESS: All pipeline steps and validation checks passed.")
print("Your dashboard data is ready.")