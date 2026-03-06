#!/usr/bin/env python3
"""Download HEIC photos from Google Drive, save as JPEG, for a batch of folders."""

import json
import base64
import os
import sys
import subprocess
import time

WEBHOOK_DOWNLOAD = "https://n8n.rnd.webpromo.tools/webhook/download-folder-files"
WEBHOOK_LIST = "https://n8n.rnd.webpromo.tools/webhook/list-folder-files"
WEBHOOK_SHEET = "https://n8n.rnd.webpromo.tools/webhook/write-queue-sheet"
CONVERTED_DIR = "/home/user/hospital/Photo/converted"
FOLDERS_FILE = "/tmp/all_folders.json"


def download_folder(folder_id, folder_name):
    """Download all files from a Drive folder via n8n webhook."""
    out_dir = os.path.join(CONVERTED_DIR, folder_name)
    os.makedirs(out_dir, exist_ok=True)

    result = subprocess.run([
        'curl', '-s', '-X', 'POST', WEBHOOK_DOWNLOAD,
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({"folderId": folder_id}),
        '--max-time', '180'
    ], capture_output=True, text=True)

    if not result.stdout.strip():
        print(f" EMPTY", end='', flush=True)
        return download_folder_via_thumbnails(folder_id, folder_name)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f" LARGE->thumbnails", end='', flush=True)
        return download_folder_via_thumbnails(folder_id, folder_name)

    files = data.get('files', [])
    count = 0
    for f in files:
        name = f['name']
        b64 = f['base64']
        out_name = name.rsplit('.', 1)[0] + '.jpg'
        out_path = os.path.join(out_dir, out_name)
        with open(out_path, 'wb') as fp:
            fp.write(base64.b64decode(b64))
        count += 1

    return count


def download_folder_via_thumbnails(folder_id, folder_name):
    """Fallback: list files, then download each via thumbnail URL."""
    out_dir = os.path.join(CONVERTED_DIR, folder_name)
    os.makedirs(out_dir, exist_ok=True)

    result = subprocess.run([
        'curl', '-s', '-X', 'POST', WEBHOOK_LIST,
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({"folderId": folder_id}),
        '--max-time', '30'
    ], capture_output=True, text=True)

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return 0

    files = data.get('files', [])
    count = 0
    for f in files:
        name = f.get('name', '')
        lower = name.lower()
        if not (lower.endswith('.heic') or lower.endswith('.jpg') or lower.endswith('.jpeg') or lower.endswith('.png')):
            continue

        thumbnail = f.get('thumbnailLink', '')
        if not thumbnail:
            continue

        # Use high-res thumbnail
        if '=s' in thumbnail:
            thumbnail = thumbnail.rsplit('=s', 1)[0] + '=s4096'
        else:
            thumbnail += '=s4096'

        out_name = name.rsplit('.', 1)[0] + '.jpg'
        out_path = os.path.join(out_dir, out_name)

        subprocess.run([
            'curl', '-s', '-L', '-o', out_path,
            thumbnail, '--max-time', '30'
        ], capture_output=True, text=True)

        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        if size > 1000:
            count += 1
        elif os.path.exists(out_path):
            os.remove(out_path)

    return count


def update_sheet_status(folder_names, status="DONE"):
    """Update status in the converted-folders sheet."""
    with open(FOLDERS_FILE) as fp:
        data = json.load(fp)

    folders = data['folders']

    for fname in folder_names:
        for f in folders:
            if f['name'] == fname:
                row = f['row'] + 1  # +1 for header
                payload = {
                    "spreadsheetId": "1cgctBCQVmqpfQKdomYLfGAWVwRjT1Qw0-dl9F5RzoOg",
                    "range": f"converted-folders!D{row}",
                    "majorDimension": "ROWS",
                    "values": [[status]]
                }
                subprocess.run([
                    'curl', '-s', '-X', 'POST', WEBHOOK_SHEET,
                    '-H', 'Content-Type: application/json',
                    '-d', json.dumps(payload),
                    '--max-time', '10'
                ], capture_output=True, text=True)
                break


def process_batch(batch_num):
    """Process a batch of 10 folders."""
    with open(FOLDERS_FILE) as fp:
        data = json.load(fp)

    folders = data['folders']
    start = (batch_num - 1) * 10
    end = start + 10
    batch = folders[start:end]

    processed = []
    for f in batch:
        name = f['name']
        fid = f['id']

        out_dir = os.path.join(CONVERTED_DIR, name)
        if os.path.exists(out_dir) and len(os.listdir(out_dir)) > 0:
            print(f"  SKIP {name} (already exists with {len(os.listdir(out_dir))} files)")
            processed.append(name)
            continue

        print(f"  Downloading {name}...", end='', flush=True)
        count = download_folder(fid, name)
        print(f" {count} files")
        processed.append(name)
        time.sleep(1)

    return processed


if __name__ == '__main__':
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Processing batch {batch_num}...")
    processed = process_batch(batch_num)
    print(f"\nBatch {batch_num} complete: {len(processed)} folders")
    print(f"Folders: {processed}")

    print("Updating sheet status...")
    update_sheet_status(processed, "DONE")
    print("Done!")
