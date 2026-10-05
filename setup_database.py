import sqlite3
from pathlib import Path

# Store the database beside this Python file.
database_path = Path(__file__).parent / "research.db"

# Open the database, creating it if it doesn't exist.
connection = sqlite3.connect(database_path)

# SQL: create a table to hold our company list.
connection.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        ticker TEXT PRIMARY KEY,
        company_name TEXT NOT NULL,
        business_focus TEXT NOT NULL
    )
""")

# Our initial research companies.
companies = [
    ("GWW", "W.W. Grainger", "Industrial and MRO supplies"),
    ("MSM", "MSC Industrial", "Metalworking and MRO supplies"),
    ("WCC", "Wesco International", "Electrical and infrastructure distribution"),
]

# SQL: insert each company, or update it if it already exists.
connection.executemany("""
    INSERT INTO companies (ticker, company_name, business_focus)
    VALUES (?, ?, ?)
    ON CONFLICT(ticker) DO UPDATE SET
        company_name = excluded.company_name,
        business_focus = excluded.business_focus
""", companies)

connection.commit()

# SQL: retrieve the company list alphabetically by ticker.
rows = connection.execute("""
    SELECT ticker, company_name
    FROM companies
    ORDER BY ticker
""").fetchall()

for ticker, company_name in rows:
    print(f"{ticker}: {company_name}")

connection.close()
print("Database ready.")