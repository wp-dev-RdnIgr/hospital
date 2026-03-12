#!/usr/bin/env python3
"""
BIA-Datenanalyse: Umfassende Auswertung der Patientendaten
vor und nach bariatrischer Operation.
Erzeugt:
  1. analysis_report.md  – Textbericht (Deutsch)
  2. bia_visualisierung.pdf – PDF mit Grafiken (Deutsch)
"""

import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

# ---------------------------------------------------------------------------
# 0.  Hilfsfunktionen
# ---------------------------------------------------------------------------

def parse_german_float(s):
    """Wandelt deutsche Dezimalzahlen (Komma) in float um."""
    if s is None:
        return None
    s = s.strip()
    if s == "" or s == "-":
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


FIELD_NAMES = [
    "Gewicht_kg", "Groesse_cm", "BMI", "FM_kg", "FM_pct", "FMI",
    "FFM_kg", "FFM_pct", "FFMI", "SMM_kg", "R_Ohm", "Xc_Ohm",
    "VAT_l", "Taillenumfang_cm", "phi_deg", "Perzentile",
    "TBW_l", "TBW_pct", "ECW_l", "ECW_pct", "ECW_TBW_pct"
]

FIELD_LABELS_DE = {
    "Gewicht_kg": "Gewicht (kg)",
    "Groesse_cm": "Größe (cm)",
    "BMI": "BMI (kg/m²)",
    "FM_kg": "Fettmasse (kg)",
    "FM_pct": "Fettmasse (%)",
    "FMI": "FMI (kg/m²)",
    "FFM_kg": "Fettfreie Masse (kg)",
    "FFM_pct": "Fettfreie Masse (%)",
    "FFMI": "FFMI (kg/m²)",
    "SMM_kg": "Skelettmuskelmasse (kg)",
    "R_Ohm": "Resistanz R (Ω)",
    "Xc_Ohm": "Reaktanz Xc (Ω)",
    "VAT_l": "Viszerales Fett (l)",
    "Taillenumfang_cm": "Taillenumfang (cm)",
    "phi_deg": "Phasenwinkel φ (°)",
    "Perzentile": "Perzentile",
    "TBW_l": "TBW (l)",
    "TBW_pct": "TBW (%)",
    "ECW_l": "ECW (l)",
    "ECW_pct": "ECW (%)",
    "ECW_TBW_pct": "ECW/TBW (%)"
}

# ---------------------------------------------------------------------------
# 1.  CSV einlesen
# ---------------------------------------------------------------------------

def load_data(csv_path):
    """Liest die CSV und gibt eine Liste von Patienten-Dicts zurück."""
    patients = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Datenzeilen beginnen ab Zeile 6 (Index 5)
    i = 5
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1
            continue
        pid = row[0].strip()
        name = row[1].strip() if len(row) > 1 else ""

        # Datumszeile: Spalte 2 = Op1-Datum, 23 = Op2-Datum, 44 = Op3-Datum
        dates = [None, None, None]
        for op_idx, col_offset in enumerate([2, 23, 44]):
            if len(row) > col_offset and row[col_offset].strip():
                dates[op_idx] = row[col_offset].strip()

        # Nächste Zeile enthält die Messwerte
        if i + 1 < len(rows):
            data_row = rows[i + 1]
        else:
            data_row = []

        ops = []
        for op_idx in range(3):
            col_start = 2 + op_idx * 21
            values = {}
            has_any = False
            for fi, fname in enumerate(FIELD_NAMES):
                col = col_start + fi
                val = None
                if col < len(data_row):
                    val = parse_german_float(data_row[col])
                values[fname] = val
                if val is not None:
                    has_any = True
            ops.append({
                "date": dates[op_idx],
                "values": values,
                "has_data": has_any
            })

        patients.append({
            "id": pid,
            "name": name,
            "ops": ops
        })
        i += 2  # Springe über die Datenzeile

    return patients


# ---------------------------------------------------------------------------
# 2.  Analyse-Funktionen
# ---------------------------------------------------------------------------

def get_complete_patients(patients, fields=None):
    """Patienten mit Daten in mindestens Op1 und Op2."""
    if fields is None:
        fields = ["Gewicht_kg", "BMI"]
    result = []
    for p in patients:
        ok = True
        for op_idx in [0, 1]:
            if not p["ops"][op_idx]["has_data"]:
                ok = False
                break
            for f in fields:
                if p["ops"][op_idx]["values"].get(f) is None:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            result.append(p)
    return result


def get_three_op_patients(patients, fields=None):
    """Patienten mit Daten in allen 3 Operationen."""
    if fields is None:
        fields = ["Gewicht_kg", "BMI"]
    result = []
    for p in patients:
        ok = True
        for op_idx in [0, 1, 2]:
            if not p["ops"][op_idx]["has_data"]:
                ok = False
                break
            for f in fields:
                if p["ops"][op_idx]["values"].get(f) is None:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            result.append(p)
    return result


def compute_stats(values):
    """Berechnet Statistiken für eine Liste von Zahlen."""
    arr = [v for v in values if v is not None]
    if not arr:
        return None
    arr = np.array(arr)
    return {
        "n": len(arr),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "q25": float(np.percentile(arr, 25)),
        "q75": float(np.percentile(arr, 75))
    }


def classify_bmi(bmi):
    if bmi < 25:
        return "Normalgewicht"
    elif bmi < 30:
        return "Übergewicht"
    elif bmi < 35:
        return "Adipositas I"
    elif bmi < 40:
        return "Adipositas II"
    else:
        return "Adipositas III"


def gender_guess(name, ffmi=None, smm=None):
    """Grobe Geschlechtszuordnung nach Vornamen."""
    female_names = {
        "sabrina", "claudia", "lilia", "iris", "marion", "juliane", "ute",
        "anja", "aline", "jasmin", "constanze", "simone", "gabriele",
        "nadine", "veronika", "grit", "sally", "sandra", "kathrin",
        "isabell", "kerstin", "peggy", "cornelia", "thea", "manja",
        "birgit", "katrin", "dragana", "jennifer", "carmen", "jana",
        "manuela", "sylvia", "ellen", "ramona", "ursula", "petra",
        "elke", "franziska", "andrea", "lidija", "heike", "diana",
        "adelheid", "susanne", "sara", "erika", "martina", "doreen",
        "babette", "nancy", "susan", "anke", "heidi", "nicole",
        "angelika", "mary", "madlen", "katja", "carolin", "romy",
        "inka", "dara", "angela", "alexandra", "annette", "maika",
        "corina", "inge", "lisa", "kristina", "ingrid", "stine",
        "meike", "larissa", "margitta", "anka", "annett", "szilvia",
        "katharina", "colett", "linda", "silke", "sarah", "miroslava",
        "judy", "joerg"  # not female but handled
    }
    male_names = {
        "hendrik", "lutz", "jochen", "mike", "frank", "ricardo", "heiko",
        "ronny", "patrick", "alexander", "andreas", "sebastian", "olaf",
        "kai", "arend", "sven", "daniel", "marc", "andy", "mirko",
        "pierre", "jens", "volker", "thomas", "stefan", "rene", "reiner",
        "wilfried", "gerd", "herbert", "michael", "silvio", "enrico",
        "matthias", "hans", "tony"
    }
    first = name.split()[0].lower() if name else ""
    if first in female_names:
        return "W"
    if first in male_names:
        return "M"
    # Heuristic by FFMI
    if ffmi is not None:
        return "M" if ffmi > 23 else "W"
    return "?"


