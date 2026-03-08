#!/usr/bin/env python3
"""Check height consistency across operations for each patient.
Height should be constant (or very close) across all operations.
If height varies significantly, it suggests data from the wrong patient."""

import csv
import io

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

def main():
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    problems = []
    i = 5
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1
            continue
        pid = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""
        data_row = rows[i + 1] if i + 1 < len(rows) else []

        # Get heights from each operation (col index: Op1=3, Op2=24, Op3=45)
        heights = []
        dates = []
        for op_idx, (height_col, date_col) in enumerate([(3, 2), (24, 23), (45, 44)]):
            date = row[date_col].strip() if len(row) > date_col and row[date_col].strip() else None
            height = parse_german_number(data_row[height_col]) if len(data_row) > height_col else None
            if date and height:
                heights.append(height)
                dates.append((op_idx + 1, date, height))

        if len(heights) >= 2:
            min_h = min(heights)
            max_h = max(heights)
            diff = max_h - min_h
            if diff > 2.0:  # More than 2cm difference is suspicious
                problems.append({
                    'pid': pid,
                    'name': name,
                    'row': i + 1,
                    'data_row': i + 2,
                    'heights': dates,
                    'diff': diff
                })

        i += 2

    print(f"Height consistency check: {len(problems)} patients with issues\n")
    for p in sorted(problems, key=lambda x: x['diff'], reverse=True):
        print(f"  {p['pid']} ({p['name']}) row {p['data_row']}:")
        for op, date, h in p['heights']:
            print(f"    Op{op} [{date}]: {h} cm")
        print(f"    MAX DIFF: {p['diff']:.1f} cm")
        print()

if __name__ == '__main__':
    main()
