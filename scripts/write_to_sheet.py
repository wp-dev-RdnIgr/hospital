#!/usr/bin/env python3
"""Write extracted BIA data to Google Sheet, skipping patients that already exist."""

import json
import os
import subprocess
import sys
import csv
import io
import time

SPREADSHEET_ID = "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg"
SHEET_NAME = "Patientendaten"
SHEET_GID = "1199154574"
WEBHOOK_URL = "https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet"
EXTRACTED_DIR = "/home/user/hospital/extracted_data"


def read_existing_ids():
    """Read patient IDs already present in the Google Sheet."""
    result = subprocess.run([
        'curl', '-s', '-L',
        f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}',
        '--max-time', '15'
    ], capture_output=True, text=True)

    if not result.stdout.strip():
        print("ERROR: Could not read sheet data")
        sys.exit(1)

    reader = csv.reader(io.StringIO(result.stdout))
    rows = list(reader)

    existing = {}  # id -> row_number (1-indexed)
    last_data_row = 4  # header ends at row 4
    for i, row in enumerate(rows):
        if i < 4:
            continue
        pid = row[0].strip() if row and row[0].strip() else None
        if pid:
            existing[pid] = i + 1
            last_data_row = i + 1

    return existing, last_data_row


def load_extracted_patients():
    """Load all extracted patient data from JSON files."""
    patients = {}
    for fname in sorted(os.listdir(EXTRACTED_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(EXTRACTED_DIR, fname)
        with open(path) as f:
            data = json.load(f)
        patients[data['id']] = data
    return patients


def write_patient(patient, start_row):
    """Write a single patient to the sheet via webhook."""
    payload = json.dumps({
        "spreadsheetId": SPREADSHEET_ID,
        "sheetName": SHEET_NAME,
        "startRow": start_row,
        "patients": [patient]
    })

    result = subprocess.run([
        'curl', '-s', '-X', 'POST', WEBHOOK_URL,
        '-H', 'Content-Type: application/json',
        '-d', payload,
        '--max-time', '30'
    ], capture_output=True, text=True)

    try:
        resp = json.loads(result.stdout)
        return resp.get('success', False)
    except (json.JSONDecodeError, ValueError):
        print(f"  ERROR: {result.stdout[:200]}")
        return False


def main():
    dry_run = '--dry-run' in sys.argv

    print("Reading existing patients from sheet...")
    existing, last_data_row = read_existing_ids()
    print(f"  Found {len(existing)} patients, last data row: {last_data_row}")

    print("Loading extracted patient data...")
    extracted = load_extracted_patients()
    print(f"  Found {len(extracted)} patients in extracted_data/")

    # Find patients not yet in the sheet
    missing = {}
    for pid, data in extracted.items():
        if pid not in existing:
            missing[pid] = data

    if not missing:
        print("\nAll patients already in sheet. Nothing to write.")
        return

    print(f"\nMissing patients ({len(missing)}):")
    for pid in sorted(missing):
        p = missing[pid]
        print(f"  {pid}: {p['name']} ({len(p['operations'])} operations)")

    if dry_run:
        print("\n[DRY RUN] No data written.")
        return

    # Write missing patients, each takes 2 rows
    # Patients start on even rows (6, 8, 10, ...) in 1-indexed
    # last_data_row is the ID row, data row is last_data_row+1
    next_row = last_data_row + 2  # skip the data row of last patient

    print(f"\nWriting {len(missing)} patients starting at row {next_row}...")
    for pid in sorted(missing):
        patient = missing[pid]
        print(f"  Writing {pid} ({patient['name']}) at row {next_row}...", end='', flush=True)
        success = write_patient(patient, next_row)
        if success:
            print(" OK")
        else:
            print(" FAILED")
        next_row += 2  # each patient takes 2 rows
        time.sleep(1)

    print("\nDone!")


if __name__ == '__main__':
    main()
