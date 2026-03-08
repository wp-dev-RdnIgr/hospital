#!/usr/bin/env python3
"""Compare extracted JSON data with sheet CSV data to find discrepancies."""

import json
import os
import csv
import io
import sys

EXTRACTED_DIR = "/home/user/hospital/extracted_data"
CSV_FILE = "/home/user/hospital/sheet_data_fresh.csv"

FIELD_NAMES = [
    "Gewicht", "Größe", "BMI", "FM(kg)", "FM(%)", "FMI",
    "FFM(kg)", "FFM(%)", "FFMI", "SMM", "R(Ohm)", "Xc(Ohm)",
    "VAT(l)", "Taillenumfang", "φ(deg)", "Perzentile",
    "TBW(l)", "TBW(%)", "ECW(l)", "ECW(%)", "ECW/TBW(%)"
]


def parse_german_number(s):
    """Parse German-format number (comma as decimal sep)."""
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
    """Load patient data from CSV. Returns dict: patient_id -> {name, operations: [{date, fields}]}"""
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    patients = {}
    i = 5  # data starts at row 6 (0-indexed: 5)
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1
            continue

        pid = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""

        # Parse dates from columns: col 2 (op1), col 23 (op2), col 44 (op3)
        dates = []
        for col_idx in [2, 23, 44]:
            if len(row) > col_idx and row[col_idx].strip():
                dates.append(row[col_idx].strip())
            else:
                dates.append(None)

        # Next row has the data values
        data_row = rows[i + 1] if i + 1 < len(rows) else []

        operations = []
        for op_idx, date in enumerate(dates):
            if date is None:
                operations.append(None)
                continue

            # Fields start at col 2 + op_idx*21 in the data row
            start_col = 2 + op_idx * 21
            fields = []
            for j in range(21):
                col = start_col + j
                if col < len(data_row) and data_row[col].strip():
                    val = parse_german_number(data_row[col])
                    fields.append(val)
                else:
                    fields.append(None)

            operations.append({"date": date, "fields": fields})

        patients[pid] = {"name": name, "operations": operations}
        i += 2  # skip data row

    return patients


