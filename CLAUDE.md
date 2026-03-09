# Hospital Project Notes

## Current Task — Заполнение пустых ячеек по фото (2026-03-09)

### Goal
Найти все пустые ячейки у пациентов в таблице, проверить фото в папке каждого пациента, заполнить данные или пометить серым.

### Algorithm
1. Определить пустые ячейки у пациента
2. Проверить фото в папке `Photo/converted/{patient_id}/`
3. Если данные найдены → записать в таблицу через webhook
4. Если данных нет → пометить серым цветом
5. Перейти к следующему пациенту

### Status: ЗАВЕРШЕНО (2026-03-09)
- **Всего пациентов с пробелами:** 44 (43 частичных + 1 полностью пустой)
- **Обработано:** 44/44 ✅

### Результаты
- **Данные найдены и записаны:** ~30 пациентов (полностью или частично заполнены пустые ячейки)
- **Помечено серым (данных нет в фото):** ~14 пациентов (отсутствующие страницы BIA-отчёта)
- **Найдены фото в UNKNOWN:** IMG_4071 и IMG_4072 опознаны как страницы 2 и 3 для 444571 Katrin Barth Op2

### Ключевые находки
- 237025 Nadine Plottke: Op2 был полностью пустой (21 поле) — все 3 страницы найдены, все заполнены
- 445118 Claudia Renke-Albert: Op1 и Op2 — страницы 3 найдены, все 12 полей заполнены
- 444571 Katrin Barth: Op2 — 12 полей заполнены из UNKNOWN-фото (IMG_4071, IMG_4072)
- Несколько пациентов с отсутствующими страницами 1 или 3 помечены серым

### Patients Queue (по порядку)
1. 30006 Sabrina Hamadi - Op1 (13 empty)
2. 39221 Lutz Dittmann - Op2 (6 empty)
3. 72296 Sabrina Reichelt - Op1 (15 empty)
4. 72298 Sabrina Liebig - Op1 (6 empty)
5. 90056 Sabrina Hamadi - Op1 (6 empty), Op3 (6 empty)
6. 125358 Ricardo Liebl - Op2 (6 empty)
7. 147096 Juliane Folganty - Op1 (15 empty)
8. 151150 Nico Weinigel - Op3 (6 empty)
9. 1614978 Unknown - Op1 (13 empty)
10. 165656 Sandra Stark - Op1 (13 empty)
11. 166566 Sandra Stark - Op3 (12 empty)
12. 168566 Sandra Stark - Op1 (15 empty)
13. 175037 Petra Paul - Op3 (9 empty)
14. 244671 Petra Lindner - Op3 (6 empty)
15. 441882 Lidija Barjamovic - Op1 (12 empty), Op2 (12 empty)
16. 450049 Birgit Büttner - Op1 (12 empty), Op2 (15 empty)
17. 380007 Angela Keil - Op1 (12 empty)
18. 416847 Herbert Boge - Op1 (15 empty)
19. 437313 Daniela Bernhardt - Op1 (6 empty)
20. 443074 Claudia Becker - Op3 (15 empty)
21. 453434 René Dony - Op1 (15 empty)
22. 456968 Anett Friedrich - Op1 (6 empty)
23. 190716 Ellen Kroll - Op3 (6 empty)
24. 194282 Ramona Nemes - Op3 (6 empty)
25. 202144 Ursula Kaden - Op1 (13 empty)
26. 233002 Simone Gessner - Op1 (12 empty)
27. 292144 Ursula Kaden - Op1 (6 empty), Op2 (6 empty)
28. 302114 Silvio Bicker - Op2 (15 empty), Op3 (6 empty)
29. 383157 Wilfried Merres - Op2 (6 empty)
30. 407407 Jasmin Germann - Op1 (12 empty)
31. 439155 Ramona Weisse - Op2 (6 empty)
32. 444571 Katrin Barth - Op1 (6 empty), Op2 (12 empty)
33. 445118 Claudia Renke-Albert - Op1 (6 empty), Op2 (6 empty)
34. 453451 Elke Rössel - Op1 (12 empty)
35. 454894 Stefan Georgi - Op2 (6 empty)
36. 478963 Andre Wolf - Op1 (9 empty)
37. 482715 Madlen Michel - Op2 (6 empty)
38. 482936 Katja Mayer - Op2 (7 empty)
39. 485760 Doreen Brudek - Op2 (6 empty)
40. 487487 Jasmin Germann - Op1 (7 empty)
41. 489265 Heidi Glaser - Op2 (1 empty)
42. 492327 Sebastian Frey - Op1 (6 empty)
43. 460150 Tony Backhaus - Op1 (6 empty)
44. 237025 Nadine Plottke - Op2 (21 empty - fully empty)

---

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

## Current Task — Сопоставление фото из UNKNOWN с пациентами в таблице (2026-03-09)

### Goal
Просканировать фото из `Photo/converted/UNKNOWN/`, сопоставить по имени с пациентами в таблице, внести новые данные, подкрасить голубым, переместить фото.

### Status (2026-03-09)
- [x] Просканировано **53 фото** из папки UNKNOWN
- [x] **46 фото опознаны** → 24 пациента
- [x] **7 фото НЕ опознаны** (страницы 2-3 без имени) → остались в UNKNOWN
- [x] Найдены **2 новых записи** для таблицы:
  - **Daniela Bernhardt (437313)** — Op3, 15.05.2023 — полный набор (21 поле)
  - **Ursula Kaden (202144)** — Op2, 12.08.2025 — частичные данные (8 из 21 полей, только стр.2)