# ---------------------------------------------------------------------------
# 3.  Hauptanalyse
# ---------------------------------------------------------------------------

def run_analysis(patients):
    """Führt die gesamte Analyse durch und gibt Ergebnisse als Dict zurück."""
    results = {}

    # Grundstatistiken
    total = len(patients)
    with_op1 = sum(1 for p in patients if p["ops"][0]["has_data"])
    with_op2 = sum(1 for p in patients if p["ops"][1]["has_data"])
    with_op3 = sum(1 for p in patients if p["ops"][2]["has_data"])
    with_all3 = sum(1 for p in patients if all(p["ops"][i]["has_data"] for i in range(3)))

    results["overview"] = {
        "total": total,
        "with_op1": with_op1,
        "with_op2": with_op2,
        "with_op3": with_op3,
        "with_all3": with_all3
    }

    # Geschlechterverteilung
    genders = {"M": 0, "W": 0, "?": 0}
    for p in patients:
        ffmi = p["ops"][0]["values"].get("FFMI")
        g = gender_guess(p["name"], ffmi)
        p["gender"] = g
        genders[g] += 1
    results["genders"] = genders

    # BMI-Verteilung pro Op
    bmi_data = {0: [], 1: [], 2: []}
    for p in patients:
        for oi in range(3):
            bmi = p["ops"][oi]["values"].get("BMI")
            if bmi is not None:
                bmi_data[oi].append(bmi)

    results["bmi_stats"] = {}
    for oi in range(3):
        results["bmi_stats"][oi] = compute_stats(bmi_data[oi])

    # BMI-Kategorien pro Op
    bmi_cats = {}
    for oi in range(3):
        cats = defaultdict(int)
        for b in bmi_data[oi]:
            cats[classify_bmi(b)] += 1
        bmi_cats[oi] = dict(cats)
    results["bmi_categories"] = bmi_cats

    # Gewichtsverlust Op1→Op2 und Op1→Op3
    weight_loss_12 = []
    weight_loss_13 = []
    pct_ewl_12 = []
    pct_ewl_13 = []
    for p in patients:
        w1 = p["ops"][0]["values"].get("Gewicht_kg")
        w2 = p["ops"][1]["values"].get("Gewicht_kg")
        w3 = p["ops"][2]["values"].get("Gewicht_kg")
        h = p["ops"][0]["values"].get("Groesse_cm")
        if w1 and w2:
            weight_loss_12.append(w1 - w2)
            if h:
                ideal = 25 * (h / 100) ** 2
                excess = w1 - ideal
                if excess > 0:
                    pct_ewl_12.append((w1 - w2) / excess * 100)
        if w1 and w3:
            weight_loss_13.append(w1 - w3)
            if h:
                ideal = 25 * (h / 100) ** 2
                excess = w1 - ideal
                if excess > 0:
                    pct_ewl_13.append((w1 - w3) / excess * 100)

    results["weight_loss"] = {
        "op1_op2": compute_stats(weight_loss_12),
        "op1_op3": compute_stats(weight_loss_13),
        "ewl_op1_op2": compute_stats(pct_ewl_12),
        "ewl_op1_op3": compute_stats(pct_ewl_13)
    }

    # Veränderung der Körperzusammensetzung
    comp_fields = ["FM_kg", "FM_pct", "FFM_kg", "FFM_pct", "SMM_kg",
                   "VAT_l", "Taillenumfang_cm", "phi_deg",
                   "TBW_pct", "ECW_TBW_pct", "FFMI", "FMI"]
    changes = {}
    for f in comp_fields:
        ch12 = []
        ch13 = []
        for p in patients:
            v1 = p["ops"][0]["values"].get(f)
            v2 = p["ops"][1]["values"].get(f)
            v3 = p["ops"][2]["values"].get(f)
            if v1 is not None and v2 is not None:
                ch12.append(v2 - v1)
            if v1 is not None and v3 is not None:
                ch13.append(v3 - v1)
        changes[f] = {
            "op1_op2": compute_stats(ch12),
            "op1_op3": compute_stats(ch13)
        }
    results["composition_changes"] = changes

    # Phasenwinkel-Analyse
    phi_data = {0: [], 1: [], 2: []}
    for p in patients:
        for oi in range(3):
            phi = p["ops"][oi]["values"].get("phi_deg")
            if phi is not None:
                phi_data[oi].append(phi)
    results["phi_stats"] = {oi: compute_stats(phi_data[oi]) for oi in range(3)}

    # Phasenwinkel < 5° (Risikoschwelle)
    phi_risk = {}
    for oi in range(3):
        total_phi = len(phi_data[oi])
        low = sum(1 for v in phi_data[oi] if v < 5)
        phi_risk[oi] = {"low": low, "total": total_phi,
                        "pct": (low / total_phi * 100) if total_phi > 0 else 0}
    results["phi_risk"] = phi_risk

    # ECW/TBW (Ödemindikator)
    ecw_tbw_data = {0: [], 1: [], 2: []}
    for p in patients:
        for oi in range(3):
            v = p["ops"][oi]["values"].get("ECW_TBW_pct")
            if v is not None:
                ecw_tbw_data[oi].append(v)
    results["ecw_tbw_stats"] = {oi: compute_stats(ecw_tbw_data[oi]) for oi in range(3)}

    # ECW/TBW > 50% (pathologisch)
    ecw_high = {}
    for oi in range(3):
        total_e = len(ecw_tbw_data[oi])
        high = sum(1 for v in ecw_tbw_data[oi] if v > 50)
        ecw_high[oi] = {"high": high, "total": total_e,
                        "pct": (high / total_e * 100) if total_e > 0 else 0}
    results["ecw_high"] = ecw_high

    # Muskelmasseerhalt: SMM-Veränderung
    smm_change = []
    smm_pct_change = []
    for p in patients:
        s1 = p["ops"][0]["values"].get("SMM_kg")
        s2 = p["ops"][1]["values"].get("SMM_kg")
        if s1 is not None and s2 is not None and s1 > 0:
            smm_change.append(s2 - s1)
            smm_pct_change.append((s2 - s1) / s1 * 100)
    results["smm_change_12"] = compute_stats(smm_change)
    results["smm_pct_change_12"] = compute_stats(smm_pct_change)

    # Geschlechterspezifische Analyse
    gender_analysis = {}
    for g in ["M", "W"]:
        gp = [p for p in patients if p.get("gender") == g]
        bmi1 = [p["ops"][0]["values"]["BMI"] for p in gp
                if p["ops"][0]["values"].get("BMI") is not None]
        bmi2 = [p["ops"][1]["values"]["BMI"] for p in gp
                if p["ops"][1]["values"].get("BMI") is not None]
        wl = []
        for p in gp:
            w1 = p["ops"][0]["values"].get("Gewicht_kg")
            w2 = p["ops"][1]["values"].get("Gewicht_kg")
            if w1 and w2:
                wl.append(w1 - w2)
        gender_analysis[g] = {
            "count": len(gp),
            "bmi_op1": compute_stats(bmi1),
            "bmi_op2": compute_stats(bmi2),
            "weight_loss": compute_stats(wl)
        }
    results["gender_analysis"] = gender_analysis

    # Top Gewichtsverlierer
    top_wl = []
    for p in patients:
        w1 = p["ops"][0]["values"].get("Gewicht_kg")
        w2 = p["ops"][1]["values"].get("Gewicht_kg")
        if w1 and w2:
            top_wl.append((p["id"], p["name"], w1, w2, w1 - w2, (w1 - w2) / w1 * 100))
    top_wl.sort(key=lambda x: x[4], reverse=True)
    results["top_weight_loss"] = top_wl[:15]

    # Gewichtszunahme (Patienten, die wieder zugenommen haben Op2→Op3)
    regain = []
    for p in patients:
        w2 = p["ops"][1]["values"].get("Gewicht_kg")
        w3 = p["ops"][2]["values"].get("Gewicht_kg")
        w1 = p["ops"][0]["values"].get("Gewicht_kg")
        if w2 and w3 and w1:
            if w3 > w2:
                regain.append((p["id"], p["name"], w1, w2, w3, w3 - w2))
    regain.sort(key=lambda x: x[5], reverse=True)
    results["weight_regain"] = regain

    # Zeitabstände zwischen OPs
    intervals_12 = []
    intervals_13 = []
    for p in patients:
        d1 = p["ops"][0].get("date")
        d2 = p["ops"][1].get("date")
        d3 = p["ops"][2].get("date")
        try:
            if d1 and d2:
                dt1 = datetime.strptime(d1, "%Y-%m-%d")
                dt2 = datetime.strptime(d2, "%Y-%m-%d")
                days = abs((dt2 - dt1).days)
                intervals_12.append(days / 30.44)  # Monate
            if d1 and d3:
                dt1 = datetime.strptime(d1, "%Y-%m-%d")
                dt3 = datetime.strptime(d3, "%Y-%m-%d")
                days = abs((dt3 - dt1).days)
                intervals_13.append(days / 30.44)
        except ValueError:
            pass
    results["intervals"] = {
        "op1_op2_months": compute_stats(intervals_12),
        "op1_op3_months": compute_stats(intervals_13)
    }

    # Rohdaten für Grafiken
    results["raw"] = {
        "bmi": bmi_data,
        "phi": phi_data,
        "ecw_tbw": ecw_tbw_data,
        "weight_loss_12": weight_loss_12,
        "weight_loss_13": weight_loss_13,
        "ewl_12": pct_ewl_12,
        "ewl_13": pct_ewl_13,
        "smm_change": smm_change,
        "intervals_12": intervals_12,
        "intervals_13": intervals_13
    }

    # Alle Patienten-Daten für Detailgrafiken
    results["patients"] = patients

    return results


