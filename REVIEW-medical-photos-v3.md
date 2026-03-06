# Technical Review: Medical Photos v3 - Sequential

**Workflow ID:** `AdyJp6fjXUssihTR`
**Workflow Name:** Medical Photos v3 - Sequential
**Date:** 2026-03-05
**Status:** 1 CRITICAL BUG (Vision model) + 1 FIXED (off-by-one)

---

## Summary

The workflow processes medical photos from Google Drive client folders, extracts data via OpenAI Vision, and writes results to Google Sheets. Two critical bugs found:

1. **~~Off-by-one error~~** in `Build Sheet Data` — **ALREADY FIXED** in current workflow (loop starts at `i = 6`).
2. **OpenAI Vision extraction failure** — `gpt-4o-mini` with thumbnail images extracts almost no data (1 out of 21 fields). Need `gpt-4o` and full-resolution file download. **THIS IS THE ACTIVE BUG.**

---

## Critical Bug: Off-by-one in `Build Sheet Data` node

### Problem

In the `Build Sheet Data` code node, the loop that scans existing client rows in the spreadsheet has an incorrect starting index:

```javascript
// CURRENT (BUGGY):
for (let i = 5; i < rows.length; i += 2) {
  const id = rows[i] && rows[i][0];
  if (id) clientRowMap[String(id).trim()] = i + 1;
}
```

The first client is written to **row 7** (1-indexed) = **index 6** (0-indexed in the `rows` array).

The scanning loop starts at `i = 5` with step 2, checking indices: **5, 7, 9, 11...**

**Index 6 is never checked.** The first client is invisible to the scanner.

### Impact

1. Client 1 → written to rows 7-8 ✓
2. Client 2 → scans rows at indices 5, 7, 9... → misses client 1 at index 6 → `clientRowMap` is empty → `nextFreeRow = 7` → **overwrites rows 7-8**
3. Client 3 → same problem → overwrites rows 7-8 again
4. Only the **last** client survives in the spreadsheet

This explains the reported behavior:
- **Google Drive:** ALL folders renamed to `_DONE` (loop works correctly)
- **Google Sheets:** Only ONE record (the last client processed), potentially incomplete

### Fix

Change the starting index from `5` to `6`:

```javascript
// FIXED:
for (let i = 6; i < rows.length; i += 2) {
  const id = rows[i] && rows[i][0];
  if (id) clientRowMap[String(id).trim()] = i + 1;
}
```

Now the scan checks indices **6, 8, 10, 12...** which correctly aligns with where client data rows are written (rows 7, 9, 11... in 1-indexed = indices 6, 8, 10... in 0-indexed).

---

## Critical Bug #2: OpenAI Vision extracts almost no data

### Problem

The workflow uses `gpt-4o-mini` model and Google Drive **thumbnails** (even upscaled to 2048px) instead of full-resolution files. For photos of hospital monitor screens with small text and numbers, this combination fails catastrophically.

**Evidence from test run:** Only 1 out of 21 medical fields was extracted (`ECW_TBW_pct: 50.12`). All other fields (Gewicht, Grosse, BMI, FM, FFM, SMM, BIVA, VAT, Phasenwinkel, Wasser) returned `null`.

### Root Causes

1. **`gpt-4o-mini` is too weak for medical screen OCR.** The mini model struggles with reading small numbers from monitor photos. `gpt-4o` is significantly better at vision tasks.

2. **Thumbnail instead of actual file.** The `Build OpenAI Request` node downloads via `thumbnailLink` (with `=s2048`), which is a compressed preview. For HEIC/JPEG photos of screens, the full file has much better detail. Should use `https://www.googleapis.com/drive/v3/files/{fileId}?alt=media` to download the actual file.

3. **`max_tokens: 800`** is borderline. The expected JSON response with 21+ fields can approach this limit, especially if the model adds explanatory text. Should increase to `1500`.

### Fix

In the **`Build OpenAI Request`** node:

```javascript
// 1. Change model from gpt-4o-mini to gpt-4o
model: 'gpt-4o',

// 2. Download actual file instead of thumbnail:
const response = await this.helpers.httpRequestWithAuthentication.call(
  this, 'googleDriveOAuth2Api',
  { method: 'GET', url: `https://www.googleapis.com/drive/v3/files/${fileData.id}?alt=media`, encoding: 'arraybuffer' }
);
base64Image = Buffer.from(response).toString('base64');

