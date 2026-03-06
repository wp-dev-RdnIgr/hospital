# Hospital Project Notes

## HEIC Photo Conversion Method

When converting HEIC photos for reading/analysis, use this approach:
- Convert HEIC -> JPEG using `pillow` + `pillow-heif` (pip install pillow pillow-heif)
- Full resolution, quality=95, subsampling=0
- Save to `Photo/converted/` folder
- This produces readable, high-quality results

```python
from pillow_heif import register_heif_opener
from PIL import Image
import os

register_heif_opener()

src_dir = "/home/user/hospital/Photo"
out_dir = "/home/user/hospital/Photo/converted"
os.makedirs(out_dir, exist_ok=True)

for fname in sorted(os.listdir(src_dir)):
    if fname.upper().endswith(".HEIC"):
        path = os.path.join(src_dir, fname)
        img = Image.open(path)
        out_name = fname.rsplit(".", 1)[0] + ".jpg"
        out_path = os.path.join(out_dir, out_name)
        img.save(out_path, "JPEG", quality=95, subsampling=0)
```

## BIA Write to Google Sheet — n8n Webhook

After importing the workflow `BIA_Write_to_Sheet_workflow.json` into n8n (Hospital folder), use this webhook to write BIA data to the Google Sheet:

- **Webhook URL (production):** `https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet`
- **Method:** POST
- **Target Spreadsheet:** `1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg`
- **Target Sheet GID:** `1199154574`

### Usage — structured patient data:

```json
{
  "spreadsheetId": "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg",
  "sheetGid": 1199154574,
  "sheetName": "BIA",
  "startRow": 6,
  "patients": [
    {
      "id": "126915",
      "name": "Anja Ostwald",
      "operations": [
        {
          "date": "2025-01-15",
          "fields": [63.35, 157.8, 25.44, 12.18, 19.2, 4.9, 51.17, 80.8, 20.6, 20.96, 466.5, 38.4, 0.01, 71.0, 4.7, 9, 37.5, 58.9, 18.1, 28.3, 48.1]
        }
      ]
    }
  ]
}
```

**Field order (21 fields per operation):**
Gewicht(kg), Groesse(cm), BMI, FM(kg), FM(%), FMI, FFM(kg), FFM(%), FFMI, SMM(kg), R(Ohm), Xc(Ohm), VAT(l), Taillenumfang(cm), phi(deg), Perzentile, TBW(l), TBW(%), ECW(l), ECW(%), ECW/TBW(%)