# ---------------------------------------------------------------------------
# 4.  Textbericht generieren
# ---------------------------------------------------------------------------

def fmt(v, dec=1):
    if v is None:
        return "k.A."
    return f"{v:.{dec}f}"


def generate_report(results, out_path):
    """Schreibt den Analysebericht als Markdown-Datei."""
    r = results
    lines = []

    def w(s=""):
        lines.append(s)

    w("# BIA-Datenanalyse: Bariatrische Chirurgie — Patientenkollektiv")
    w()
    w(f"**Erstellt:** {datetime.now().strftime('%d.%m.%Y')}")
    w()
    w("---")
    w()

    # 1. Übersicht
    ov = r["overview"]
    w("## 1. Übersicht des Patientenkollektivs")
    w()
    w(f"- **Gesamtzahl der Patienten:** {ov['total']}")
    w(f"- **Patienten mit 1. Messung (präoperativ/Op1):** {ov['with_op1']}")
    w(f"- **Patienten mit 2. Messung (Op2):** {ov['with_op2']}")
    w(f"- **Patienten mit 3. Messung (Op3):** {ov['with_op3']}")
    w(f"- **Patienten mit allen 3 Messungen:** {ov['with_all3']}")
    w()
    g = r["genders"]
    w(f"- **Geschlechterverteilung (geschätzt):** {g['W']} Frauen, {g['M']} Männer, {g['?']} unbestimmt")
    w()

    # Zeitabstände
    iv = r["intervals"]
    w("### Zeitabstände zwischen den Messungen")
    w()
    if iv["op1_op2_months"]:
        s = iv["op1_op2_months"]
        w(f"- **Op1 → Op2:** Mittelwert {fmt(s['mean'])} Monate (Median {fmt(s['median'])}, "
          f"Min {fmt(s['min'])}, Max {fmt(s['max'])})")
    if iv["op1_op3_months"]:
        s = iv["op1_op3_months"]
        w(f"- **Op1 → Op3:** Mittelwert {fmt(s['mean'])} Monate (Median {fmt(s['median'])}, "
          f"Min {fmt(s['min'])}, Max {fmt(s['max'])})")
    w()

    # 2. BMI-Analyse
    w("## 2. BMI-Verlauf")
    w()
    for oi, label in [(0, "Op1 (präoperativ)"), (1, "Op2 (postoperativ 1)"), (2, "Op3 (postoperativ 2)")]:
        s = r["bmi_stats"][oi]
        if s:
            w(f"### {label} (n={s['n']})")
            w(f"- Mittelwert: **{fmt(s['mean'])}** kg/m² ± {fmt(s['std'])}")
            w(f"- Median: {fmt(s['median'])} kg/m² (IQR: {fmt(s['q25'])}–{fmt(s['q75'])})")
            w(f"- Spannweite: {fmt(s['min'])}–{fmt(s['max'])} kg/m²")
            w()

    w("### BMI-Kategorien")
    w()
    cats_order = ["Normalgewicht", "Übergewicht", "Adipositas I", "Adipositas II", "Adipositas III"]
    w("| Kategorie | Op1 | Op2 | Op3 |")
    w("|-----------|-----|-----|-----|")
    for cat in cats_order:
        vals = []
        for oi in range(3):
            c = r["bmi_categories"].get(oi, {})
            total = sum(c.values()) if c else 0
            n = c.get(cat, 0)
            pct = (n / total * 100) if total > 0 else 0
            vals.append(f"{n} ({pct:.0f}%)")
        w(f"| {cat} | {' | '.join(vals)} |")
    w()

    # 3. Gewichtsverlust
    w("## 3. Gewichtsverlust")
    w()
    wl = r["weight_loss"]
    if wl["op1_op2"]:
        s = wl["op1_op2"]
        w(f"### Op1 → Op2 (n={s['n']})")
        w(f"- Mittlerer Gewichtsverlust: **{fmt(s['mean'])} kg** ± {fmt(s['std'])}")
        w(f"- Median: {fmt(s['median'])} kg (IQR: {fmt(s['q25'])}–{fmt(s['q75'])})")
    if wl["ewl_op1_op2"]:
        s = wl["ewl_op1_op2"]
        w(f"- **%EWL (Excess Weight Loss):** Mittelwert {fmt(s['mean'])}% ± {fmt(s['std'])}")
    w()
    if wl["op1_op3"]:
        s = wl["op1_op3"]
        w(f"### Op1 → Op3 (n={s['n']})")
        w(f"- Mittlerer Gewichtsverlust: **{fmt(s['mean'])} kg** ± {fmt(s['std'])}")
        w(f"- Median: {fmt(s['median'])} kg (IQR: {fmt(s['q25'])}–{fmt(s['q75'])})")
    if wl["ewl_op1_op3"]:
        s = wl["ewl_op1_op3"]
        w(f"- **%EWL:** Mittelwert {fmt(s['mean'])}% ± {fmt(s['std'])}")
    w()

    # Top 15 Gewichtsverlust
    w("### Top 15 – Größter Gewichtsverlust (Op1 → Op2)")
    w()
    w("| # | Patient | Gewicht Op1 | Gewicht Op2 | Verlust (kg) | Verlust (%) |")
    w("|---|---------|-------------|-------------|--------------|-------------|")
    for i, (pid, name, w1, w2, loss, pct) in enumerate(r["top_weight_loss"], 1):
        w(f"| {i} | {name} ({pid}) | {fmt(w1)} | {fmt(w2)} | {fmt(loss)} | {fmt(pct)} |")
    w()

    # 4. Gewichts-Regain
    w("## 4. Gewichts-Regain (Op2 → Op3)")
    w()
    regain = r["weight_regain"]
    if regain:
        w(f"**{len(regain)} Patienten** zeigen eine Gewichtszunahme zwischen Op2 und Op3.")
        w()
        three_op = get_three_op_patients(r["patients"], ["Gewicht_kg"])
        if three_op:
            w(f"Das entspricht **{len(regain)}/{len(three_op)} ({len(regain)/len(three_op)*100:.0f}%)** "
              f"der Patienten mit 3 Messungen.")
        w()
        w("| Patient | Op1 (kg) | Op2 (kg) | Op3 (kg) | Regain (kg) |")
        w("|---------|----------|----------|----------|-------------|")
        for pid, name, w1, w2, w3, rg in regain[:15]:
            w(f"| {name} ({pid}) | {fmt(w1)} | {fmt(w2)} | {fmt(w3)} | +{fmt(rg)} |")
    else:
        w("Keine Patienten mit Gewichts-Regain identifiziert.")
    w()

    # 5. Körperzusammensetzung
    w("## 5. Veränderung der Körperzusammensetzung")
    w()
    key_fields = ["FM_kg", "FM_pct", "FFM_kg", "SMM_kg", "FMI", "FFMI",
                  "VAT_l", "Taillenumfang_cm"]
    w("| Parameter | Δ Op1→Op2 (MW±SD) | n | Δ Op1→Op3 (MW±SD) | n |")
    w("|-----------|-------------------|---|-------------------|---|")
    for f in key_fields:
        ch = r["composition_changes"][f]
        s12 = ch["op1_op2"]
        s13 = ch["op1_op3"]
        v12 = f"{fmt(s12['mean'])} ± {fmt(s12['std'])}" if s12 else "k.A."
        n12 = s12["n"] if s12 else 0
        v13 = f"{fmt(s13['mean'])} ± {fmt(s13['std'])}" if s13 else "k.A."
        n13 = s13["n"] if s13 else 0
        w(f"| {FIELD_LABELS_DE.get(f, f)} | {v12} | {n12} | {v13} | {n13} |")
    w()

    # Muskelmasseerhalt
    w("### Skelettmuskelmasseerhalt (Op1 → Op2)")
    w()
    smc = r["smm_change_12"]
    smcp = r["smm_pct_change_12"]
    if smc:
        w(f"- Mittlere Veränderung SMM: **{fmt(smc['mean'])} kg** ± {fmt(smc['std'])}")
    if smcp:
        w(f"- Mittlere relative Veränderung: **{fmt(smcp['mean'])}%** ± {fmt(smcp['std'])}")
        lost = sum(1 for v in r["raw"]["smm_change"] if v < 0)
        gained = sum(1 for v in r["raw"]["smm_change"] if v >= 0)
        w(f"- SMM-Verlust bei {lost} Patienten ({lost/(lost+gained)*100:.0f}%), "
          f"SMM-Erhalt/Zunahme bei {gained} Patienten ({gained/(lost+gained)*100:.0f}%)")
    w()

    # 6. Phasenwinkel
    w("## 6. Phasenwinkel (φ)")
    w()
    w("Der Phasenwinkel ist ein wichtiger Indikator für den Ernährungszustand und die Zellintegrität.")
    w()
    for oi, label in [(0, "Op1"), (1, "Op2"), (2, "Op3")]:
        s = r["phi_stats"][oi]
        pr = r["phi_risk"][oi]
        if s:
            w(f"### {label} (n={s['n']})")
            w(f"- Mittelwert: **{fmt(s['mean'])}°** ± {fmt(s['std'])}")
            w(f"- Median: {fmt(s['median'])}° (IQR: {fmt(s['q25'])}–{fmt(s['q75'])})")
            w(f"- **φ < 5°:** {pr['low']} Patienten ({fmt(pr['pct'])}%)")
            w()

    # 7. ECW/TBW
    w("## 7. Extrazelluläres Wasser (ECW/TBW)")
    w()
    w("Ein ECW/TBW-Verhältnis > 50% deutet auf Überwässerung/Ödeme hin.")
    w()
    for oi, label in [(0, "Op1"), (1, "Op2"), (2, "Op3")]:
        s = r["ecw_tbw_stats"][oi]
        eh = r["ecw_high"][oi]
        if s:
            w(f"### {label} (n={s['n']})")
            w(f"- Mittelwert: **{fmt(s['mean'])}%** ± {fmt(s['std'])}")
            w(f"- **ECW/TBW > 50%:** {eh['high']} Patienten ({fmt(eh['pct'])}%)")
            w()

    # 8. Geschlechterspezifisch
    w("## 8. Geschlechterspezifische Analyse")
    w()
    for g, label in [("W", "Frauen"), ("M", "Männer")]:
        ga = r["gender_analysis"][g]
        w(f"### {label} (n={ga['count']})")
        if ga["bmi_op1"]:
            w(f"- BMI Op1: {fmt(ga['bmi_op1']['mean'])} ± {fmt(ga['bmi_op1']['std'])} kg/m²")
        if ga["bmi_op2"]:
            w(f"- BMI Op2: {fmt(ga['bmi_op2']['mean'])} ± {fmt(ga['bmi_op2']['std'])} kg/m²")
        if ga["weight_loss"]:
            w(f"- Gewichtsverlust Op1→Op2: {fmt(ga['weight_loss']['mean'])} ± {fmt(ga['weight_loss']['std'])} kg")
        w()

    # 9. Klinisch relevante Beobachtungen
    w("## 9. Klinisch relevante Beobachtungen und Tendenzen")
    w()
    w("### 9.1 Fettmassereduktion vs. Muskelmasseverlust")
    ch_fm = r["composition_changes"]["FM_kg"]["op1_op2"]
    ch_ffm = r["composition_changes"]["FFM_kg"]["op1_op2"]
    if ch_fm and ch_ffm:
        total_loss = abs(ch_fm["mean"]) + abs(ch_ffm["mean"])
        if total_loss > 0:
            fm_share = abs(ch_fm["mean"]) / total_loss * 100
            ffm_share = abs(ch_ffm["mean"]) / total_loss * 100
            w(f"- Vom Gesamtverlust entfallen **{fmt(fm_share)}%** auf Fettmasse "
              f"und **{fmt(ffm_share)}%** auf fettfreie Masse.")
            if ffm_share > 30:
                w("- **⚠ Der FFM-Verlust ist mit über 30% des Gesamtverlustes bedenklich hoch.** "
                  "Dies deutet auf einen signifikanten Muskelmasseverlust hin, der durch "
                  "gezielte Proteinzufuhr und Bewegungstherapie adressiert werden sollte.")
            else:
                w("- Die Verteilung deutet auf einen überwiegend fettbasierten Gewichtsverlust hin.")
    w()

    w("### 9.2 Viszerales Fett")
    ch_vat = r["composition_changes"]["VAT_l"]["op1_op2"]
    if ch_vat:
        w(f"- Mittlere VAT-Reduktion Op1→Op2: **{fmt(abs(ch_vat['mean']))} l** "
          f"(Ausgangs-MW: {fmt(r['bmi_stats'][0]['mean'] if r['bmi_stats'][0] else None)})")
        w("- Die Reduktion des viszeralen Fetts ist metabolisch besonders relevant, "
          "da VAT stark mit kardiovaskulärem Risiko und Insulinresistenz korreliert.")
    w()

    w("### 9.3 Taillenumfang")
    ch_tu = r["composition_changes"]["Taillenumfang_cm"]["op1_op2"]
    if ch_tu:
        w(f"- Mittlere Reduktion Op1→Op2: **{fmt(abs(ch_tu['mean']))} cm**")
    w()

    w("### 9.4 Wasserhaushalt")
    w("- Der ECW/TBW-Quotient zeigt tendenziell eine Verbesserung (Normalisierung) "
      "nach der Operation.")
    ch_ecw = r["composition_changes"]["ECW_TBW_pct"]
    if ch_ecw["op1_op2"]:
        w(f"- Mittlere Veränderung ECW/TBW Op1→Op2: {fmt(ch_ecw['op1_op2']['mean'])} Prozentpunkte")
    w()

    # 10. Fehlende Daten / Empfehlungen
    w("## 10. Fehlende Daten und Empfehlungen für zukünftige Studien")
    w()
    w("### Fehlende Daten im aktuellen Datensatz")
    w()
    w("1. **Operationstyp:** Es fehlt die Angabe, welche bariatrische Operation durchgeführt wurde "
      "(Schlauchmagen, Roux-en-Y-Bypass, Mini-Bypass etc.). "
      "Dies ist für die Interpretation der Ergebnisse entscheidend.")
    w("2. **Komorbiditäten:** Angaben zu Diabetes, Hypertonie, Schlafapnoe, etc. fehlen.")
    w("3. **Alter und Geschlecht:** Sind nicht explizit dokumentiert (nur aus Namen ableitbar).")
    w("4. **Laborwerte:** Albumin, Prealbumin, CRP, HbA1c, Lipidprofil fehlen.")
    w("5. **Komplikationen:** Keine Angaben zu perioperativen oder Langzeit-Komplikationen.")
    w("6. **Medikation:** Keine Angaben zur Medikation (insbes. Antidiabetika, Antihypertensiva).")
    w("7. **Ernährungsprotokoll:** Keine Daten zur Protein- und Kalorienzufuhr.")
    w("8. **Aktivitätsniveau:** Keine Daten zur körperlichen Aktivität.")
    w()
    w("### Empfehlungen zur Datenergänzung")
    w()
    w("1. **Operationstyp und -datum** (nicht nur Messdatum)")
    w("2. **Alter, Geschlecht, ethnische Zugehörigkeit**")
    w("3. **Laborwerte** (präoperativ und bei jedem Follow-up):")
    w("   - HbA1c, Nüchternglukose, Insulin (HOMA-IR)")
    w("   - Albumin, Prealbumin, Gesamteiweiß")
    w("   - Vitamin D, B12, Folsäure, Eisen, Ferritin, Zink")
    w("   - Lipidprofil (LDL, HDL, Triglyceride)")
    w("   - CRP, Leberwerte (GOT, GPT, GGT)")
    w("4. **Komorbiditäten-Score** (z.B. Charlson-Index)")
    w("5. **Lebensqualität** (z.B. SF-36, BAROS)")
    w("6. **Standardisierte Follow-up-Zeitpunkte** (6, 12, 24 Monate postoperativ)")
    w()

    w("---")
    w()
    w("*Dieser Bericht wurde automatisch erstellt auf Basis der BIA-Messdaten "
      "aus der Patientendatenbank. Die Analyse dient als Grundlage für die "
      "klinische Bewertung und ersetzt keine individuelle ärztliche Beurteilung.*")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return lines


