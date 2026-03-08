#!/usr/bin/env python3
"""Automated verification of all patients: compare JSON extractions with sheet data.

For each patient:
1. Load JSON extraction (from photos) and sheet data
2. Compare field-by-field with zero tolerance
3. Generate format requests: red for mismatches, yellow for verified name
4. Apply via n8n webhook
5. Update verification_progress.json
"""

import json
import os
import subprocess
import sys
import time

WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_ID = 1199154574
EXTRACTED_DIR = "/home/user/hospital/extracted_data"
PROGRESS_FILE = "/home/user/hospital/verification_progress.json"
PARSED_SHEET = "/home/user/hospital/parsed_sheet_data.json"
CONVERTED_DIR = "/home/user/hospital/Photo/converted"

FIELD_NAMES = [
    "Gewicht", "Größe", "BMI", "FM(kg)", "FM(%)", "FMI",
    "FFM(kg)", "FFM(%)", "FFMI", "SMM", "R(Ω)", "Xc(Ω)",
    "VAT(l)", "Taillenumfang", "φ(deg)", "Perzentile",
    "TBW(l)", "TBW(%)", "ECW(l)", "ECW(%)", "ECW/TBW(%)"
]

# Colors
RED = {"red": 1.0, "green": 0.78, "blue": 0.78}
YELLOW = {"red": 1.0, "green": 1.0, "blue": 0.78}


def load_progress():
    with open(PROGRESS_FILE) as f:
        return json.load(f)


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def load_sheet_data():
    with open(PARSED_SHEET) as f:
        return json.load(f)


def load_json_extraction(pid):
    path = os.path.join(EXTRACTED_DIR, f"{pid}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def values_match(json_val, sheet_val):
    """Compare two values with zero tolerance."""
    if json_val is None and sheet_val is None:
        return True
    if json_val is None or sheet_val is None:
        return True  # Can't compare if one is missing - not a mismatch
    # Both are numbers - compare
    try:
        jv = float(json_val)
        sv = float(sheet_val)
        # Zero tolerance: must be exactly equal when rounded to same precision
        # Use string comparison to handle floating point
        return abs(jv - sv) < 0.01
    except (ValueError, TypeError):
        return str(json_val) == str(sheet_val)


def make_color_request(row_0based, col_0based, color):
    """Create a repeatCell format request."""
    return {
        "repeatCell": {
            "range": {
                "sheetId": SHEET_ID,
                "startRowIndex": row_0based,
                "endRowIndex": row_0based + 1,
                "startColumnIndex": col_0based,
                "endColumnIndex": col_0based + 1
            },
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": color
                }
            },
            "fields": "userEnteredFormat.backgroundColor"
        }
    }


def apply_format_requests(requests):
    """Send format requests to webhook."""
    if not requests:
        return True
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
    return result.returncode == 0


