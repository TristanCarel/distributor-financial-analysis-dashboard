import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

project = Path(__file__).parent
raw_folder = project / "data" / "raw"
raw_folder.mkdir(parents=True, exist_ok=True)

# Each company has its own SEC identifier.
companies = {
    "GWW": "0000277135",
    "MSM": "0001003078",
    "WCC": "0000929008",
}

email = input("Enter your contact email for SEC requests: ").strip()

if "@" not in email:
    raise SystemExit("Please run again with a valid contact email.")

headers = {
    "User-Agent": f"DistributorResearch/0.1 {email}",
    "Accept": "application/json",
}

for ticker, cik in companies.items():
    output_file = raw_folder / f"{ticker}_companyfacts.json"

    # Reuse existing downloads to avoid unnecessary requests.
    if output_file.exists():
        existing = json.loads(output_file.read_text(encoding="utf-8"))

        if int(existing["cik"]) != int(cik):
            raise ValueError(f"Unexpected company in {output_file.name}")

        print(f"{ticker}: using saved data")
        continue

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    print(f"{ticker}: downloading...")

    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()

    if int(data["cik"]) != int(cik):
        raise ValueError(f"Unexpected company returned for {ticker}")

    if "us-gaap" not in data.get("facts", {}):
        raise ValueError(f"No US accounting data found for {ticker}")

    output_file.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )

    # Record where and when this download came from.
    metadata = {
        "ticker": ticker,
        "cik": cik,
        "source_url": url,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    metadata_file = raw_folder / f"{ticker}_metadata.json"
    metadata_file.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"{ticker}: saved data for {data['entityName']}")

    # Leave a pause between requests to the SEC.
    time.sleep(1)

print("\nAll three company files are available.")