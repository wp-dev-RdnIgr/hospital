import csv
import json

with open('/home/user/hospital/sheet_data_fresh.csv', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Row 4 (0-indexed=3) has field names, Row 5 has units
# Row 6+ has data (alternating: patient header, data row)
# Structure: PatID, Name, then 3 operations x 21 fields each + date row

field_names = [
    "Gewicht", "Groesse", "BMI", "FM_kg", "FM_pct", "FMI",
    "FFM_kg", "FFM_pct", "FFMI", "SMM", "R", "Xc",
    "VAT", "Taillenumfang", "phi", "Perzentile",
    "TBW_l", "TBW_pct", "ECW_l", "ECW_pct", "ECW_TBW_pct"
]

patients = {}
reader = csv.reader(lines)
all_rows = list(reader)

# Data starts at row 6 (0-indexed=5)
i = 5
while i < len(all_rows) - 1:
    header_row = all_rows[i]
    data_row = all_rows[i + 1]
    
    pat_id = header_row[0].strip()
    pat_name = header_row[1].strip()
    
    if not pat_id or pat_id == '':
        i += 1
        continue
    
    # Dates for 3 operations
    op1_date = header_row[2].strip() if len(header_row) > 2 else ""
    op2_date = header_row[23].strip() if len(header_row) > 23 else ""
    op3_date = header_row[44].strip() if len(header_row) > 44 else ""
    
    patient = {
        "id": pat_id,
        "name": pat_name,
        "operations": []
    }
    
    for op_idx, (date, col_start) in enumerate([(op1_date, 2), (op2_date, 23), (op3_date, 44)]):
        if not date:
            continue
        
        fields = {}
        for j, fname in enumerate(field_names):
            col = col_start + j
            if col < len(data_row):
                val = data_row[col].strip().replace(',', '.')
                if val:
                    try:
                        fields[fname] = float(val)
                    except ValueError:
                        fields[fname] = val
        
        if fields:
            patient["operations"].append({
                "op_num": op_idx + 1,
                "date": date,
                "fields": fields
            })
    
    if patient["operations"]:
        patients[pat_id] = patient
    
    i += 2

print(f"Parsed {len(patients)} patients")
for pid, p in list(patients.items())[:3]:
    print(f"\n{pid} - {p['name']}:")
    for op in p['operations']:
        print(f"  Op{op['op_num']} ({op['date']}): {len(op['fields'])} fields")
        print(f"    Gewicht={op['fields'].get('Gewicht')}, Groesse={op['fields'].get('Groesse')}, BMI={op['fields'].get('BMI')}")

with open('/home/user/hospital/parsed_patients.json', 'w') as f:
    json.dump(patients, f, indent=2, ensure_ascii=False)

print(f"\nSaved to parsed_patients.json")

# Also list all patient folders
import os
folders = sorted(os.listdir('/home/user/hospital/Photo/converted/'))
print(f"\nPhoto folders: {len(folders)}")

# Check which patients have photos but not in CSV and vice versa
csv_ids = set(patients.keys())
photo_ids = set(folders)
print(f"In CSV but no photos: {csv_ids - photo_ids}")
print(f"In photos but no CSV: {photo_ids - csv_ids}")
