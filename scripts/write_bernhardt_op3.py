#!/usr/bin/env python3
"""Write Daniela Bernhardt (437313) Op3 data to Google Sheet.

The blue cells are empty because the n8n workflow crashed on merge cells.
This script writes data directly via updateCells batchUpdate requests
through the webhook's formatRequests parameter (same mechanism that
successfully applied blue coloring).
"""

import json
import subprocess
import sys

WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_ID = 1199154574

# Bernhardt is at CSV row 178 (1-indexed), which is 0-indexed row 177
# Date row = 177, Data row = 178
DATE_ROW = 177  # 0-indexed
DATA_ROW = 178  # 0-indexed

# Op3 starts at column 44 (0-indexed)
# Cols 0-1: ID, Name
# Cols 2-22: Op1 (col 2 = date, cols 2-22 = 21 data fields)
# Cols 23-43: Op2
# Cols 44-64: Op3
OP3_DATE_COL = 44
OP3_DATA_START = 44

# Data from CLAUDE.md:
# Gewicht=77.4, Größe=160, BMI=30.25, FM=25.92, FM%=33.5, FMI=10.1,
# FFM=51.48, FFM%=66.5, FFMI=20.1, SMM=21.57, R=491.2, Xc=36.6,
# VAT=0.7, WC=93, φ=4.3, Perz=1, TBW=37.91, TBW%=49.0,
# ECW=18.51, ECW%=23.9, ECW/TBW=48.8
OP3_DATE = "2023-05-15"
OP3_VALUES = [
    77.4, 160, 30.25, 25.92, 33.5, 10.1,
    51.48, 66.5, 20.1, 21.57, 491.2, 36.6,
    0.7, 93, 4.3, 1, 37.91, 49.0,
    18.51, 23.9, 48.8
]


def make_update_cells_request(row_0based, col_start, values, is_date=False):
    """Create an updateCells batchUpdate request."""
    cells = []
    for v in values:
        if is_date:
            cells.append({"userEnteredValue": {"stringValue": str(v)}})
        elif isinstance(v, (int, float)):
            cells.append({"userEnteredValue": {"numberValue": v}})
        else:
            cells.append({"userEnteredValue": {"stringValue": str(v)}})

    return {
        "updateCells": {
            "range": {
                "sheetId": SHEET_ID,
                "startRowIndex": row_0based,
                "endRowIndex": row_0based + 1,
                "startColumnIndex": col_start,
                "endColumnIndex": col_start + len(values)
            },
            "rows": [{"values": cells}],
            "fields": "userEnteredValue"
        }
    }


def send_requests(requests):
    """Send batchUpdate requests via webhook."""
    payload = {
        "spreadsheetId": SPREADSHEET_ID,
        "formatRequests": requests
    }
    result = subprocess.run([
        'curl', '-s', '-X', 'POST', WEBHOOK_URL,
        '-H', 'Content-Type: application/json',
        '-d', json.dumps(payload),
        '--max-time', '30'
    ], capture_output=True, text=True)
    print(f"Response: {result.stdout[:500]}")
    return result.returncode == 0


def main():
    dry_run = '--dry-run' in sys.argv

    print(f"Writing Daniela Bernhardt (437313) Op3 data")
    print(f"  Date: {OP3_DATE} -> row {DATE_ROW}, col {OP3_DATE_COL}")
    print(f"  Data: {len(OP3_VALUES)} values -> row {DATA_ROW}, cols {OP3_DATA_START}-{OP3_DATA_START + len(OP3_VALUES) - 1}")
    print(f"  Values: {OP3_VALUES}")

    requests = [
        # Write date
        make_update_cells_request(DATE_ROW, OP3_DATE_COL, [OP3_DATE], is_date=True),
        # Write data values
        make_update_cells_request(DATA_ROW, OP3_DATA_START, OP3_VALUES),
    ]

    if dry_run:
        print("\n[DRY RUN] Requests:")
        print(json.dumps(requests, indent=2))
        return

    print("\nSending to webhook...")
    success = send_requests(requests)
    print(f"Result: {'OK' if success else 'FAILED'}")


if __name__ == '__main__':
    main()
