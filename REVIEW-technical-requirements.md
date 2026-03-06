# Technical Requirements Review: Hospital n8n Automation System

**Date:** 2026-03-06
**Reviewer:** Claude (automated review)
**Scope:** All n8n workflows and supporting infrastructure in the Hospital project

---

## System Overview

The Hospital project automates processing of patient BIA (Bioelectrical Impedance Analysis) medical data using n8n workflows hosted at `https://n8n.rnd.webpromo.tools`. The system consists of 4 interconnected workflows that handle photo organization, data extraction, and spreadsheet writing.

### Target Spreadsheet
- **Spreadsheet ID:** `1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg`
- **Sheet Tab:** `Patientendaten` (GID: `1199154574`)
- **Structure:** Patient ID + Name in columns A-B, then blocks of 21 BIA fields per operation starting at column C

---

## Workflow Inventory

| # | Workflow | ID | Purpose | Status |
|---|---------|-----|---------|--------|
| 1 | HEIC Photo Organizer | `gFcvIN83wmc9UvkS` | Sort HEIC photos into patient ID folders on Google Drive | Active |
| 2 | HEIC Organizer Error Handler | `03h9SHa3Bj7pe8Gk` | Auto-restart organizer after errors (120s delay) | Active |
| 3 | Medical Photos v3 - Sequential | `AdyJp6fjXUssihTR` | Extract BIA data from photos via OpenAI Vision, write to Sheets | Active |
| 4 | BIA Write to Google Sheet | `oOXNiOsuAABXtTrZ` | Webhook endpoint for direct BIA data writing | Active |

---

## Workflow 1: HEIC Photo Organizer (`gFcvIN83wmc9UvkS`)

### Purpose
Sorts ~100 HEIC photos from a single Google Drive folder into subfolders named by patient ID (5-7 digits).

### Architecture
```
Manual Trigger -> Set Folder ID -> List HEIC Files -> Parse File List -> Split In Batches
  -> Get Thumbnail URL -> Download JPEG Thumbnail -> OpenAI Vision (GPT-4o) -> Parse Response
  -> IF (recognized?) -> [yes] Search/Create Patient Folder -> Move File
                       -> [no]  Leave in place
  -> Wait 2s -> next batch
```

### Technical Details
| Parameter | Value |
|-----------|-------|
| Google Drive Folder | `1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_` |
| OpenAI Model | `gpt-4o` |
| Image Source | Thumbnail at `s2048` resolution |
| Rate Limiting | 2s delay between files |
| Credential (Drive) | `googleDriveOAuth2Api` ID `Nl36H51nJBoCaf67` |
| Credential (OpenAI) | `openAiApi` ID `b1hLC5E1Ad7p27A9` |

### Known Issues
1. **Thumbnail resolution may be insufficient** - Uses `s2048` thumbnails which were later found inadequate for data extraction in Workflow 3 (fixed there with full file download). For ID recognition only, `s2048` appears sufficient.
2. **No pagination** - `pageSize: 200` may miss files if folder contains >200 items.
3. **No UNKNOWN folder handling in base workflow** - Unrecognized files stay in root. The spec mentions an UNKNOWN folder but the workflow leaves files in place.

---

## Workflow 2: HEIC Organizer Error Handler (`03h9SHa3Bj7pe8Gk`)

### Purpose
Catches errors from the organizer workflow and restarts it after a 120-second cooldown.

### Architecture
```
Error Trigger -> Wait 120s -> POST to /webhook/heic-organizer
```

### Technical Details
- Simple 3-node error recovery workflow
- Restarts the main organizer via webhook call
- No retry limit (could loop indefinitely on persistent errors)

### Known Issues
1. **Infinite restart loop** - No counter to limit restart attempts. A persistent error (e.g., expired credentials, API quota exceeded) will cause indefinite restarts every 120 seconds.
2. **No alerting** - No notification mechanism (email, Slack) when errors occur.

---

## Workflow 3: Medical Photos v3 - Sequential (`AdyJp6fjXUssihTR`)

### Purpose
Iterates over patient folders on Google Drive, extracts BIA measurement data from medical photos using OpenAI Vision, and writes structured results to Google Sheets.

