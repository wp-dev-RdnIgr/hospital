#!/usr/bin/env python3
"""Extract BIA data from converted JPEG photos of patient reports.

Each patient folder contains 3 photos per operation (pages 1-3 of BIA report).
Photos are sorted by filename to determine page order.

Page 1: Gewicht, Größe, BMI, FM(kg), FM(%), FMI, FFM(kg), FFM(%), FFMI
Page 2: SMM, TBW(l), TBW(%), ECW(l), ECW(%), ECW/TBW(%)
Page 3: R(Ohm), Xc(Ohm), VAT(l), Taillenumfang(cm), phi(deg), Perzentile

Output: 21 fields per operation in order:
Gewicht, Größe, BMI, FM(kg), FM(%), FMI, FFM(kg), FFM(%), FFMI, SMM,
R, Xc, VAT, Taillenumfang, phi, Perzentile, TBW, TBW%, ECW, ECW%, ECW/TBW%
"""

import json
import os
import re
import sys


CONVERTED_DIR = "/home/user/hospital/Photo/converted"
EXTRACTED_DIR = "/home/user/hospital/extracted_data"


def parse_german_number(s):
    """Parse a German-format number (comma as decimal separator)."""
    if s is None:
        return None
    s = s.strip().replace(' ', '')
    if not s or s == '-':
        return None
    s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def extract_page1(text):
    """Extract fields from page 1: BMI section + Fettmasse + Fettfreie Masse."""
    data = {}

    # Gewicht
    m = re.search(r'Gewicht[:\s]*\n?\s*([\d.,]+)\s*kg', text)
    if m:
        data['gewicht'] = parse_german_number(m.group(1))

    # Größe
    m = re.search(r'Gr[öo](?:ß|ss)e[:\s]*\n?\s*([\d.,]+)\s*cm', text)
    if m:
        data['groesse'] = parse_german_number(m.group(1))

    # BMI
    m = re.search(r'BMI[:\s]*\n?\s*([\d.,]+)\s*kg/m', text)
    if m:
        data['bmi'] = parse_german_number(m.group(1))

    # Fettmasse FM (kg) and FM (%)
    m = re.search(r'Fettmasse\s*\(FM\)[:\s]*\n?\s*([\d.,]+)\s*kg\s*\(([\d.,]+)\s*%\)', text)
    if m:
        data['fm_kg'] = parse_german_number(m.group(1))
        data['fm_pct'] = parse_german_number(m.group(2))

    # FMI
    m = re.search(r'Fettmasse-Index\s*\(FMI\)[:\s]*\n?\s*([\d.,]+)', text)
    if m:
        data['fmi'] = parse_german_number(m.group(1))

    # Fettfreie Masse FFM (kg) and FFM (%)
    m = re.search(r'Fettfreie\s*Masse\s*\(FFM\)[:\s]*\n?\s*([\d.,]+)\s*kg\s*\(([\d.,]+)\s*%\)', text)
    if m:
        data['ffm_kg'] = parse_german_number(m.group(1))
        data['ffm_pct'] = parse_german_number(m.group(2))

    # FFMI
    m = re.search(r'Fettfreie-Masse-Index\s*\(FFMI\)[:\s]*\n?\s*([\d.,]+)', text)
    if m:
        data['ffmi'] = parse_german_number(m.group(1))

    return data


def extract_page2(text):
    """Extract fields from page 2: SMM + Water."""
    data = {}

    # SMM
    m = re.search(r'Skelettmuskelmasse\s*\(SMM\)[:\s]*\n?\s*([\d.,]+)', text)
    if m:
        data['smm'] = parse_german_number(m.group(1))

    # TBW
    m = re.search(r'Gesamt(?:körper)?wasser\s*\(TBW\)[:\s]*\n?\s*([\d.,]+)\s*l?\s*\(([\d.,]+)\s*%\)', text)
    if m:
        data['tbw_l'] = parse_german_number(m.group(1))
        data['tbw_pct'] = parse_german_number(m.group(2))

    # ECW
    m = re.search(r'Extrazellul[aä]res\s*Wasser\s*\(ECW\)[:\s]*\n?\s*([\d.,]+)\s*l?\s*\(([\d.,]+)\s*%\)', text)
    if m:
        data['ecw_l'] = parse_german_number(m.group(1))
        data['ecw_pct'] = parse_german_number(m.group(2))

    # ECW/TBW
    m = re.search(r'ECW/TBW[:\s]*\n?\s*([\d.,]+)\s*%', text)
    if m:
        data['ecw_tbw'] = parse_german_number(m.group(1))

    return data


def extract_page3(text):
    """Extract fields from page 3: BIVA + VAT + Phasenwinkel."""
    data = {}

    # Resistanz R
    m = re.search(r'Resistanz\s*\(R\)[:\s]*\n?\s*([\d.,]+)\s*[ΩO]', text)
    if m:
        data['r_ohm'] = parse_german_number(m.group(1))

    # Reaktanz Xc
    m = re.search(r'Reaktanz\s*\(Xc\)[:\s]*\n?\s*([\d.,]+)\s*[ΩO]', text)
    if m:
        data['xc_ohm'] = parse_german_number(m.group(1))

    # VAT
    m = re.search(r'Viszerales\s*Fett\s*\(VAT\)[:\s]*\n?\s*([\d.,]+)\s*l', text)
    if m:
        data['vat'] = parse_german_number(m.group(1))

    # Taillenumfang
    m = re.search(r'Taillenumfang\s*\(WC\)[:\s]*\n?\s*([\d.,]+)\s*cm', text)
    if m:
        data['taillenumfang'] = parse_german_number(m.group(1))

    # Phasenwinkel phi
    m = re.search(r'Phasenwinkel\s*\([φϕp]\)[:\s]*\n?\s*([\d.,]+)', text)
    if m:
        data['phi'] = parse_german_number(m.group(1))

    # Perzentile
    m = re.search(r'Perzentile[:\s]*\n?\s*(\d+)', text)
    if m:
        data['perzentile'] = int(m.group(1))

    return data


def extract_patient_info(text):
    """Extract patient ID, name, date from any page."""
    info = {}

    m = re.search(r'ID[:\s]+(\d+)', text)
    if m:
        info['id'] = m.group(1)

    m = re.search(r'Name[:\s]+(.+)', text)
    if m:
        info['name'] = m.group(1).strip()

    # Date format: DD.MM.YYYY
    m = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
    if m:
        parts = m.group(1).split('.')
        info['date'] = f"{parts[2]}-{parts[1]}-{parts[0]}"

    return info


def build_fields(p1, p2, p3):
    """Build the 21-field array from extracted page data."""
    return [
        p1.get('gewicht'),
        p1.get('groesse'),
        p1.get('bmi'),
        p1.get('fm_kg'),
        p1.get('fm_pct'),
        p1.get('fmi'),
        p1.get('ffm_kg'),
        p1.get('ffm_pct'),
        p1.get('ffmi'),
        p2.get('smm'),
        p3.get('r_ohm'),
        p3.get('xc_ohm'),
        p3.get('vat'),
        p3.get('taillenumfang'),
        p3.get('phi'),
        p3.get('perzentile'),
        p2.get('tbw_l'),
        p2.get('tbw_pct'),
        p2.get('ecw_l'),
        p2.get('ecw_pct'),
        p2.get('ecw_tbw'),
    ]


if __name__ == '__main__':
    # This script is meant to be called by the main processing loop
    # which reads images via Claude vision and passes OCR text
    print("This module provides extraction functions.")
    print("Use extract_all_patients.py for batch processing.")
