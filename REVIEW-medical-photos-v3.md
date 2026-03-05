# Technical Review: Medical Photos v3 - Sequential

**Workflow ID:** `AdyJp6fjXUssihTR`
**Workflow Name:** Medical Photos v3 - Sequential
**Date:** 2026-03-05
**Status:** CRITICAL BUG FOUND

---

## Summary

The workflow processes medical photos from Google Drive client folders, extracts data via OpenAI Vision, and writes results to Google Sheets. A critical off-by-one error causes **all client records to overwrite each other**, leaving only the last processed client in the spreadsheet.

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
| P1 | Add error handling to prevent folder rename on sheet write failure | `Rename Folder DONE` |
| P2 | Add explicit `skipped: false` in success path | `Write Client to Sheets` |
| P2 | Add logging/summary before sheet write | New node after `Split Files` done |

---

## How to Apply the Fix

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
5. Save the workflow
6. **Before re-running:** Use the `Cleanup - Remove _DONE` workflow (`GNXhjuIo5j0xXG2p`) to remove `_DONE` suffixes from the affected folders, so they can be re-processed