### Architecture
```
Webhook/Manual -> Config -> List Folders -> Filter Clients (numeric names only)
  -> Split Clients (batch=1)
    +- [done] -> All Done
    +- [each] -> List Client Files -> Prepare Files -> Has Files?
        +- [no] -> Skip -> next client
        +- [yes] -> Split Files (batch=1)
            +- [done] -> Write Client to Sheets -> Has Data?
            |   +- [yes] -> Read Sheet -> Build Sheet Data -> Sheets Merge -> Sheets Write -> Rename Folder DONE -> next client
            |   +- [no] -> next client
            +- [each] -> Get Metadata -> Build OpenAI Request -> Image OK?
                +- [yes] -> OpenAI Vision -> Parse & Store -> Rename File DONE -> Delay 2s -> next file
                +- [no] -> Skip Error File -> next file
```

### Technical Details
| Parameter | Value |
|-----------|-------|
| OpenAI Model | `gpt-4o-mini` (production) / `gpt-4o` (in JSON, should be `gpt-4o-mini`) |
| Image Source (JPEG/PNG) | Full file download via `files/{id}?alt=media` |
| Image Source (HEIC) | Thumbnail at `s4096` |
| max_tokens | 1500 |
| Rate Limiting | 2s between files, 1s between clients |
| Inter-node Data | `$getWorkflowStaticData('global')` |
| Credential (Drive) | `googleDriveOAuth2Api` ID `Nl36H51nJBoCaf67` |
| Credential (Sheets) | Uses Drive credential for Sheets API (works but not ideal) |

### Data Extraction Fields (21 per operation)
```
Gewicht(kg), Groesse(cm), BMI, FM(kg), FM(%), FMI,
FFM(kg), FFM(%), FFMI, SMM(kg), R(Ohm), Xc(Ohm),
VAT(l), Taillenumfang(cm), phi(deg), Perzentile,
TBW(l), TBW(%), ECW(l), ECW(%), ECW/TBW(%)
```

### Known Issues

#### Critical
1. **Model mismatch in JSON** - The `Build OpenAI Request` node hardcodes `model: 'gpt-4o'` but production was supposed to use `gpt-4o-mini` per the review. Cost implications: gpt-4o is ~10x more expensive.

#### High
2. **No rollback on partial failure** - If Sheets write fails after photos were already renamed with `_DONE`, there's no way to re-process without manual cleanup (renaming files/folders back).
3. **`globalStaticData` fragility** - All inter-file data is accumulated in `staticData.clientData`. If the workflow crashes mid-client, all collected data for that client is lost.
4. **Sheets write uses `RAW` valueInputOption** - Numeric values written as-is. Dates and formatted strings won't be interpreted. Should use `USER_ENTERED` if locale-specific formatting is needed.

#### Medium
5. **Read Sheet reads entire range `A1:ZZ2000`** - Downloads potentially large amounts of data. Could be optimized to read only column A (for row mapping) and row 1-2 (for header detection).
6. **Same-date photo merging** - Multiple photos with the same date silently overwrite fields. Later non-null values replace earlier ones. Could lose data if photos contain conflicting values.
7. **No pagination for Google Drive listing** - `pageSize: 200/500` limits could miss folders or files in large datasets.
8. **Merge-before-write ordering** - `Sheets Merge` runs before `Sheets Write`. Merging cells before writing values could cause unexpected behavior if cells being merged already contain data.

---

## Workflow 4: BIA Write to Google Sheet (`oOXNiOsuAABXtTrZ`)

### Purpose
Webhook endpoint that accepts structured patient BIA data via POST and writes it directly to Google Sheets with cell merging for formatted layout.

### Architecture
```
Webhook (POST /bia-write-sheet) -> Parse Input -> Write Data -> Apply Merge -> Respond OK
```

### Technical Details
| Parameter | Value |
|-----------|-------|
| Webhook URL | `https://n8n.rnd.webpromo.tools/webhook/bia-write-sheet` |
| Method | POST |
| Credential (Sheets) | `googleSheetsOAuth2Api` ID `hMp9ISVYVcdpImYl` |
| Default Spreadsheet | `1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg` |
| Default Sheet | `Patientendaten` (GID `1199154574`) |

### Input Modes
1. **Structured patients** - Array of patient objects with `id`, `name`, `operations[{date, fields[21]}]`
2. **Raw rows** - Direct `rows` array of arrays
3. **Single row** - One `row` array

### Sheet Layout (2-row per patient)
```
Row N:   [ID]  [Name]  [date1 merged across 21 cols]  [date2 merged across 21 cols] ...
Row N+1: [ID]  [Name]  [21 BIA values]                [21 BIA values]               ...
```