- [x] Данные записаны в Google Sheet через webhook
- [x] Ячейки подкрашены **голубым** (#ADD8E6)
- [x] 46 фото перемещены в папки пациентов
- [x] 7 неопознанных фото остались в UNKNOWN

### Детали: опознанные фото

| Пациент (ID) | Фото | Дата BIA | Статус в таблице |
|--------------|------|----------|------------------|
| Claudia Becker (443074) | IMG_4110-4111 | 13.05.2024 | Уже в Op3 |
| Daniela Bernhardt (437313) | IMG_4119 | 11.10.2021 | Уже в Op1 |
| Daniela Bernhardt (437313) | IMG_4124-4126 | 15.05.2023 | **НОВОЕ → Op3** ✅ |
| Silvio Bicker (302114) | IMG_4236-4237 | 18.09.2023 | Уже в Op2 |
| Silvio Bicker (302114) | IMG_4240 | 08.04.2024 | Уже в Op3 |
| Herbert Boge (416847) | IMG_4242-4243 | 25.04.2022 | Уже в Op1 |
| Birgit Büttner (450049) | IMG_4246-4247 | 15.02.2022 | Уже в Op1 |
| Birgit Büttner (450049) | IMG_4248-4249 | 27.06.2023 | Уже в Op2 |
| René Dony (453434) | IMG_4258, 4260 | 28.10.2022 | Уже в Op1 |
| Ursula Kaden (202144) | IMG_4386 | 12.08.2025 | **НОВОЕ → Op2** ✅ (частич.) |
| Anja Kröber (883) | IMG_4398-4400 | 22.05.2023 | Уже в Op1 |
| Anja Kröber (883) | IMG_4401-4403 | 28.05.2024 | Уже в Op2 |
| Petra Lindner (244671) | IMG_4446 | 13.01.2026 | Уже в Op3 |
| Wilfried Merres (383157) | IMG_4490 | 30.09.2024 | Уже в Op2 |
| Ramona Nemes (194282) | IMG_4511 | 30.07.2024 | Уже в Op3 |
| Claudia Oppen (8863) | IMG_4522-4524 | 13.02.2023 | Уже в Op1 |
| Claudia Oppen (8863) | IMG_4525-4527 | 06.02.2024 | Уже в Op2 |
| Petra Paul (175037) | IMG_4553 | 10.06.2024 | Уже в Op3 |
| Claudia Renke-Albert (445118) | IMG_4597 | 07.06.2022 | Уже в Op1 |
| Claudia Renke-Albert (445118) | IMG_4600 | 27.04.2023 | Уже в Op2 |
| Stefan Georgi (454894) | IMG_4738 | 12.03.2024 | Уже в Op2 |
| Ricardo Liebl (125358) | IMG_4756 | 13.11.2024 | Уже в Op2 |
| Anett Friedrich (456968) | IMG_4762 | 23.01.2023 | Уже в Op1 |
| Tony Backhaus (460150) | IMG_4827 | 06.02.2023 | Уже в Op1 |
| Madlen Michel (482715) | IMG_5224 | 22.12.2025 | Уже в Op2 |
| Katja Mayer (482936) | IMG_5230 | 23.02.2026 | Уже в Op2 |
| Doreen Brudek (485760) | IMG_5268 | 13.10.2025 | Уже в Op2 |
| Andre Wolf (478963) | IMG_5276 | 12.03.2024 | Уже в Op1 |
| Sebastian Frey (492327) | IMG_5408 | 28.11.2024 | Уже в Op1 |
| Iris Becher (59183) | IMG_5426 | 09.12.2025 | Уже в Op2 |

### Неопознанные фото (7 шт.) — в UNKNOWN

| Фото | Причина |
|------|---------|
| IMG_4052.jpg | Страница 2, имя не видно (фото экрана) |
| IMG_4053.jpg | Страница 3, имя не видно (фото экрана) |
| IMG_4057.jpg | Страница 3, имя не видно (фото экрана) |
| IMG_4068.jpg | Страница 3, 45 жен., 25.08.2022, имя не видно |
| IMG_4071.jpg | Страница 2, имя не видно (фото экрана) |
| IMG_4072.jpg | Страница 3, 44 муж., 07.08.2023, имя не видно |
| IMG_4356.jpg | Страница 4, 28 жен., 18.03.2022, имя не видно |

### Новые данные в таблице (голубые ячейки)

**Daniela Bernhardt (437313) — Op3 (15.05.2023):**
Gewicht=77.4, Größe=160, BMI=30.25, FM=25.92 (33.5%), FMI=10.1, FFM=51.48 (66.5%), FFMI=20.1, SMM=21.57, R=491.2, Xc=36.6, VAT=0.7, WC=93, φ=4.3°, Perz=1, TBW=37.91 (49.0%), ECW=18.51 (23.9%), ECW/TBW=48.8%

**Ursula Kaden (202144) — Op2 (12.08.2025) — частичные:**
FMI=20.4, FFMI=19.5, SMM=15.09, TBW=34.01 (38.9%), ECW=16.31 (19.3%), ECW/TBW=50.6%
(Отсутствуют: Gewicht, Größe, BMI, FM, FFM, R, Xc, VAT, WC, φ, Perz — фото стр.1 и стр.3 не найдены)

---

## Previous Task — Верификация данных таблицы по фото + цветовая маркировка

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
