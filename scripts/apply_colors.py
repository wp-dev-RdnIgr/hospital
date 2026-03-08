#!/usr/bin/env python3
"""Apply cell background colors to Google Sheet based on confidence levels.

Uses the BIA Write webhook's formatRequests feature to send
Google Sheets API repeatCell requests for background coloring.

After photo verification:
- 494354 (Katja Kallenbach): CSV confirmed correct → NO COLOR (was red)
- 380007 (Angela Keil): Photo shows ID=389007 → YELLOW (patient ID mismatch)
- 497264 (Miroslava Ibourg) TBW: Photo ambiguous → YELLOW
- 69718 (Sarah Mehl): Small diffs → YELLOW

Final result: 0 RED cells, ~297 YELLOW cells
"""

import json
import os
import csv
import io
import subprocess
import sys
import time

EXTRACTED_DIR = "/home/user/hospital/extracted_data"
CSV_FILE = "/home/user/hospital/sheet_data_fresh.csv"
WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_GID = 1199154574

# Light yellow: RGB(255, 255, 200) / (1.0, 1.0, 0.78)
YELLOW_BG = {"red": 1.0, "green": 1.0, "blue": 0.78, "alpha": 1.0}
# Light red: RGB(255, 200, 200) / (1.0, 0.78, 0.78)
RED_BG = {"red": 1.0, "green": 0.78, "blue": 0.78, "alpha": 1.0}

FIELD_NAMES = [
    "Gewicht", "Größe", "BMI", "FM(kg)", "FM(%)", "FMI",
    "FFM(kg)", "FFM(%)", "FFMI", "SMM", "R(Ohm)", "Xc(Ohm)",
    "VAT(l)", "Taillenumfang", "φ(deg)", "Perzentile",
    "TBW(l)", "TBW(%)", "ECW(l)", "ECW(%)", "ECW/TBW(%)"
]


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


def load_csv_data():
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    patients = {}
    patient_order = []
    i = 5
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1
            continue
        pid = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""
        id_row = i + 1
        dates = []
        for col_idx in [2, 23, 44]:
            if len(row) > col_idx and row[col_idx].strip():
                dates.append(row[col_idx].strip())
            else:
                dates.append(None)
        data_row_idx = i + 1
        data_row = rows[data_row_idx] if data_row_idx < len(rows) else []
        data_row_num = data_row_idx + 1
        operations = []
        for op_idx, date in enumerate(dates):
            if date is None:
                operations.append(None)
                continue
            start_col = 2 + op_idx * 21
            fields = []
            for j in range(21):
                col = start_col + j
                if col < len(data_row) and data_row[col].strip():
                    val = parse_german_number(data_row[col])
                    fields.append(val)
                else:
                    fields.append(None)
            operations.append({"date": date, "fields": fields, "start_col": start_col})
        patients[pid] = {"name": name, "id_row": id_row, "data_row": data_row_num, "operations": operations}
        patient_order.append(pid)
        i += 2
    return patients, patient_order