### Known Issues

#### High
1. **No authentication on webhook** - The webhook endpoint is publicly accessible. Anyone with the URL can write arbitrary data to the Google Sheet.
2. **No input validation** - The Parse Input node doesn't validate field types, array lengths, or required fields. Malformed input could write garbage data.
3. **Hardcoded credentials in local JSON** - `BIA_Write_to_Sheet_workflow.json` contains outdated credential IDs (`googleDriveOAuth2Api` instead of `googleSheetsOAuth2Api`). The live workflow on n8n was fixed but the local file is stale.

#### Medium
4. **No concurrency protection** - Simultaneous webhook calls could write overlapping data. No locking mechanism for the `startRow` parameter.
5. **`hasFormatting` check unreachable** - The local JSON has an IF node checking `hasFormatting`, but `$json` after the Write Data HTTP response doesn't contain Parse Input's data. The live workflow fixed this by removing the IF node, but the local JSON is outdated.

---

## Cross-Cutting Concerns

### Credential Management
| Credential | Type | ID | Used By |
|-----------|------|-----|---------|
| Google Drive for n8n | `googleDriveOAuth2Api` | `Nl36H51nJBoCaf67` | Workflows 1, 3 |
| Google Sheets account | `googleSheetsOAuth2Api` | `hMp9ISVYVcdpImYl` | Workflow 4 (live) |
| OpenAi - course generator | `openAiApi` | `b1hLC5E1Ad7p27A9` | Workflows 1, 3 |

**Issue:** Workflow 3 uses the Google Drive OAuth2 credential for Sheets API calls. While this works (the OAuth scope may include Sheets), it's inconsistent with Workflow 4 which uses the dedicated Sheets credential.

### Data Privacy & Compliance
- **Patient data (names, IDs, medical measurements)** flows through OpenAI's API for image analysis
- GDPR/HIPAA compliance should be verified with the clinic
- n8n API key and credentials are stored in `CLAUDE.md` (committed to git) - these should be in environment variables or a secrets manager instead

### Local vs Live Workflow Drift
The local JSON files in the repository are **out of sync** with the live n8n workflows:
- `BIA_Write_to_Sheet_workflow.json` uses wrong credential type and old sheet name
- `Medical_Photos_v3_FIXED_workflow.json` may not reflect latest live changes
- No CI/CD pipeline to keep local files in sync with n8n

### Error Handling Summary
| Workflow | Error Handling |
|----------|---------------|
| 1 (HEIC Organizer) | External error handler workflow (Workflow 2) |
| 2 (Error Handler) | None (restart loop) |
| 3 (Medical Photos v3) | Per-file skip on image download failure; no recovery on Sheets write failure |
| 4 (BIA Write) | None - errors returned as HTTP 500 to caller |

---

## Recommendations

### Priority 1 (Security)
1. **Add webhook authentication** - Add API key or bearer token validation to BIA Write webhook
2. **Remove credentials from CLAUDE.md** - Move API keys and tokens to environment variables
3. **Validate webhook input** - Add schema validation in Parse Input node

### Priority 2 (Reliability)
4. **Add restart counter to Error Handler** - Limit to 3-5 restarts, then send alert
5. **Add rollback for Workflow 3** - Don't rename files/folders until Sheets write succeeds
6. **Sync local JSON files with n8n** - Add export script or use n8n API to periodically dump workflow definitions

### Priority 3 (Performance/Quality)
7. **Optimize Sheet reading** - Read only needed columns/rows instead of `A1:ZZ2000`
8. **Add pagination for Drive API** - Handle `nextPageToken` for folders with >200 files
9. **Standardize credential usage** - Use `googleSheetsOAuth2Api` consistently for Sheets API calls
10. **Fix model specification** - Align JSON and live workflow on `gpt-4o-mini` for cost savings

---

## Test Results Reference

### HEIC Photo Organizer (2026-03-05)
- 15/15 files processed, 0 errors
- 3 patients identified, folders created
- Duration: ~3 minutes

### Medical Photos v3 - Thumbnail vs Full File (2026-03-06)
| Config | Fields Extracted |
|--------|-----------------|
| gpt-4o-mini + thumbnail s2048 | 1/21 |
| gpt-4o-mini + full file download | 20/21 |
| gpt-4o + full file download | 21/21 |

Full file download was the critical fix. gpt-4o-mini chosen for production (cost/quality tradeoff).
