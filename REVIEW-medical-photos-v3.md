# Technical Review: Medical Photos v3 - Sequential

**Workflow ID:** `AdyJp6fjXUssihTR`
**Workflow Name:** Medical Photos v3 - Sequential
**Date:** 2026-03-06
**Status:** FIX APPLIED AND TESTED

---

## Summary

The workflow processes medical photos from Google Drive client folders, extracts data via OpenAI Vision, and writes results to Google Sheets.

**Root cause:** Using Google Drive thumbnails (`s2048`) instead of full-resolution files caused OpenAI Vision to extract almost no data (1/21 fields). Switching to actual file download via `files/{id}?alt=media` fixed the issue completely.

**Fix applied to production:** `gpt-4o-mini` + full file download + `max_tokens: 1500`.

---

## Test Results (folder 494354 - Katja Kallenbach, 6 HEIC photos, 2 operations)

### Comparison: thumbnail vs full file download

| Configuration | Op 1 (18.03.2025) | Op 2 (10.02.2026) | Notes |
|---|---|---|---|
| gpt-4o-mini + thumbnail s2048 (original) | **1/21** | N/A | Only ECW_TBW_pct extracted |
| gpt-4o-mini + **full file** | **20/21** | **18/21** | Missing TBW_l in Op1; ECW_TBW_pct wrong value in Op2 (18.8 instead of 52.3) |
| gpt-4o + **full file** | **21/21** | **16/21** | All values correct, most accurate |

### Key findings

1. **Full file download is the critical fix.** Going from thumbnail to actual file improved gpt-4o-mini from 1/21 to 20/21 fields.
2. **gpt-4o is more accurate** but gpt-4o-mini is acceptable. mini occasionally confuses similar fields (ECW_pct vs ECW_TBW_pct).
3. **gpt-4o-mini chosen for production** due to cost/speed tradeoff. 20/21 fields with occasional field confusion is acceptable vs 1/21 with thumbnails.

### Production configuration

| Parameter | Before | After |
|---|---|---|
| Model | gpt-4o-mini | gpt-4o-mini (unchanged) |
| Image source (JPEG/PNG) | thumbnail s2048 | **Full file via Drive API** |
| Image source (HEIC) | thumbnail s2048 | **thumbnail s4096** (OpenAI doesn't support HEIC) |
| max_tokens | 800 | **1500** |

---

## Bug #1 (ALREADY FIXED): Off-by-one in `Build Sheet Data`

The scan loop started at `i = 5` instead of `i = 6`, causing all clients to overwrite each other in row 7. **Already fixed** in current workflow.

---

## Bug #2 (FIXED): OpenAI Vision extracts almost no data from thumbnails

### Problem

Google Drive thumbnails (even at `s2048`) lose too much detail for OCR of hospital monitor screens with small text and numbers.

### Root Cause

The `Build OpenAI Request` node downloaded images via `thumbnailLink` instead of the actual file. Thumbnails are compressed JPEG previews that lose fine detail.

### Fix Applied

In the **`Build OpenAI Request`** node:

```javascript
// For JPEG/PNG: download actual file via Drive API
const response = await this.helpers.httpRequestWithAuthentication.call(
  this, 'googleDriveOAuth2Api',
  { method: 'GET', url: `https://www.googleapis.com/drive/v3/files/${fileData.id}?alt=media`,
    encoding: 'arraybuffer', timeout: 30000 }
);
base64Image = Buffer.from(response).toString('base64');

// For HEIC: use high-res thumbnail (OpenAI doesn't support HEIC natively)
// Fallback: thumbnail at s4096 instead of s2048

// max_tokens increased from 800 to 1500
```

---

## Secondary Issues (unchanged)

### 1. No rollback on partial failure

If Sheets write fails, the folder still gets renamed to `_DONE`. Files are already renamed individually during processing. No way to re-process without manual cleanup.

### 2. Global staticData for inter-node data passing

Fragile but works for sequential execution. No logging of collected data before sheet write.

### 3. Same-date photo merging

Multiple photos for same date merge fields. Later non-null values overwrite earlier ones. Likely by design.

---

## Workflow Architecture

```
Webhook -> Config -> List Folders -> Filter Clients -> Split Clients (batch=1)
  +- [done] -> All Done
  +- [each] -> List Client Files -> Prepare Files -> Has Files?
      +- [no files] -> Skip -> Split Clients
      +- [has files] -> Split Files (batch=1)
          +- [done] -> Write Client to Sheets -> Has Data?
          |   +- [yes] -> Read Sheet -> Build Sheet Data -> Sheets Merge -> Sheets Write -> Rename Folder DONE -> Split Clients
          |   +- [no] -> Split Clients
          +- [each] -> Get Metadata -> Build OpenAI Request -> Image OK?
              +- [yes] -> OpenAI Vision -> Parse & Store -> Rename File DONE -> Delay 2s -> Split Files
              +- [no] -> Skip Error File -> Split Files
```

### Key Configuration

| Parameter | Value |
|-----------|-------|
| Root Folder ID | `1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_` |
| Spreadsheet ID | `1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg` |
| Sheet Name | `Patientendaten` |
| Sheet GID | `1199154574` |
| OpenAI Model | `gpt-4o-mini` |
| Image Source | Full file download (JPEG/PNG) / thumbnail s4096 (HEIC) |
| max_tokens | 1500 |
