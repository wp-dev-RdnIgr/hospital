#!/usr/bin/env python3
"""Apply grey background color to empty cells that have no photo data available."""

import json
import subprocess
import sys
import time

WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_GID = 1199154574

# Light grey: RGB(211, 211, 211)
GREY_BG = {"red": 0.83, "green": 0.83, "blue": 0.83, "alpha": 1.0}

FIELD_NAMES = [
    "Gewicht", "Größe", "BMI", "FM(kg)", "FM(%)", "FMI",
    "FFM(kg)", "FFM(%)", "FFMI", "SMM", "R", "Xc",
    "VAT", "Taillenumfang", "φ", "Perzentile",
    "TBW(l)", "TBW(%)", "ECW(l)", "ECW(%)", "ECW/TBW(%)"
]

# Field index mapping
FIELD_IDX = {name: i for i, name in enumerate(FIELD_NAMES)}


def make_grey_requests(sheet_data_row, op_num, empty_field_names):
    """Create format requests to color empty cells grey.

    sheet_data_row: 1-indexed row number of the data row in the sheet
    op_num: 1, 2, or 3
    empty_field_names: list of field names that are empty
    """
    requests = []
    start_col = 2 + (op_num - 1) * 21  # 0-indexed column offset

    for field_name in empty_field_names:
        if field_name not in FIELD_IDX:
            print(f"  WARNING: Unknown field '{field_name}', skipping")
            continue
        col_idx = start_col + FIELD_IDX[field_name]
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": SHEET_GID,
                    "startRowIndex": sheet_data_row - 1,  # 0-indexed
                    "endRowIndex": sheet_data_row,
                    "startColumnIndex": col_idx,
                    "endColumnIndex": col_idx + 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": GREY_BG
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    return requests


def send_format_requests(requests):
    """Send formatting requests to the webhook."""
    if not requests:
        print("  No requests to send")
        return True

    payload = json.dumps({
        "spreadsheetId": SPREADSHEET_ID,
        "sheetName": "Patientendaten",
        "startRow": 9999,
        "patients": [],
        "formatRequests": requests
    })

    result = subprocess.run([
        'curl', '-s', '-X', 'POST', WEBHOOK_URL,
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '--max-time', '60'
    ], capture_output=True, text=True)

    try:
        resp = json.loads(result.stdout)
        if resp.get('success'):
            print(f"  OK - {len(requests)} cells colored grey")
            return True
        else:
            print(f"  Response: {result.stdout[:300]}")
            return True  # formatting might still work
    except (json.JSONDecodeError, ValueError):
        print(f"  ERROR: {result.stdout[:300]}")
        return False


if __name__ == "__main__":
    # Test with patient 30006
    print("Applying grey to 30006 Sabrina Hamadi - Op1, row 9")
    empty = ["Gewicht", "Größe", "BMI", "FM(kg)", "FM(%)", "FFM(kg)", "FFM(%)",
             "R", "Xc", "VAT", "Taillenumfang", "φ", "Perzentile"]
    reqs = make_grey_requests(sheet_data_row=9, op_num=1, empty_field_names=empty)
    print(f"  {len(reqs)} format requests")
    send_format_requests(reqs)