// 3. Increase max_tokens
max_tokens: 1500,
```

---

## Secondary Issues

### 1. No rollback on partial failure

If the Sheets write fails for a client, the workflow still proceeds to rename the folder to `_DONE` via the `Rename Folder DONE` node. This means:
- Files are already renamed `_DONE` individually during processing
- The folder gets marked `_DONE` even without successful sheet output
- **No way to re-process** without manual cleanup

**Recommendation:** Move `Rename Folder DONE` to execute only after `Sheets Write` succeeds, or add error handling that skips the rename on failure.

### 2. Global staticData for inter-node data passing

Data accumulation between `Parse & Store` and `Write Client to Sheets` uses `$getWorkflowStaticData('global')`. While this works for sequential execution, it's fragile:

- If any node in the file loop throws an unhandled error, accumulated data may be incomplete
- No visibility into what data was collected (no logging)

**Recommendation:** Consider adding a summary log node after the file loop that outputs what was collected before writing to sheets.

### 3. Same-date photo merging

If multiple photos for the same client share the same date, their extracted fields merge into a single operation entry:

```javascript
if (!cd.operations[date]) cd.operations[date] = {};
const op = cd.operations[date];
for (const field of FIELDS) {
  if (parsed[field] !== null && parsed[field] !== undefined) op[field] = parsed[field];
}
```

Later photos overwrite earlier ones for the same field. If photo A extracts `Gewicht_kg = 85` and photo B returns `Gewicht_kg = null`, the value from photo A is preserved (null is skipped). However, if photo B returns a different non-null value, it silently overwrites photo A's value.

**This is likely by design** (merging data from multiple screen photos of the same operation), but worth noting.

### 4. `Has Data?` condition uses implicit undefined check

The `Has Data?` node checks:
```
$json.skipped !== true  (strict type validation)
```

When `Write Client to Sheets` returns data (not skipped), `$json.skipped` is `undefined`. The comparison `undefined !== true` evaluates to `true` in most contexts, so this **likely works**, but it would be cleaner to explicitly return `skipped: false` in the success path.

---

## Workflow Architecture

```
Webhook → Config → List Folders → Filter Clients → Split Clients (batch=1)
  ├─ [done] → All Done
  └─ [each] → List Client Files → Prepare Files → Has Files?
      ├─ [no files] → Skip → Split Clients
      └─ [has files] → Split Files (batch=1)
          ├─ [done] → Write Client to Sheets → Has Data?
          │   ├─ [yes] → Read Sheet → Build Sheet Data → Sheets Merge → Sheets Write → Rename Folder DONE → Split Clients
          │   └─ [no] → Split Clients
          └─ [each] → Get Metadata → Build OpenAI Request → Image OK?
              ├─ [yes] → OpenAI Vision → Parse & Store → Rename File DONE → Delay 2s → Split Files
              └─ [no] → Skip Error File → Split Files
```

### Key Configuration

| Parameter | Value |
|-----------|-------|
| Root Folder ID | `1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_` |
| Spreadsheet ID | `1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg` |
| Sheet Name | `Patientendaten` |
| Sheet GID | `1199154574` |
| OpenAI Model | `gpt-4o-mini` |
| Execution Order | v1 |

---

## Action Items

| Priority | Action | Node |
|----------|--------|------|
| **P0 - CRITICAL** | Fix off-by-one: change `i = 5` to `i = 6` in client scan loop | `Build Sheet Data` |
| **P0 - CRITICAL** | Change model from `gpt-4o-mini` to `gpt-4o` | `Build OpenAI Request` |
| **P0 - CRITICAL** | Download actual file via Drive API instead of thumbnail | `Build OpenAI Request` |
| P1 | Increase `max_tokens` from 800 to 1500 | `Build OpenAI Request` |
| P1 | Add error handling to prevent folder rename on sheet write failure | `Rename Folder DONE` |
| P2 | Add explicit `skipped: false` in success path | `Write Client to Sheets` |
| P2 | Add logging/summary before sheet write | New node after `Split Files` done |

---

## How to Apply the Fixes

### Fix 1: Off-by-one in Build Sheet Data

1. Open workflow `AdyJp6fjXUssihTR` in n8n editor
2. Open the **`Build Sheet Data`** code node
3. Find the line:
   ```javascript
   for (let i = 5; i < rows.length; i += 2) {
   ```
4. Change `5` to `6`:
   ```javascript
   for (let i = 6; i < rows.length; i += 2) {
   ```

### Fix 2: OpenAI Vision quality in Build OpenAI Request

1. Open the **`Build OpenAI Request`** code node
2. Change model from `gpt-4o-mini` to `gpt-4o`:
   ```javascript
   model: 'gpt-4o',
   ```
3. Change `max_tokens` from `800` to `1500`:
   ```javascript
   max_tokens: 1500,
   ```
4. Replace the thumbnail download with actual file download:
   ```javascript
   // Instead of using thumbnailLink, download the actual file:
   try {
     const response = await this.helpers.httpRequestWithAuthentication.call(
       this, 'googleDriveOAuth2Api',
       { method: 'GET', url: `https://www.googleapis.com/drive/v3/files/${fileData.id}?alt=media`, encoding: 'arraybuffer' }
     );
     base64Image = Buffer.from(response).toString('base64');
     mediaType = fileData.mimeType || 'image/jpeg';
   } catch (e) {}
   ```

### After applying fixes

1. Save the workflow
2. **Clear existing data:** Remove the test row from the spreadsheet
3. **Reset folders:** Use the `Cleanup - Remove _DONE` workflow (`GNXhjuIo5j0xXG2p`) to remove `_DONE` suffixes from the affected folders
4. Re-run the workflow and verify that all fields are populated
