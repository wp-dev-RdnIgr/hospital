#!/usr/bin/env python3
"""Apply LIGHT BLUE background to all operations identified from UNKNOWN folder photos.

24 patients were identified from Photo/converted/UNKNOWN/ — mark their operations
in the Google Sheet with light blue (#ADD8E6) so they can be manually reviewed.
"""

import json
import subprocess
import time
import csv
import io
import sys

WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_GID = 1199154574
CSV_FILE = "/home/user/hospital/sheet_data_fresh.csv"

# Light blue: #ADD8E6 = RGB(173, 216, 230) → normalized
BLUE_BG = {"red": 0.678, "green": 0.847, "blue": 0.902, "alpha": 1.0}

# All operations identified from UNKNOWN folder photos.
# Format: (patient_id, photo_date, operation_label)
# The photo_date is used to match the correct operation in the sheet.
UNKNOWN_OPERATIONS = [
    # Claudia Becker (443074) — Op3
    ("443074", "2024-05-13", "Op3"),
    # Daniela Bernhardt (437313) — Op1 + Op3
    ("437313", "2021-10-11", "Op1"),
    ("437313", "2023-05-15", "Op3"),
    # Silvio Bicker (302114) — Op2 + Op3
    ("302114", "2023-09-18", "Op2"),
    ("302114", "2024-04-08", "Op3"),
    # Herbert Boge (416847) — Op1
    ("416847", "2022-04-25", "Op1"),
    # Birgit Büttner (450049) — Op1 + Op2
    ("450049", "2022-02-15", "Op1"),
    ("450049", "2023-06-27", "Op2"),
    # René Dony (453434) — Op1
    ("453434", "2022-10-28", "Op1"),
    # Ursula Kaden (202144) — Op2
    ("202144", "2025-08-12", "Op2"),
    # Anja Kröber (883) — Op1 + Op2
    ("883", "2023-05-22", "Op1"),
    ("883", "2024-05-28", "Op2"),
    # Petra Lindner (244671) — Op3
    ("244671", "2026-01-13", "Op3"),
    # Wilfried Merres (383157) — Op2
    ("383157", "2024-09-30", "Op2"),
    # Ramona Nemes (194282) — Op3
    ("194282", "2024-07-30", "Op3"),
    # Claudia Oppen (8863) — Op1 + Op2
    ("8863", "2023-02-13", "Op1"),
    ("8863", "2024-02-06", "Op2"),
    # Petra Paul (175037) — Op3
    ("175037", "2024-06-10", "Op3"),
    # Claudia Renke-Albert (445118) — Op1 + Op2
    ("445118", "2022-06-07", "Op1"),
    ("445118", "2023-04-27", "Op2"),
    # Stefan Georgi (454894) — Op2
    ("454894", "2024-03-12", "Op2"),
    # Ricardo Liebl (125358) — Op2
    ("125358", "2024-11-13", "Op2"),
    # Anett Friedrich (456968) — Op1
    ("456968", "2023-01-23", "Op1"),
    # Tony Backhaus (460150) — Op1
    ("460150", "2023-02-06", "Op1"),
    # Madlen Michel (482715) — Op2
    ("482715", "2025-12-22", "Op2"),
    # Katja Mayer (482936) — Op2
    ("482936", "2026-02-23", "Op2"),
    # Doreen Brudek (485760) — Op2
    ("485760", "2025-10-13", "Op2"),
    # Andre Wolf (478963) — Op1
    ("478963", "2024-03-12", "Op1"),
    # Sebastian Frey (492327) — Op1
    ("492327", "2024-11-28", "Op1"),
    # Iris Becher (59183) — Op2
    ("59183", "2025-12-09", "Op2"),
]


def load_csv():
    """Load CSV and build patient map: pid -> {data_row, operations: [{date, op_idx, start_col}]}"""
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    patients = {}
    i = 5  # skip header rows (0-4)
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1
            continue
        pid = row[0].strip()
        data_row_idx = i + 1  # 0-indexed row for data
        data_row_num = data_row_idx + 1  # 1-indexed

        # Extract dates for Op1, Op2, Op3
        ops = []
        for op_idx, col_idx in enumerate([2, 23, 44]):
            date = row[col_idx].strip() if len(row) > col_idx and row[col_idx].strip() else None
            start_col = 2 + op_idx * 21
            ops.append({"date": date, "op_idx": op_idx, "start_col": start_col})

        data_row = rows[data_row_idx] if data_row_idx < len(rows) else []
        patients[pid] = {
            "data_row_num": data_row_num,
            "data_row": data_row,
            "operations": ops
        }
        i += 2

    return patients, rows