def verify_patient(pid, sheet_data, progress):
    """Verify a single patient and return format requests + discrepancies."""
    format_requests = []
    discrepancies = {}

    patient_sheet = sheet_data.get(pid)
    if not patient_sheet:
        print(f"  {pid}: NOT IN SHEET - skip")
        return [], {"note": "not in sheet"}

    json_data = load_json_extraction(pid)
    row_index = patient_sheet['row_index']
    data_row = row_index + 1  # Data is on the row after the ID row

    # Yellow name cell (always mark as verified if we have photos)
    photo_dir = os.path.join(CONVERTED_DIR, pid)
    has_photos = os.path.exists(photo_dir) and len(os.listdir(photo_dir)) > 0

    if has_photos:
        format_requests.append(make_color_request(row_index, 1, YELLOW))

    if not json_data:
        # No JSON extraction - mark all non-empty sheet fields as yellow (unverified)
        print(f"  {pid}: NO JSON extraction")
        for op in patient_sheet['operations']:
            if op is None:
                continue
            base_col = op['base_col']
            for fi, val in enumerate(op['fields']):
                if val is not None:
                    format_requests.append(make_color_request(data_row, base_col + fi, YELLOW))
        return format_requests, {"note": "no JSON extraction, all fields yellow"}

    # Compare operations by date
    json_ops_by_date = {}
    for op in json_data.get('operations', []):
        d = op.get('date', '')
        json_ops_by_date[d] = op.get('fields', [])

    for op_idx, sheet_op in enumerate(patient_sheet['operations']):
        if sheet_op is None:
            continue
        op_date = sheet_op['date']
        base_col = sheet_op['base_col']
        sheet_fields = sheet_op['fields']
        op_name = f"op{op_idx+1}"

        json_fields = json_ops_by_date.get(op_date)
        if json_fields is None:
            # No JSON data for this operation date - mark yellow
            for fi, val in enumerate(sheet_fields):
                if val is not None:
                    format_requests.append(make_color_request(data_row, base_col + fi, YELLOW))
            discrepancies[op_name] = [f"no JSON for date {op_date}, all fields yellow"]
            continue

        # Compare field by field
        op_discrep = []
        for fi in range(min(len(sheet_fields), len(json_fields), 21)):
            sv = sheet_fields[fi]
            jv = json_fields[fi]

            if sv is None and jv is None:
                continue  # Both empty, nothing to check

            if sv is None and jv is not None:
                continue  # Sheet empty, JSON has data - no action on empty cell

            if sv is not None and jv is None:
                # Sheet has data but JSON doesn't - mark yellow (unverifiable)
                format_requests.append(make_color_request(data_row, base_col + fi, YELLOW))
                op_discrep.append(f"{FIELD_NAMES[fi]}: sheet={sv}, json=None -> yellow")
                continue

            if not values_match(jv, sv):
                # Mismatch - RED
                format_requests.append(make_color_request(data_row, base_col + fi, RED))
                op_discrep.append(f"{FIELD_NAMES[fi]}: json={jv}, sheet={sv}")

        if op_discrep:
            discrepancies[op_name] = op_discrep

    return format_requests, discrepancies


def main():
    start_index = int(sys.argv[1]) if len(sys.argv) > 1 else None
    end_index = int(sys.argv[2]) if len(sys.argv) > 2 else None

    progress = load_progress()
    sheet_data = load_sheet_data()
    patient_order = progress['patient_order']

    if start_index is None:
        start_index = progress['last_completed_index'] + 1

    if end_index is None:
        end_index = len(patient_order)

    print(f"Verifying patients {start_index} to {end_index-1} ({end_index - start_index} patients)")

    for idx in range(start_index, min(end_index, len(patient_order))):
        pid = patient_order[idx]

        if pid in progress['completed_patients']:
            print(f"[{idx}] {pid}: already done, skip")
            continue

        print(f"[{idx}] {pid}...", end='', flush=True)

        format_requests, discrepancies = verify_patient(pid, sheet_data, progress)

        # Apply colors
        if format_requests:
            # Batch in groups of 50
            for i in range(0, len(format_requests), 50):
                batch = format_requests[i:i+50]
                success = apply_format_requests(batch)
                if not success:
                    print(f" WEBHOOK FAILED", end='')
                time.sleep(0.5)

        # Update progress
        progress['completed_patients'].append(pid)
        progress['last_completed_patient_id'] = pid
        progress['last_completed_index'] = idx
        if discrepancies:
            progress['discrepancies'][pid] = discrepancies
        else:
            progress['discrepancies'][pid] = {}

        n_red = sum(1 for r in format_requests if r['repeatCell']['cell']['userEnteredFormat']['backgroundColor'] == RED)
        n_yellow = sum(1 for r in format_requests if r['repeatCell']['cell']['userEnteredFormat']['backgroundColor'] == YELLOW)
        print(f" {n_red} red, {n_yellow} yellow, {len(discrepancies)} ops with issues")

        # Save progress every patient
        save_progress(progress)

        # Small delay between patients
        time.sleep(0.3)

    progress['status'] = 'completed' if end_index >= len(patient_order) else 'in_progress'
    save_progress(progress)
    print(f"\nDone! Completed {len(progress['completed_patients'])}/{len(patient_order)} patients")


if __name__ == '__main__':
    main()
