#!/usr/bin/env python3
"""Find patients with empty cells in the sheet data."""
import csv
import json

FIELDS = [
    "Gewicht", "Größe", "BMI", "FM(kg)", "FM(%)", "FMI",
    "FFM(kg)", "FFM(%)", "FFMI", "SMM", "R", "Xc",
    "VAT", "Taillenumfang", "φ", "Perzentile",
    "TBW(l)", "TBW(%)", "ECW(l)", "ECW(%)", "ECW/TBW(%)"
]

def parse_sheet():
    with open("/home/user/hospital/sheet_data_fresh.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    patients = []
    # Data starts at row 6 (0-indexed), pairs of rows
    i = 5  # row 6 in 1-indexed = index 5
    while i < len(rows) - 1:
        header_row = rows[i]
        data_row = rows[i + 1]

        patient_id = header_row[0].strip() if len(header_row) > 0 else ""
        patient_name = header_row[1].strip() if len(header_row) > 1 else ""

        if not patient_id:
            i += 2
            continue

        # 3 operations, each with date + 21 fields (but date is in header row, fields in data row)
        # Header row: col2 = Op1 date, col23 = Op2 date, col44 = Op3 date
        # Data row: col2-22 = Op1 fields (21), col23-43 = Op2 fields (21), col44-64 = Op3 fields (21)

        ops = []
        for op_idx in range(3):
            date_col = 2 + op_idx * 21
            data_start = 2 + op_idx * 21

            op_date = header_row[date_col].strip() if len(header_row) > date_col else ""

            if not op_date:
                continue

            # Extract 21 data fields
            fields_data = {}
            has_any = False
            empty_fields = []
            filled_fields = []

            for j, field_name in enumerate(FIELDS):
                col = data_start + j
                val = data_row[col].strip() if len(data_row) > col else ""
                fields_data[field_name] = val
                if val:
                    has_any = True
                    filled_fields.append(field_name)
                else:
                    empty_fields.append(field_name)

            if has_any and empty_fields:
                # This operation has partial data
                ops.append({
                    "op_num": op_idx + 1,
                    "date": op_date,
                    "empty_fields": empty_fields,
                    "filled_fields": filled_fields,
                    "empty_count": len(empty_fields),
                    "filled_count": len(filled_fields),
                    "sheet_row": i + 2  # 1-indexed row of data (i+1 for 0-index, +1 for 1-indexed)
                })
            elif not has_any:
                # All fields empty - entire operation empty
                ops.append({
                    "op_num": op_idx + 1,
                    "date": op_date,
                    "empty_fields": FIELDS.copy(),
                    "filled_fields": [],
                    "empty_count": 21,
                    "filled_count": 0,
                    "all_empty": True,
                    "sheet_row": i + 2
                })

        if ops:
            has_gaps = any(op.get("empty_count", 0) > 0 and op.get("empty_count", 0) < 21 for op in ops)
            has_fully_empty = any(op.get("all_empty", False) for op in ops)

            patients.append({
                "id": patient_id,
                "name": patient_name,
                "operations": ops,
                "has_partial_data": has_gaps,
                "has_fully_empty_ops": has_fully_empty
            })

        i += 2

    return patients

patients = parse_sheet()

# Summary
print("=== PATIENTS WITH EMPTY CELLS ===\n")

# First show patients with PARTIAL data (some filled, some empty) - most interesting
partial = [p for p in patients if p["has_partial_data"]]
fully_empty = [p for p in patients if p["has_fully_empty_ops"] and not p["has_partial_data"]]

print(f"Patients with PARTIAL data (gaps to fill): {len(partial)}")
print(f"Patients with FULLY EMPTY operations: {len(fully_empty)}")
print()

print("--- PARTIAL DATA (priority - check photos) ---")
for p in partial:
    for op in p["operations"]:
        if 0 < op["empty_count"] < 21:
            print(f"\n{p['id']} {p['name']} - Op{op['op_num']} ({op['date']})")
            print(f"  Filled ({op['filled_count']}): {', '.join(op['filled_fields'])}")
            print(f"  Empty ({op['empty_count']}): {', '.join(op['empty_fields'])}")
            print(f"  Sheet data row: {op['sheet_row']}")

print("\n\n--- FULLY EMPTY OPERATIONS ---")
for p in patients:
    for op in p["operations"]:
        if op.get("all_empty"):
            print(f"{p['id']} {p['name']} - Op{op['op_num']} ({op['date']}) - ALL 21 fields empty (row {op['sheet_row']})")

# Save to JSON for processing
result = {
    "partial_data_patients": partial,
    "fully_empty_patients": fully_empty,
    "all_patients_with_gaps": patients
}
with open("/home/user/hospital/empty_cells_analysis.json", "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"\n\nSaved analysis to empty_cells_analysis.json")
