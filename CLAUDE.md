# Hospital Project Notes

## HEIC Photo Conversion Method

When converting HEIC photos for reading/analysis, use this approach:
- Convert HEIC -> JPEG using `pillow` + `pillow-heif` (pip install pillow pillow-heif)
- Full resolution, quality=95, subsampling=0
- Save to `Photo/converted/` folder
- This produces readable, high-quality results
- **Max confirmed viewable file size:** ~12 MB (JPEG). Tested successfully on IMG_4537.jpg (12 MB)

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
- **n8n Workflow ID:** `oOXNiOsuAABXtTrZ`
- **Target Spreadsheet:** `1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg`
- **Target Sheet GID:** `1199154574`
- **Sheet Tab Name:** `Patientendaten`
- **Google Sheets Credential:** `googleSheetsOAuth2Api` ID=`hMp9ISVYVcdpImYl` (name: "Google Sheets account")

### Usage — structured patient data:

```json
{
  "spreadsheetId": "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg",
  "sheetName": "Patientendaten",
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

## n8n Access Credentials

- **n8n Base URL:** `https://n8n.rnd.webpromo.tools`
- **n8n API Key:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8`
- **MCP Server URL:** `https://n8n.rnd.webpromo.tools/mcp-server/http`
- **MCP Access Token:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjJmYWMzY2JlLTRkM2UtNDY1MC05YzgwLTFhOWNhOGZjOTdlMCIsImlhdCI6MTc2ODgyNjU0N30.wEpv9lvPPq0cmccRzv1MPMJ4SM2Cmw0cMjL1dDBUlt4`
- **Hospital folder workflows** are in: Personal / Test-flow / Hospital

Always use `X-N8N-API-KEY` header with the API Key for REST API calls to n8n.

## Current Task — Верификация данных таблицы по фото + цветовая маркировка

### Goal
Проверить ВСЕ данные в Google Sheet (Patientendaten) по фото BIA-отчётов из `Photo/converted/`. Пометить ячейки цветом по уровню уверенности:
- **Светло-красный** — низкая уверенность (данные скорее всего неправильные / от другого пациента)
- **Светло-жёлтый** — средняя уверенность (не удалось проверить по фото / мелкие расхождения)
- **Без цвета** — высокая уверенность (JSON из фото совпадает с CSV)

### Status (2026-03-08)
- [x] Скачаны данные из Google Sheet → `sheet_data_fresh.csv` (190 пациентов, 384 строки)
- [x] Сравнение JSON-извлечений (188 файлов) с CSV: **91.7% совпадение** (8571 из 9342 полей)
- [x] Проверка расхождений по фото (494354 — CSV правильный, JSON был неверный)
- [x] Проверка консистентности роста → **8 пациентов с несовпадением роста** (данные другого пациента!)
- [x] Закрашены **295 жёлтых ячеек** (средняя уверенность)
- [x] Закрашены **156 красных ячеек** (низкая уверенность — данные другого пациента)

### Результаты верификации

#### КРАСНЫЕ ячейки (156 шт.) — данные скорее всего от ДРУГОГО пациента:

| Пациент | Строка | Операция | Проблема |
|---------|--------|----------|----------|
| 151150 Nico Weinigel | 49 | Op3 | Рост 164 vs 180 cm (diff=16!) |
| 141154 Daniel Sanchez-Almeida | 43 | Op1 | Рост 182 vs 168 cm (diff=14!) |
| 90056 Sabrina Hamadi | 27 | Op1 | Рост 155 vs 165 cm (diff=10!) |
| 39221 Lutz Dittmann | 13 | Op1 | Рост 189 vs 180.4 cm (diff=8.6!) |
| 59183 Iris Becher | 17 | Op3 | Рост 172 vs 165 cm (diff=7!) |
| 97934 Dandy Menzel | 29 | Op3 | Рост 166 vs 173 cm (diff=7!) |
| 443074 Claudia Becker | 181 | Op2 | Рост 159 vs 165 cm (diff=6!) |
| 32514 Claudia Puhlfuerst | 11 | Op1 | Рост 167.1 vs 172 cm (diff=4.9) |

#### ЖЁЛТЫЕ ячейки (295 шт.) — не проверено по фото:

| Причина | Кол-во ячеек |
|---------|-------------|
| Нет JSON-данных для даты операции (фото отсутствуют или не извлечены) | ~280 |
| Мелкие расхождения JSON/CSV (<1.0) | ~5 |
| Нет JSON-извлечения вообще (380007) | ~9 |

#### Пациенты с жёлтыми ячейками:
32514, 39221, 48951, 59183, 69718, 97934, 141154, 151150, 165656, 494354, 1614978, 380007

### Скрипты верификации

| Скрипт | Назначение |
|--------|-----------|
| `scripts/compare_json_csv.py` | Сравнение JSON-извлечений с CSV таблицы |
| `scripts/build_color_map.py` | Построение карты ячеек для закраски |
| `scripts/apply_colors.py` | Применение жёлтой закраски через webhook |
| `scripts/apply_red_colors.py` | Применение красной закраски (несовпадение роста) |
| `scripts/check_height_consistency.py` | Проверка консистентности роста между операциями |

### Файлы с результатами

| Файл | Содержание |
|------|-----------|
| `comparison_report.json` | Детальный отчёт сравнения JSON vs CSV |
| `color_map.json` | Карта ячеек для закраски (координаты + причины) |
| `format_requests.json` | Запросы форматирования для Google Sheets API |

---

## Предыдущая задача — BIA Pipeline: Read Photos -> Extract Data -> Write to Google Sheet

### n8n Workflows — Актуальные

| Workflow | ID | Webhook path | Назначение |
|----------|----|-------------|------------|
| **BIA Write to Google Sheet** (NEW) | `8jb5CD0AuC5oXW8K` | `bia-write-sheet` | Запись BIA данных + форматирование |
| **BIA Write to Google Sheet** (OLD) | `oOXNiOsuAABXtTrZ` | `bia-write-sheet` | Старая версия без форматирования (КОНФЛИКТ путей!) |
| Hospital - List Drive Folders v5 | `X86NI7GW2JnQZdfq` | `list-drive-folders-v5` | Листинг папок Drive |
| Hospital - Download Folder Files | `3tXFkXxsG06izpaA` | `download-folder-files` | Скачивание файлов из Drive |
| Hospital - List Folder Files Only | `fnyPmXPx7j9E0MwM` | `list-folder-files` | Список файлов в папке |
| Hospital - List Folders Simple | `jEaVIVJwlMFINKm1` | `list-folders-simple` | Простой список папок |
| Hospital - Write Queue to Sheet | `YcRGMBKfFvCrn6rI` | `write-queue-sheet` | Запись очереди в Sheet |

### Known Issues
1. **Merge cells conflict**: workflow `8jb5CD0AuC5oXW8K` падает на шаге Apply Formatting, потому что пытается объединить ячейки, которые уже объединены. Нужно добавить unmergeCells перед mergeCells.
2. **Webhook path conflict**: оба BIA-воркфлоу (`8jb5CD0AuC5oXW8K` и `oOXNiOsuAABXtTrZ`) используют путь `bia-write-sheet`. Нужно деактивировать старый.