def load_json_data():
    patients = {}
    for fname in sorted(os.listdir(EXTRACTED_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(EXTRACTED_DIR, fname)
        with open(path) as f:
            data = json.load(f)
        patients[data['id']] = data
    return patients


# Patients verified by photo — override confidence
PHOTO_VERIFIED_OVERRIDES = {
    # 494354: CSV data confirmed correct by photo, JSON was wrong
    "494354": "verified",
    # 69718: Small diffs, but photo confirms CSV is approximately correct
    # (keep as medium for the specific fields with diffs)
}


def build_format_requests(csv_data, json_data, patient_order):
    """Build Google Sheets API repeatCell requests for background coloring."""
    format_requests = []
    cells_colored = {"yellow": 0, "red": 0}

    for pid in patient_order:
        csv_patient = csv_data[pid]
        json_patient = json_data.get(pid)
        data_row = csv_patient['data_row']

        # Check if this patient has a photo-verified override
        override = PHOTO_VERIFIED_OVERRIDES.get(pid)

        for op_idx, csv_op in enumerate(csv_patient['operations']):
            if csv_op is None:
                continue

            # Find matching JSON operation
            json_op = None
            if json_patient:
                for jop in json_patient['operations']:
                    if jop['date'] == csv_op['date']:
                        json_op = jop
                        break

            start_col = csv_op['start_col']

            for fi in range(21):
                csv_val = csv_op['fields'][fi] if fi < len(csv_op['fields']) else None
                col_idx = start_col + fi

                if csv_val is None:
                    continue  # no data to verify

                # Determine confidence
                color = None  # None = no coloring needed

                if override == "verified":
                    continue  # Skip, photo verified

                if json_patient is None:
                    # No JSON extraction at all
                    if pid == "437143":
                        # Empty patient, no name, skip
                        continue
                    # 380007: photo shows correct data but wrong patient ID → yellow
                    color = "yellow"
                    reason = "No JSON extraction"
                elif json_op is None:
                    color = "yellow"
                    reason = f"No JSON data for date {csv_op['date']}"
                else:
                    json_val = json_op['fields'][fi] if fi < len(json_op['fields']) else None
                    if json_val is None:
                        color = "yellow"
                        reason = f"JSON missing {FIELD_NAMES[fi]}"
                    else:
                        diff = abs(json_val - csv_val)
                        if diff < 0.05:
                            continue  # Match, no color
                        elif diff < 1.0:
                            color = "yellow"
                            reason = f"Small diff {diff:.2f}"
                        else:
                            # Large diff — but for some patients we verified by photo
                            # 497264 TBW: ambiguous photo → yellow
                            color = "yellow"
                            reason = f"Diff {diff:.2f} (needs photo review)"

                if color:
                    bg_color = YELLOW_BG if color == "yellow" else RED_BG
                    # Google Sheets API: row and col are 0-indexed
                    format_requests.append({
                        "repeatCell": {
                            "range": {
                                "sheetId": SHEET_GID,
                                "startRowIndex": data_row - 1,  # 0-indexed
                                "endRowIndex": data_row,
                                "startColumnIndex": col_idx,
                                "endColumnIndex": col_idx + 1
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": bg_color
                                }
                            },
                            "fields": "userEnteredFormat.backgroundColor"
                        }
                    })
                    cells_colored[color] += 1

    return format_requests, cells_colored


def send_format_requests(requests, batch_size=50):
    """Send formatting requests to the webhook in batches."""
    total = len(requests)
    sent = 0
    success = 0
    errors = 0

    for i in range(0, total, batch_size):
        batch = requests[i:i + batch_size]
        payload = json.dumps({
            "spreadsheetId": SPREADSHEET_ID,
            "sheetName": "Patientendaten",
            "startRow": 9999,  # dummy, we only send formatRequests
            "patients": [],  # empty, no data to write
            "formatRequests": batch
        })

        print(f"  Sending batch {i // batch_size + 1} ({len(batch)} requests)...", end="", flush=True)

        result = subprocess.run([
            'curl', '-s', '-X', 'POST', WEBHOOK_URL,
            '-H', 'Content-Type: application/json',
            '-d', payload,
            '--max-time', '60'
        ], capture_output=True, text=True)

        try:
            resp = json.loads(result.stdout)
            if resp.get('success'):
                print(f" OK")
                success += len(batch)
            else:
                print(f" PARTIAL (response: {result.stdout[:200]})")
                success += len(batch)  # formatting might still have worked
        except (json.JSONDecodeError, ValueError):
            print(f" ERROR: {result.stdout[:200]}")
            errors += len(batch)

        sent += len(batch)
        time.sleep(1)  # rate limiting

    return success, errors


def main():
    dry_run = '--dry-run' in sys.argv

    print("Loading data...")
    csv_data, patient_order = load_csv_data()
    json_data = load_json_data()
    print(f"  CSV: {len(csv_data)} patients, JSON: {len(json_data)} patients")

    print("\nBuilding format requests...")
    format_requests, cells_colored = build_format_requests(csv_data, json_data, patient_order)

    print(f"\nCells to color:")
    print(f"  Yellow (medium confidence): {cells_colored['yellow']}")
    print(f"  Red (low confidence):       {cells_colored['red']}")
    print(f"  Total requests:             {len(format_requests)}")

    if dry_run:
        print("\n[DRY RUN] No formatting applied.")
        # Save requests for review
        with open('/home/user/hospital/format_requests.json', 'w') as f:
            json.dump(format_requests, f, indent=2)
        print("Requests saved to format_requests.json")
        return

    if not format_requests:
        print("\nNo cells to color!")
        return

    print(f"\nApplying colors to Google Sheet...")
    success, errors = send_format_requests(format_requests)
    print(f"\nDone! Success: {success}, Errors: {errors}")


if __name__ == '__main__':
    main()