def load_json_data():
    """Load all extracted JSON data."""
    patients = {}
    for fname in sorted(os.listdir(EXTRACTED_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(EXTRACTED_DIR, fname)
        with open(path) as f:
            data = json.load(f)
        patients[data['id']] = data
    return patients


def compare_values(json_val, csv_val, tolerance=0.05):
    """Compare two values. Returns: 'match', 'mismatch', 'json_only', 'csv_only', 'both_empty'"""
    if json_val is None and csv_val is None:
        return 'both_empty'
    if json_val is not None and csv_val is None:
        return 'json_only'
    if json_val is None and csv_val is not None:
        return 'csv_only'
    # Both have values
    if abs(json_val - csv_val) < tolerance:
        return 'match'
    return 'mismatch'


def find_matching_op(json_ops, csv_date):
    """Find JSON operation matching CSV date."""
    for op in json_ops:
        if op['date'] == csv_date:
            return op
    return None


def main():
    print("Loading CSV data...")
    csv_data = load_csv_data()
    print(f"  {len(csv_data)} patients in CSV")

    print("Loading JSON data...")
    json_data = load_json_data()
    print(f"  {len(json_data)} patients in JSON")

    # Track issues
    mismatches = []
    json_only_values = []
    csv_only_no_json = []  # patients in CSV but no JSON file
    missing_photos = []  # patients with JSON but no photos at all

    total_fields = 0
    matched_fields = 0
    mismatch_fields = 0
    csv_only_fields = 0  # CSV has data, JSON doesn't
    json_only_fields = 0

    for pid, csv_patient in sorted(csv_data.items()):
        json_patient = json_data.get(pid)

        if json_patient is None:
            csv_only_no_json.append(pid)
            # Count non-empty CSV fields
            for op in csv_patient['operations']:
                if op:
                    for fv in op['fields']:
                        if fv is not None:
                            csv_only_fields += 1
                            total_fields += 1
            continue

        # Compare operations
        for op_idx, csv_op in enumerate(csv_patient['operations']):
            if csv_op is None:
                continue

            json_op = find_matching_op(json_patient['operations'], csv_op['date'])
            if json_op is None:
                # Try converting date format
                # CSV date might be YYYY-MM-DD or DD.MM.YYYY etc
                json_op_found = False
                for jop in json_patient['operations']:
                    # Check if dates match in any format
                    csv_d = csv_op['date']
                    json_d = jop['date']
                    if csv_d == json_d:
                        json_op = jop
                        json_op_found = True
                        break

                if not json_op_found:
                    # CSV has data for a date that JSON doesn't have
                    for fi, fv in enumerate(csv_op['fields']):
                        if fv is not None:
                            csv_only_fields += 1
                            total_fields += 1
                    continue

            # Compare field by field
            for fi in range(21):
                csv_val = csv_op['fields'][fi] if fi < len(csv_op['fields']) else None
                json_val = json_op['fields'][fi] if fi < len(json_op['fields']) else None

                result = compare_values(json_val, csv_val)
                total_fields += 1

                if result == 'match':
                    matched_fields += 1
                elif result == 'mismatch':
                    mismatch_fields += 1
                    mismatches.append({
                        'pid': pid,
                        'name': csv_patient['name'],
                        'op_idx': op_idx + 1,
                        'date': csv_op['date'],
                        'field': FIELD_NAMES[fi],
                        'field_idx': fi,
                        'json_val': json_val,
                        'csv_val': csv_val,
                        'diff': abs(json_val - csv_val)
                    })
                elif result == 'json_only':
                    json_only_fields += 1
                    json_only_values.append({
                        'pid': pid,
                        'name': csv_patient['name'],
                        'op_idx': op_idx + 1,
                        'date': csv_op['date'],
                        'field': FIELD_NAMES[fi],
                        'json_val': json_val
                    })
                elif result == 'csv_only':
                    csv_only_fields += 1

    # Report
    print(f"\n{'='*80}")
    print(f"COMPARISON RESULTS")
    print(f"{'='*80}")
    print(f"Total fields compared: {total_fields}")
    print(f"  Matched: {matched_fields} ({matched_fields/max(total_fields,1)*100:.1f}%)")
    print(f"  Mismatched: {mismatch_fields} ({mismatch_fields/max(total_fields,1)*100:.1f}%)")
    print(f"  CSV only (no JSON): {csv_only_fields}")
    print(f"  JSON only (not in CSV): {json_only_fields}")
    print(f"  Patients in CSV but no JSON file: {len(csv_only_no_json)}")

    if csv_only_no_json:
        print(f"\n--- Patients WITHOUT JSON extraction ---")
        for pid in csv_only_no_json:
            print(f"  {pid}: {csv_data[pid]['name']}")

    if mismatches:
        print(f"\n--- MISMATCHES (total: {len(mismatches)}) ---")
        for m in sorted(mismatches, key=lambda x: x['diff'], reverse=True):
            print(f"  {m['pid']} ({m['name']}) Op{m['op_idx']} [{m['date']}] "
                  f"{m['field']}: JSON={m['json_val']} vs CSV={m['csv_val']} (diff={m['diff']:.2f})")

    if json_only_values:
        print(f"\n--- JSON has data but CSV is empty ({len(json_only_values)} fields) ---")
        for j in json_only_values[:50]:
            print(f"  {j['pid']} ({j['name']}) Op{j['op_idx']} [{j['date']}] "
                  f"{j['field']}: JSON={j['json_val']}")

    # Save detailed report as JSON for later processing
    report = {
        'summary': {
            'total_fields': total_fields,
            'matched': matched_fields,
            'mismatched': mismatch_fields,
            'csv_only': csv_only_fields,
            'json_only': json_only_fields,
            'patients_no_json': csv_only_no_json
        },
        'mismatches': mismatches,
        'json_only_values': json_only_values[:100]
    }

    report_path = '/home/user/hospital/comparison_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed report saved to {report_path}")


if __name__ == '__main__':
    main()