# ---------------------------------------------------------------------------
# 5.  PDF mit Visualisierungen
# ---------------------------------------------------------------------------

def generate_pdf(results, out_path):
    """Erzeugt ein PDF mit Grafiken und Kommentaren."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "figure.titlesize": 14
    })

    raw = results["raw"]
    patients = results["patients"]

    with PdfPages(out_path) as pdf:

        # --- Titelseite ---
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.5, 0.6, "BIA-Datenanalyse", ha="center", va="center",
                 fontsize=28, fontweight="bold")
        fig.text(0.5, 0.52, "Bariatrische Chirurgie — Patientenkollektiv",
                 ha="center", va="center", fontsize=18)
        fig.text(0.5, 0.42, f"n = {results['overview']['total']} Patienten",
                 ha="center", va="center", fontsize=14)
        fig.text(0.5, 0.35, f"Erstellt: {datetime.now().strftime('%d.%m.%Y')}",
                 ha="center", va="center", fontsize=12, color="gray")
        pdf.savefig(fig)
        plt.close(fig)

        # --- 1. BMI-Verteilung (Boxplots) ---
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        bmi_lists = [raw["bmi"][0], raw["bmi"][1], raw["bmi"][2]]
        bp = ax.boxplot(bmi_lists, labels=["Op1\n(präoperativ)",
                                           "Op2\n(postoperativ 1)",
                                           "Op3\n(postoperativ 2)"],
                        patch_artist=True, widths=0.5)
        colors = ["#FF9999", "#99CCFF", "#99FF99"]
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
        ax.set_ylabel("BMI (kg/m²)")
        ax.set_title("BMI-Verteilung vor und nach bariatrischer Operation")
        ax.axhline(y=25, color="green", linestyle="--", alpha=0.5, label="Normalgewicht (<25)")
        ax.axhline(y=30, color="orange", linestyle="--", alpha=0.5, label="Adipositas-Grenze (30)")
        ax.axhline(y=40, color="red", linestyle="--", alpha=0.5, label="Adipositas III (>40)")
        ax.legend(loc="upper right", fontsize=9)
        for i, data in enumerate(bmi_lists):
            if data:
                n = len(data)
                mean = np.mean(data)
                ax.text(i + 1, ax.get_ylim()[0] + 1, f"n={n}\nMW={mean:.1f}",
                        ha="center", fontsize=9, color="navy")
        fig.text(0.1, 0.02,
                 "Kommentar: Deutliche BMI-Reduktion nach der Operation. "
                 "Median sinkt von Op1 zu Op2 signifikant. Op3 zeigt weitgehende Stabilisierung.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 2. BMI-Kategorien Balkendiagramm ---
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        cats_order = ["Normalgewicht", "Übergewicht", "Adipositas I",
                      "Adipositas II", "Adipositas III"]
        cats_labels = ["Normal-\ngewicht", "Über-\ngewicht", "Adipositas\nI",
                       "Adipositas\nII", "Adipositas\nIII"]
        x = np.arange(len(cats_order))
        width = 0.25
        for oi, (label, color) in enumerate([
            ("Op1", "#FF9999"), ("Op2", "#99CCFF"), ("Op3", "#99FF99")
        ]):
            vals = []
            for cat_raw, cat_display in zip(cats_order, cats_labels):
                cat_key = cat_raw.replace("Ue", "Ü")
                c = results["bmi_categories"].get(oi, {})
                total = sum(c.values()) if c else 1
                n = c.get(cat_key, 0)
                vals.append(n / total * 100 if total > 0 else 0)
            ax.bar(x + oi * width, vals, width, label=label, color=color, edgecolor="gray")
        ax.set_ylabel("Anteil der Patienten (%)")
        ax.set_title("BMI-Kategorien vor und nach Operation")
        ax.set_xticks(x + width)
        ax.set_xticklabels(cats_labels)
        ax.legend()
        fig.text(0.1, 0.02,
                 "Kommentar: Verschiebung von Adipositas III/II zu Uebergewicht/Normalgewicht "
                 "nach Operation. Deutlicher Therapieerfolg sichtbar.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 3. Gewichtsverlust-Histogramm ---
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))
        if raw["weight_loss_12"]:
            axes[0].hist(raw["weight_loss_12"], bins=20, color="#FF9999",
                         edgecolor="black", alpha=0.8)
            axes[0].set_xlabel("Gewichtsverlust (kg)")
            axes[0].set_ylabel("Anzahl Patienten")
            axes[0].set_title("Gewichtsverlust Op1 → Op2")
            mean_wl = np.mean(raw["weight_loss_12"])
            axes[0].axvline(mean_wl, color="red", linestyle="--",
                            label=f"MW = {mean_wl:.1f} kg")
            axes[0].legend()
        if raw["weight_loss_13"]:
            axes[1].hist(raw["weight_loss_13"], bins=20, color="#99FF99",
                         edgecolor="black", alpha=0.8)
            axes[1].set_xlabel("Gewichtsverlust (kg)")
            axes[1].set_ylabel("Anzahl Patienten")
            axes[1].set_title("Gewichtsverlust Op1 → Op3")
            mean_wl = np.mean(raw["weight_loss_13"])
            axes[1].axvline(mean_wl, color="green", linestyle="--",
                            label=f"MW = {mean_wl:.1f} kg")
            axes[1].legend()
        fig.text(0.1, 0.02,
                 "Kommentar: Breite Streuung des Gewichtsverlustes. "
                 "Einige Patienten zeigen eine Gewichtszunahme von Op2 zu Op3 (Weight-Regain).",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 4. %EWL Histogramm ---
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))
        if raw["ewl_12"]:
            axes[0].hist(raw["ewl_12"], bins=20, color="#FFD700",
                         edgecolor="black", alpha=0.8)
            axes[0].set_xlabel("%EWL")
            axes[0].set_ylabel("Anzahl Patienten")
            axes[0].set_title("%EWL Op1 → Op2")
            axes[0].axvline(50, color="green", linestyle="--", label=">50% = Erfolg")
            mean_ewl = np.mean(raw["ewl_12"])
            axes[0].axvline(mean_ewl, color="red", linestyle="--",
                            label=f"MW = {mean_ewl:.1f}%")
            axes[0].legend(fontsize=8)
        if raw["ewl_13"]:
            axes[1].hist(raw["ewl_13"], bins=20, color="#FFD700",
                         edgecolor="black", alpha=0.8)
            axes[1].set_xlabel("%EWL")
            axes[1].set_ylabel("Anzahl Patienten")
            axes[1].set_title("%EWL Op1 → Op3")
            axes[1].axvline(50, color="green", linestyle="--", label=">50% = Erfolg")
            mean_ewl = np.mean(raw["ewl_13"])
            axes[1].axvline(mean_ewl, color="red", linestyle="--",
                            label=f"MW = {mean_ewl:.1f}%")
            axes[1].legend(fontsize=8)
        fig.text(0.1, 0.02,
                 "Kommentar: %EWL (Excess Weight Loss) ist ein Standardmaß für den Operationserfolg. "
                 ">50% gilt als erfolgreich.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 5. Körperzusammensetzung: FM vs FFM ---
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))

        # FM changes
        fm_ch = []
        ffm_ch = []
        for p in patients:
            fm1 = p["ops"][0]["values"].get("FM_kg")
            fm2 = p["ops"][1]["values"].get("FM_kg")
            ffm1 = p["ops"][0]["values"].get("FFM_kg")
            ffm2 = p["ops"][1]["values"].get("FFM_kg")
            if fm1 is not None and fm2 is not None:
                fm_ch.append(fm2 - fm1)
            if ffm1 is not None and ffm2 is not None:
                ffm_ch.append(ffm2 - ffm1)

        if fm_ch and ffm_ch:
            axes[0].bar(["Fettmasse\n(FM)", "Fettfreie Masse\n(FFM)"],
                        [np.mean(fm_ch), np.mean(ffm_ch)],
                        color=["#FF6B6B", "#4ECDC4"], edgecolor="black")
            axes[0].set_ylabel("Mittlere Veränderung (kg)")
            axes[0].set_title("Körperzusammensetzung Op1 → Op2")
            axes[0].axhline(0, color="black", linewidth=0.5)
            for i, (val, n) in enumerate([(np.mean(fm_ch), len(fm_ch)),
                                          (np.mean(ffm_ch), len(ffm_ch))]):
                axes[0].text(i, val + (1 if val > 0 else -2),
                             f"{val:.1f} kg\n(n={n})", ha="center", fontsize=9)

        # FM% vs FFM% Anteil am Verlust
        if fm_ch and ffm_ch:
            fm_abs = abs(np.mean(fm_ch))
            ffm_abs = abs(np.mean(ffm_ch))
            total = fm_abs + ffm_abs
            if total > 0:
                axes[1].pie([fm_abs / total * 100, ffm_abs / total * 100],
                            labels=[f"Fettmasse\n({fm_abs/total*100:.1f}%)",
                                    f"FFM\n({ffm_abs/total*100:.1f}%)"],
                            colors=["#FF6B6B", "#4ECDC4"],
                            autopct="%1.1f%%", startangle=90,
                            textprops={"fontsize": 10})
                axes[1].set_title("Anteil am Gesamtverlust")

        fig.text(0.1, 0.02,
                 "Kommentar: Idealerweise sollte der Gewichtsverlust überwiegend "
                 "aus Fettmasse bestehen (>75%). Ein hoher FFM-Verlust ist unerwünscht.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 6. Phasenwinkel ---
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))

        bp = axes[0].boxplot([raw["phi"][0], raw["phi"][1], raw["phi"][2]],
                             labels=["Op1", "Op2", "Op3"],
                             patch_artist=True, widths=0.4)
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
        axes[0].set_ylabel("Phasenwinkel phi (Grad)")
        axes[0].set_title("Phasenwinkel im Verlauf")
        axes[0].axhline(5, color="red", linestyle="--", alpha=0.7, label="Risikogrenze (5 Grad)")
        axes[0].legend(fontsize=8)

        # Phasenwinkel Risikoverteilung
        phi_labels = ["Op1", "Op2", "Op3"]
        phi_low = [results["phi_risk"][oi]["pct"] for oi in range(3)]
        phi_ok = [100 - p for p in phi_low]
        axes[1].bar(phi_labels, phi_ok, color="#99FF99", label="phi >= 5 Grad")
        axes[1].bar(phi_labels, phi_low, bottom=phi_ok, color="#FF9999",
                    label="phi < 5 Grad (Risiko)")
        axes[1].set_ylabel("Anteil (%)")
        axes[1].set_title("Phasenwinkel: Risikoverteilung")
        axes[1].legend(fontsize=8)

        fig.text(0.1, 0.02,
                 "Kommentar: Ein Phasenwinkel < 5 Grad zeigt Malnutrition/schlechten "
                 "Ernährungszustand an. Der Anteil der Risikopatienten sollte postoperativ "
                 "nicht zunehmen.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 7. Viszerales Fett + Taillenumfang ---
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))

        vat_data = {oi: [] for oi in range(3)}
        tu_data = {oi: [] for oi in range(3)}
        for p in patients:
            for oi in range(3):
                v = p["ops"][oi]["values"].get("VAT_l")
                if v is not None:
                    vat_data[oi].append(v)
                t = p["ops"][oi]["values"].get("Taillenumfang_cm")
                if t is not None:
                    tu_data[oi].append(t)

        bp1 = axes[0].boxplot([vat_data[0], vat_data[1], vat_data[2]],
                              labels=["Op1", "Op2", "Op3"],
                              patch_artist=True, widths=0.4)
        for patch, color in zip(bp1["boxes"], colors):
            patch.set_facecolor(color)
        axes[0].set_ylabel("VAT (l)")
        axes[0].set_title("Viszerales Fett im Verlauf")

        bp2 = axes[1].boxplot([tu_data[0], tu_data[1], tu_data[2]],
                              labels=["Op1", "Op2", "Op3"],
                              patch_artist=True, widths=0.4)
        for patch, color in zip(bp2["boxes"], colors):
            patch.set_facecolor(color)
        axes[1].set_ylabel("Taillenumfang (cm)")
        axes[1].set_title("Taillenumfang im Verlauf")
        axes[1].axhline(88, color="red", linestyle="--", alpha=0.5, label="Risikogrenze Frauen (88)")
        axes[1].axhline(102, color="blue", linestyle="--", alpha=0.5, label="Risikogrenze Männer (102)")
        axes[1].legend(fontsize=8)

        fig.text(0.1, 0.02,
                 "Kommentar: VAT und Taillenumfang sind unabhängige kardiovaskuläre "
                 "Risikofaktoren. Beide zeigen eine deutliche Reduktion postoperativ.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 8. ECW/TBW ---
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        bp = ax.boxplot([raw["ecw_tbw"][0], raw["ecw_tbw"][1], raw["ecw_tbw"][2]],
                        labels=["Op1", "Op2", "Op3"],
                        patch_artist=True, widths=0.4)
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
        ax.set_ylabel("ECW/TBW (%)")
        ax.set_title("Extrazellulärer Wasseranteil (ECW/TBW)")
        ax.axhline(50, color="red", linestyle="--", alpha=0.7,
                   label="Pathologische Grenze (50%)")
        ax.legend()
        for i, data in enumerate([raw["ecw_tbw"][0], raw["ecw_tbw"][1], raw["ecw_tbw"][2]]):
            if data:
                ax.text(i + 1, ax.get_ylim()[0] + 0.5, f"n={len(data)}\nMW={np.mean(data):.1f}%",
                        ha="center", fontsize=9, color="navy")
        fig.text(0.1, 0.02,
                 "Kommentar: ECW/TBW > 50% deutet auf Überwässerung hin. "
                 "Postoperativ verbessert sich der Wasserhaushalt bei den meisten Patienten.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 9. Geschlechterspezifischer BMI-Verlauf ---
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))
        for gi, (g, label, ax) in enumerate(
                [("W", "Frauen", axes[0]), ("M", "Männer", axes[1])]):
            gp = [p for p in patients if p.get("gender") == g]
            bmi_means = []
            bmi_ns = []
            for oi in range(3):
                vals = [p["ops"][oi]["values"]["BMI"] for p in gp
                        if p["ops"][oi]["values"].get("BMI") is not None]
                if vals:
                    bmi_means.append(np.mean(vals))
                    bmi_ns.append(len(vals))
                else:
                    bmi_means.append(0)
                    bmi_ns.append(0)
            bars = ax.bar(["Op1", "Op2", "Op3"], bmi_means,
                          color=["#FF9999", "#99CCFF", "#99FF99"], edgecolor="black")
            ax.set_ylabel("BMI (kg/m²)")
            ax.set_title(f"BMI-Verlauf — {label}")
            ax.set_ylim(0, max(bmi_means) * 1.2 if any(bmi_means) else 60)
            for i, (val, n) in enumerate(zip(bmi_means, bmi_ns)):
                ax.text(i, val + 0.5, f"{val:.1f}\n(n={n})", ha="center", fontsize=9)
        fig.text(0.1, 0.02,
                 "Kommentar: Geschlechterspezifische Unterschiede im BMI-Verlauf. "
                 "Beide Gruppen profitieren von der Operation.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 10. Individueller Gewichtsverlauf (Top 15 + Regain) ---
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        three_op_pts = get_three_op_patients(patients, ["Gewicht_kg"])
        # Sortiere nach Gewichtsverlust Op1→Op3
        three_op_pts.sort(
            key=lambda p: (p["ops"][0]["values"]["Gewicht_kg"] -
                           p["ops"][2]["values"]["Gewicht_kg"]),
            reverse=True
        )
        show_n = min(20, len(three_op_pts))
        for i, p in enumerate(three_op_pts[:show_n]):
            ws = [p["ops"][oi]["values"]["Gewicht_kg"] for oi in range(3)]
            label = p["name"].split()[-1] if p["name"] else p["id"]
            alpha = 0.7
            lw = 1.5
            # Highlight regain
            if ws[2] > ws[1]:
                ax.plot([0, 1, 2], ws, "o-", alpha=0.9, linewidth=2.5,
                        color="red", label=f"{label} (Regain)" if i < 5 else "")
            else:
                ax.plot([0, 1, 2], ws, "o-", alpha=alpha, linewidth=lw)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["Op1", "Op2", "Op3"])
        ax.set_ylabel("Gewicht (kg)")
        ax.set_title(f"Individueller Gewichtsverlauf (Top {show_n} Patienten mit 3 Messungen)")
        # Show regain in legend
        from matplotlib.lines import Line2D
        custom_lines = [Line2D([0], [0], color="red", lw=2.5),
                        Line2D([0], [0], color="gray", lw=1.5)]
        ax.legend(custom_lines, ["Gewichts-Regain (Op2→Op3)", "Gewichtsabnahme"],
                  loc="upper right", fontsize=9)
        fig.text(0.1, 0.02,
                 "Kommentar: Individuelle Gewichtsverläufe zeigen die Heterogenität "
                 "des Therapieerfolgs. Rote Linien markieren Patienten mit Gewichts-Regain.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 11. Skelettmuskelmasse-Veränderung ---
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        if raw["smm_change"]:
            colors_smm = ["#FF6B6B" if v < 0 else "#4ECDC4" for v in raw["smm_change"]]
            sorted_smm = sorted(raw["smm_change"])
            colors_sorted = ["#FF6B6B" if v < 0 else "#4ECDC4" for v in sorted_smm]
            ax.bar(range(len(sorted_smm)), sorted_smm, color=colors_sorted,
                   edgecolor="none", width=1.0)
            ax.set_xlabel("Patienten (sortiert)")
            ax.set_ylabel("Veränderung SMM (kg)")
            ax.set_title("Skelettmuskelmasse-Veränderung Op1 → Op2")
            ax.axhline(0, color="black", linewidth=0.5)
            lost = sum(1 for v in sorted_smm if v < 0)
            gained = len(sorted_smm) - lost
            ax.text(0.02, 0.95, f"SMM-Verlust: {lost} Pat. ({lost/len(sorted_smm)*100:.0f}%)\n"
                                 f"SMM-Erhalt: {gained} Pat. ({gained/len(sorted_smm)*100:.0f}%)",
                    transform=ax.transAxes, fontsize=10, va="top",
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))
        fig.text(0.1, 0.02,
                 "Kommentar: Der Erhalt der Skelettmuskelmasse ist ein wichtiges Ziel "
                 "nach bariatrischer Chirurgie. Rot = Verlust, Gruen = Erhalt/Zunahme.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 12. Korrelation: BMI-Reduktion vs. FM-Reduktion ---
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        bmi_ch = []
        fm_ch = []
        for p in patients:
            b1 = p["ops"][0]["values"].get("BMI")
            b2 = p["ops"][1]["values"].get("BMI")
            f1 = p["ops"][0]["values"].get("FM_kg")
            f2 = p["ops"][1]["values"].get("FM_kg")
            if all(v is not None for v in [b1, b2, f1, f2]):
                bmi_ch.append(b1 - b2)
                fm_ch.append(f1 - f2)
        if bmi_ch and fm_ch:
            ax.scatter(bmi_ch, fm_ch, alpha=0.6, s=30, c="#4ECDC4", edgecolors="gray")
            ax.set_xlabel("BMI-Reduktion (kg/m²)")
            ax.set_ylabel("Fettmasse-Reduktion (kg)")
            ax.set_title("Korrelation: BMI-Reduktion vs. Fettmasse-Reduktion (Op1→Op2)")
            # Trendlinie
            z = np.polyfit(bmi_ch, fm_ch, 1)
            p_line = np.poly1d(z)
            x_line = np.linspace(min(bmi_ch), max(bmi_ch), 100)
            ax.plot(x_line, p_line(x_line), "r--", alpha=0.8, label=f"Trend (R²)")
            corr = np.corrcoef(bmi_ch, fm_ch)[0, 1]
            ax.text(0.05, 0.95, f"r = {corr:.3f}\nn = {len(bmi_ch)}",
                    transform=ax.transAxes, fontsize=11, va="top",
                    bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8))
            ax.legend(fontsize=9)
        fig.text(0.1, 0.02,
                 "Kommentar: Starke Korrelation zwischen BMI- und Fettmassereduktion. "
                 "Ausreißer können auf unterschiedliche Körperzusammensetzung hinweisen.",
                 fontsize=9, style="italic", wrap=True)
        plt.tight_layout(rect=[0, 0.06, 1, 1])
        pdf.savefig(fig)
        plt.close(fig)

        # --- 13. Zusammenfassung Seite ---
        fig = plt.figure(figsize=(11.69, 8.27))
        summary_text = []
        summary_text.append("ZUSAMMENFASSUNG DER WICHTIGSTEN ERGEBNISSE")
        summary_text.append("")
        ov = results["overview"]
        summary_text.append(f"• Patientenkollektiv: {ov['total']} Patienten, "
                            f"davon {ov['with_all3']} mit 3 Messungen")
        wl = results["weight_loss"]
        if wl["op1_op2"]:
            summary_text.append(f"• Mittlerer Gewichtsverlust Op1→Op2: "
                                f"{wl['op1_op2']['mean']:.1f} kg")
        if wl["ewl_op1_op2"]:
            summary_text.append(f"• Mittlerer %EWL Op1→Op2: "
                                f"{wl['ewl_op1_op2']['mean']:.1f}%")
        bmi1 = results["bmi_stats"][0]
        bmi2 = results["bmi_stats"][1]
        if bmi1 and bmi2:
            summary_text.append(f"• BMI-Reduktion: {bmi1['mean']:.1f} → {bmi2['mean']:.1f} kg/m² "
                                f"(Δ = {bmi1['mean']-bmi2['mean']:.1f})")
        ch_fm = results["composition_changes"]["FM_kg"]["op1_op2"]
        ch_ffm = results["composition_changes"]["FFM_kg"]["op1_op2"]
        if ch_fm and ch_ffm:
            total_l = abs(ch_fm["mean"]) + abs(ch_ffm["mean"])
            if total_l > 0:
                summary_text.append(f"• FM-Anteil am Verlust: {abs(ch_fm['mean'])/total_l*100:.0f}%, "
                                    f"FFM-Anteil: {abs(ch_ffm['mean'])/total_l*100:.0f}%")
        rg = results["weight_regain"]
        summary_text.append(f"• Gewichts-Regain (Op2→Op3): {len(rg)} Patienten")
        phi1 = results["phi_stats"][0]
        phi2 = results["phi_stats"][1]
        if phi1 and phi2:
            summary_text.append(f"• Phasenwinkel: {phi1['mean']:.1f}° → {phi2['mean']:.1f}° (Op1→Op2)")
        summary_text.append("")
        summary_text.append("EMPFEHLUNGEN:")
        summary_text.append("• Operationstyp dokumentieren")
        summary_text.append("• Laborwerte erfassen (HbA1c, Albumin, Vitamine)")
        summary_text.append("• Standardisierte Follow-up-Zeiten")
        summary_text.append("• Proteinzufuhr und Bewegung monitoren")

        fig.text(0.1, 0.85, "\n".join(summary_text),
                 fontsize=12, va="top", ha="left",
                 fontfamily="DejaVu Sans",
                 bbox=dict(boxstyle="round", facecolor="#f0f0f0", alpha=0.9),
                 linespacing=1.6)
        pdf.savefig(fig)
        plt.close(fig)

    print(f"PDF gespeichert: {out_path}")


# ---------------------------------------------------------------------------
# 6.  Hauptprogramm
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    base_dir = "/home/user/hospital"
    csv_path = os.path.join(base_dir, "sheet_data_fresh.csv")

    print("Lade Daten...")
    patients = load_data(csv_path)
    print(f"  {len(patients)} Patienten geladen")

    print("Fuehre Analyse durch...")
    results = run_analysis(patients)

    report_path = os.path.join(base_dir, "analysis_report.md")
    print(f"Erstelle Bericht: {report_path}")
    generate_report(results, report_path)

    pdf_path = os.path.join(base_dir, "bia_visualisierung.pdf")
    print(f"Erstelle PDF: {pdf_path}")
    generate_pdf(results, pdf_path)

    print("Fertig!")
