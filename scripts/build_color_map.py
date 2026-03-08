#!/usr/bin/env python3
"""Build a comprehensive map of cells to color based on confidence levels.

Confidence levels:
- HIGH (no color): JSON extracted from photo matches CSV exactly
- MEDIUM (light yellow): Data in CSV but no JSON verification, or small discrepancies (<1.0)
- LOW (light red): Large discrepancies (>1.0), patients without JSON, no photo verification

Output: JSON file with list of cells to color, suitable for Google Sheets API.
"""

import json
import os
import csv
import io
import sys

EXTRACTED_DIR = "/home/user/hospital/extracted_data"
CSV_FILE = "/home/user/hospital/sheet_data_fresh.csv"
PHOTO_DIR = "/home/user/hospital/Photo/converted"

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
    """Returns dict: patient_id -> {name, row_number (1-indexed), operations: [{date, fields, data_row}]}"""
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    patients = {}
    patient_order = []  # to preserve row order
    i = 5  # data starts at row 6 (0-indexed: 5)
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1
            continue

        pid = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""
        id_row = i + 1  # 1-indexed row number in sheet

        # Parse dates
        dates = []
        for col_idx in [2, 23, 44]:
            if len(row) > col_idx and row[col_idx].strip():
                dates.append(row[col_idx].strip())
            else:
                dates.append(None)

        # Next row has data values
        data_row_idx = i + 1
        data_row = rows[data_row_idx] if data_row_idx < len(rows) else []
        data_row_num = data_row_idx + 1  # 1-indexed

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

            operations.append({
                "date": date,
                "fields": fields,
                "start_col": start_col  # 0-indexed column in sheet
            })

        patients[pid] = {
            "name": name,
            "id_row": id_row,
            "data_row": data_row_num,
            "operations": operations
        }
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


def has_photos(pid):
    """Check if patient has photos in converted directory."""
    path = os.path.join(PHOTO_DIR, str(pid))
    return os.path.isdir(path) and len(os.listdir(path)) > 0


def col_index_to_letter(col_idx):
    """Convert 0-indexed column to sheet letter (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    while col_idx >= 0:
        result = chr(65 + col_idx % 26) + result
        col_idx = col_idx // 26 - 1
    return result


def main():
    print("Loading data...")
    csv_data, patient_order = load_csv_data()
    json_data = load_json_data()

    print(f"CSV: {len(csv_data)} patients, JSON: {len(json_data)} patients")

    # Cells to color: list of {row, col, color, reason, pid, field, values}
    cells_to_color = []

    stats = {"high": 0, "medium": 0, "low": 0, "empty": 0}

    for pid in patient_order:
        csv_patient = csv_data[pid]
        json_patient = json_data.get(pid)
        data_row = csv_patient['data_row']
        photos_exist = has_photos(pid)

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
                    stats["empty"] += 1
                    continue  # no data to verify

                # Determine confidence
                if json_patient is None:
                    # No JSON extraction at all for this patient
                    if not photos_exist:
                        confidence = "low"
                        reason = "No JSON extraction, no photos"
                    else:
                        confidence = "low"
                        reason = "No JSON extraction (photos exist but unverified)"
                elif json_op is None:
                    # JSON exists but not for this operation date
                    confidence = "medium"
                    reason = f"No JSON data for date {csv_op['date']}"
                else:
                    json_val = json_op['fields'][fi] if fi < len(json_op['fields']) else None
                    if json_val is None:
                        # JSON extraction couldn't read this field
                        confidence = "medium"
                        reason = f"JSON extraction missing for {FIELD_NAMES[fi]}"
                    else:
                        diff = abs(json_val - csv_val)
                        if diff < 0.05:
                            confidence = "high"
                            reason = "Match"
                            stats["high"] += 1
                            continue  # no coloring needed
                        elif diff < 1.0:
                            confidence = "medium"
                            reason = f"Small diff: JSON={json_val}, CSV={csv_val}, diff={diff:.2f}"
                        else:
                            confidence = "low"
                            reason = f"Large diff: JSON={json_val}, CSV={csv_val}, diff={diff:.2f}"

                stats[confidence] += 1
                col_letter = col_index_to_letter(col_idx)
                cells_to_color.append({
                    "row": data_row,
                    "col": col_idx,
                    "col_letter": col_letter,
                    "cell": f"{col_letter}{data_row}",
                    "color": confidence,
                    "reason": reason,
                    "pid": pid,
                    "name": csv_patient['name'],
                    "op": op_idx + 1,
                    "field": FIELD_NAMES[fi],
                    "csv_val": csv_val
                })

    # Summary
    print(f"\n{'='*80}")
    print(f"CONFIDENCE SUMMARY")
    print(f"{'='*80}")
    print(f"High confidence (no color): {stats['high']}")
    print(f"Medium confidence (yellow): {stats['medium']}")
    print(f"Low confidence (red):       {stats['low']}")
    print(f"Empty cells (skipped):      {stats['empty']}")
    print(f"Total cells to color:       {len(cells_to_color)}")

    # Breakdown by color
    yellow_cells = [c for c in cells_to_color if c['color'] == 'medium']
    red_cells = [c for c in cells_to_color if c['color'] == 'low']

    print(f"\n--- RED cells (low confidence): {len(red_cells)} ---")
    for c in red_cells:
        print(f"  {c['cell']}: {c['pid']} ({c['name']}) Op{c['op']} {c['field']} = {c['csv_val']} | {c['reason']}")

    print(f"\n--- YELLOW cells (medium confidence): {len(yellow_cells)} ---")
    for c in yellow_cells[:50]:
        print(f"  {c['cell']}: {c['pid']} ({c['name']}) Op{c['op']} {c['field']} = {c['csv_val']} | {c['reason']}")
    if len(yellow_cells) > 50:
        print(f"  ... and {len(yellow_cells) - 50} more")

    # Save for coloring
    output = {
        "stats": stats,
        "cells_to_color": cells_to_color,
        "yellow_cells": [c['cell'] for c in yellow_cells],
        "red_cells": [c['cell'] for c in red_cells],
    }

    output_path = '/home/user/hospital/color_map.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nColor map saved to {output_path}")


if __name__ == '__main__':
    main()