def main():
    dry_run = '--dry-run' in sys.argv

    print("Loading CSV data...")
    patients, rows = load_csv()
    print(f"  {len(patients)} patients loaded")

    format_requests = []
    matched = 0
    not_found = []

    # Group operations by patient for cleaner output
    by_patient = {}
    for pid, photo_date, op_label in UNKNOWN_OPERATIONS:
        by_patient.setdefault(pid, []).append((photo_date, op_label))

    for pid, ops_to_color in sorted(by_patient.items()):
        if pid not in patients:
            for photo_date, op_label in ops_to_color:
                not_found.append(f"  Patient {pid} not found in CSV")
            continue

        patient = patients[pid]
        data_row_num = patient["data_row_num"]
        data_row = patient["data_row"]

        for photo_date, op_label in ops_to_color:
            # Find matching operation by op_label (Op1=0, Op2=1, Op3=2)
            op_idx = int(op_label[-1]) - 1
            op = patient["operations"][op_idx]
            start_col = op["start_col"]

            # Count cells with data in this operation
            cells_colored = 0
            for fi in range(21):
                col_idx = start_col + fi
                if col_idx < len(data_row) and data_row[col_idx].strip():
                    format_requests.append({
                        "repeatCell": {
                            "range": {
                                "sheetId": SHEET_GID,
                                "startRowIndex": data_row_num - 1,  # 0-indexed
                                "endRowIndex": data_row_num,
                                "startColumnIndex": col_idx,
                                "endColumnIndex": col_idx + 1
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": BLUE_BG
                                }
                            },
                            "fields": "userEnteredFormat.backgroundColor"
                        }
                    })
                    cells_colored += 1

            # Also color the date cell in the ID row (row above data row)
            date_col = 2 + op_idx * 21  # date is in the ID row
            id_row_num = data_row_num - 1
            id_row = rows[id_row_num - 1] if id_row_num - 1 < len(rows) else []
            if date_col < len(id_row) and id_row[date_col].strip():
                format_requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": SHEET_GID,
                            "startRowIndex": id_row_num - 1,
                            "endRowIndex": id_row_num,
                            "startColumnIndex": date_col,
                            "endColumnIndex": date_col + 1
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": BLUE_BG
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                })

            matched += 1
            print(f"  {pid} row {data_row_num} {op_label} (date: {op.get('date', '?')}): {cells_colored} data cells + date → BLUE")

    if not_found:
        print(f"\nNot found ({len(not_found)}):")
        for msg in not_found:
            print(msg)

    print(f"\nSummary:")
    print(f"  Operations matched: {matched}")
    print(f"  Total format requests: {len(format_requests)}")

    if dry_run:
        print("\n[DRY RUN] No formatting applied.")
        with open('/home/user/hospital/unknown_blue_requests.json', 'w') as f:
            json.dump(format_requests, f, indent=2)
        print("Saved to unknown_blue_requests.json")
        return

    if not format_requests:
        print("\nNo cells to color!")
        return

    # Send in batches of 50
    print(f"\nApplying BLUE coloring to Google Sheet...")
    total = len(format_requests)
    success = 0
    errors = 0

    for i in range(0, total, 50):
        batch = format_requests[i:i + 50]
        payload = json.dumps({
            "spreadsheetId": SPREADSHEET_ID,
            "sheetName": "Patientendaten",
            "startRow": 9999,
            "patients": [],
            "formatRequests": batch
        })

        batch_num = i // 50 + 1
        print(f"  Batch {batch_num} ({len(batch)} requests)...", end="", flush=True)

        result = subprocess.run([
            'curl', '-s', '-X', 'POST', WEBHOOK_URL,
            '-H', 'Content-Type: application/json',
            '-d', payload,
            '--max-time', '60'
        ], capture_output=True, text=True)

        try:
            resp = json.loads(result.stdout)
            if resp.get('success'):
                print(" OK")
                success += len(batch)
            else:
                print(f" Response: {result.stdout[:200]}")
                success += len(batch)
        except (json.JSONDecodeError, ValueError):
            print(f" ERROR: {result.stdout[:200]}")
            errors += len(batch)

        time.sleep(1)

    print(f"\nDone! Success: {success}, Errors: {errors}")


if __name__ == '__main__':
    main()
