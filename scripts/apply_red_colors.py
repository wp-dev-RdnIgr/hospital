#!/usr/bin/env python3
"""Apply RED background to operations with wrong patient data (height mismatch).

These operations have height values that differ significantly from other operations
of the same patient, suggesting data from a different patient was entered.
"""

import json
import subprocess
import time
import csv
import io

WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_GID = 1199154574

# Light red: RGB(255, 200, 200) / (1.0, 0.78, 0.78)
RED_BG = {"red": 1.0, "green": 0.78, "blue": 0.78, "alpha": 1.0}

CSV_FILE = "/home/user/hospital/sheet_data_fresh.csv"

def parse_german_number(s):
    if s is None:
        return None
    s = s.strip().replace(' ', '')
    if not s or s == '-':
        return None
    s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None

# Operations to mark RED (entire operation row, all 21 fields)
# Format: (pid, data_row_num_1indexed, op_index_0based, reason)
# The "outlier" operation is the one with the different height
RED_OPERATIONS = [
    ("151150", 49, 2, "Op3: height 164 vs 180 cm (diff=16)"),
    ("141154", 43, 0, "Op1: height 182 vs 168 cm (diff=14)"),
    ("90056", 27, 0, "Op1: height 155 vs 165 cm (diff=10)"),
    ("39221", 13, 0, "Op1: height 189 vs 180.4 cm (diff=8.6)"),
    ("59183", 17, 2, "Op3: height 172 vs 165 cm (diff=7)"),
    ("97934", 29, 2, "Op3: height 166 vs 173 cm (diff=7)"),
    ("443074", 181, 1, "Op2: height 159 vs 165 cm (diff=6)"),
    ("32514", 11, 0, "Op1: height 167.1 vs 172 cm (diff=4.9)"),
]


def main():
    # Read CSV to check which cells actually have data
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    format_requests = []

    for pid, data_row, op_idx, reason in RED_OPERATIONS:
        start_col = 2 + op_idx * 21
        csv_row = rows[data_row - 1] if data_row - 1 < len(rows) else []

        fields_colored = 0
        for fi in range(21):
            col_idx = start_col + fi
            # Check if cell has data
            if col_idx < len(csv_row) and csv_row[col_idx].strip():
                format_requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": SHEET_GID,
                            "startRowIndex": data_row - 1,
                            "endRowIndex": data_row,
                            "startColumnIndex": col_idx,
                            "endColumnIndex": col_idx + 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": RED_BG
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                })
                fields_colored += 1

        print(f"  {pid} row {data_row} Op{op_idx+1}: {fields_colored} cells → RED | {reason}")

    print(f"\nTotal RED format requests: {len(format_requests)}")

    # Send
    payload = json.dumps({
        "spreadsheetId": SPREADSHEET_ID,
        "sheetName": "Patientendaten",
        "startRow": 9999,
        "patients": [],
        "formatRequests": format_requests
    })

    print("Sending RED formatting...")
    result = subprocess.run([
        'curl', '-s', '-X', 'POST', WEBHOOK_URL,
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '--max-time', '60'
    ], capture_output=True, text=True)

    try:
        resp = json.loads(result.stdout)
        if resp.get('success'):
            print("OK — RED colors applied!")
        else:
            print(f"Response: {result.stdout[:300]}")
    except (json.JSONDecodeError, ValueError):
        print(f"ERROR: {result.stdout[:300]}")


if __name__ == '__main__':
    main()
