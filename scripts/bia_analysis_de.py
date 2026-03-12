#!/usr/bin/env python3
"""
BIA-Datenanalyse — exakte Reproduktion des russischen PDFs auf Deutsch.
9 Seiten, identisches Layout, alle Beschriftungen auf Deutsch.
"""
import csv, os, sys
from collections import defaultdict
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import matplotlib.colors as mcolors
import numpy as np

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "figure.titlesize": 16,
})

# ── helpers ──────────────────────────────────────────────────────────────
FIELD_NAMES = [
    "Gewicht_kg","Groesse_cm","BMI","FM_kg","FM_pct","FMI",
    "FFM_kg","FFM_pct","FFMI","SMM_kg","R_Ohm","Xc_Ohm",
    "VAT_l","Taillenumfang_cm","phi_deg","Perzentile",
    "TBW_l","TBW_pct","ECW_l","ECW_pct","ECW_TBW_pct"
]

def pf(s):
    if not s or not s.strip() or s.strip()=="-": return None
    try: return float(s.strip().replace(",","."))
    except: return None

def load_data(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    patients = []
    i = 5
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            i += 1; continue
        pid = row[0].strip()
        name = row[1].strip() if len(row)>1 else ""
        dates = [None]*3
        for oi, co in enumerate([2,23,44]):
            if len(row)>co and row[co].strip(): dates[oi]=row[co].strip()
        drow = rows[i+1] if i+1<len(rows) else []
        ops = []
        for oi in range(3):
            cs = 2+oi*21
            vals = {}; has = False
            for fi, fn in enumerate(FIELD_NAMES):
                c = cs+fi
                v = pf(drow[c]) if c<len(drow) else None
                vals[fn]=v
                if v is not None: has=True
            ops.append({"date":dates[oi],"values":vals,"has_data":has})
        patients.append({"id":pid,"name":name,"ops":ops})
        i += 2
    return patients

FEMALE = {"sabrina","claudia","lilia","iris","marion","juliane","ute","anja",
    "aline","jasmin","constanze","simone","gabriele","nadine","veronika","grit",
    "sally","sandra","kathrin","isabell","kerstin","peggy","cornelia","thea",
    "manja","birgit","katrin","dragana","jennifer","carmen","jana","manuela",
    "sylvia","ellen","ramona","ursula","petra","elke","franziska","andrea",
    "lidija","heike","diana","adelheid","susanne","sara","erika","martina",
    "doreen","babette","nancy","susan","anke","heidi","nicole","angelika",
    "mary","madlen","katja","carolin","romy","dara","angela","alexandra",
    "annette","maika","corina","inge","lisa","kristina","ingrid","stine",
    "meike","larissa","margitta","anka","annett","szilvia","katharina","colett",
    "linda","silke","sarah","miroslava","judy","anika","baerbel","linda"}
MALE = {"hendrik","lutz","jochen","mike","frank","ricardo","heiko","ronny",
    "patrick","alexander","andreas","sebastian","olaf","kai","arend","sven",
    "daniel","marc","andy","mirko","pierre","jens","volker","thomas","stefan",
    "rene","reiner","wilfried","gerd","herbert","michael","silvio","enrico",
    "matthias","hans","tony","joerg"}

def gender(p):
    first = p["name"].split()[0].lower() if p["name"] else ""
    if first in FEMALE: return "W"
    if first in MALE: return "M"
    ffmi = p["ops"][0]["values"].get("FFMI")
    if ffmi is not None: return "M" if ffmi>23 else "W"
    return "?"

def vals(patients, oi, field):
    return [p["ops"][oi]["values"][field] for p in patients
            if p["ops"][oi]["values"].get(field) is not None]

# ── colors matching original ─────────────────────────────────────────────
C_OP1 = "#5B9BD5"  # blue
C_OP2 = "#ED7D31"  # orange
C_OP3 = "#70AD47"  # green

# ── main ─────────────────────────────────────────────────────────────────
def generate_pdf(patients, out_path):
    for p in patients:
        p["gender"] = gender(p)

    n_op1 = sum(1 for p in patients if p["ops"][0]["has_data"])
    n_op2 = sum(1 for p in patients if p["ops"][1]["has_data"])
    n_op3 = sum(1 for p in patients if p["ops"][2]["has_data"])
    n_f = sum(1 for p in patients if p["gender"]=="W")
    n_m = sum(1 for p in patients if p["gender"]=="M")

    with PdfPages(out_path) as pdf:

        # ═══════════════ PAGE 1: Übersicht ═══════════════════════════════
        fig = plt.figure(figsize=(13.5, 9.5))
        fig.suptitle("BIA-Datenanalyse: bariatrische Chirurgie", fontsize=18, fontweight="bold", y=0.98)

        # 1a: BMI-Histogramm präoperativ
        ax1 = fig.add_subplot(2,2,1)
        bmi1 = vals(patients,0,"BMI")
        ax1.hist(bmi1, bins=20, color=C_OP1, edgecolor="white")
        ax1.axvline(30, color="orange", ls="--", label="BMI=30")
        ax1.axvline(40, color="red", ls="--", label="BMI=40")
        ax1.set_xlabel("BMI (kg/m²)")
        ax1.set_ylabel("Anzahl Patienten")
        ax1.set_title("BMI-Verteilung präoperativ")
        ax1.legend(fontsize=8)

        # 1b: Geschlechterverteilung
        ax2 = fig.add_subplot(2,2,2)
        ax2.pie([n_f, n_m], labels=[f"Frauen ({n_f})", f"Männer ({n_m})"],
                autopct="%1.0f%%", colors=[C_OP2, C_OP1], startangle=90,
                textprops={"fontsize":11})
        ax2.set_title("Geschlechterverteilung")

        # 1c: Datenverfügbarkeit
        ax3 = fig.add_subplot(2,2,3)
        bars = ax3.bar(["Präoperativ\n(Op1)", "1. Kontrolle\n(Op2)", "2. Kontrolle\n(Op3)"],
                       [n_op1, n_op2, n_op3], color=[C_OP1, C_OP2, C_OP3], edgecolor="white")
        for b, v in zip(bars, [n_op1, n_op2, n_op3]):
            ax3.text(b.get_x()+b.get_width()/2, v+2, str(v), ha="center", fontweight="bold", fontsize=11)
        ax3.set_ylabel("Anzahl Patienten")
        ax3.set_title("Datenverfügbarkeit je Zeitpunkt")

        # 1d: Gewichtsverteilung präoperativ
        ax4 = fig.add_subplot(2,2,4)
        w1 = vals(patients,0,"Gewicht_kg")
        ax4.hist(w1, bins=20, color=C_OP3, edgecolor="white")
        med = np.median(w1)
        ax4.axvline(med, color="red", ls="--", label=f"Median={med:.0f} kg")
        ax4.set_xlabel("Gewicht (kg)")
        ax4.set_ylabel("Anzahl Patienten")
        ax4.set_title("Gewichtsverteilung präoperativ")
        ax4.legend(fontsize=8)

        plt.tight_layout(rect=[0,0,1,0.94])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 2: Gewichts- und BMI-Dynamik ══════════════
        fig = plt.figure(figsize=(13.5, 9.5))
        fig.suptitle("Gewichts- und BMI-Dynamik", fontsize=16, fontweight="bold", y=0.98)

        # 2a: BMI-Boxplots
        ax1 = fig.add_subplot(2,2,1)
        bmi_all = [vals(patients,oi,"BMI") for oi in range(3)]
        bp = ax1.boxplot(bmi_all, tick_labels=[f"Op1\n(n={len(bmi_all[0])})",
                         f"Op2\n(n={len(bmi_all[1])})", f"Op3\n(n={len(bmi_all[2])})"],
                         patch_artist=True, widths=0.5)
        for patch, c in zip(bp["boxes"], [C_OP1, C_OP2, C_OP3]):
            patch.set_facecolor(c); patch.set_alpha(0.7)
        ax1.axhline(30, color="gray", ls=":", alpha=0.5)
        ax1.set_ylabel("BMI (kg/m²)")
        ax1.set_title("BMI-Verteilung je Zeitpunkt")

        # 2b: Gewichts-Boxplots
        ax2 = fig.add_subplot(2,2,2)
        w_all = [vals(patients,oi,"Gewicht_kg") for oi in range(3)]
        bp2 = ax2.boxplot(w_all, tick_labels=[f"Op1\n(n={len(w_all[0])})",
                          f"Op2\n(n={len(w_all[1])})", f"Op3\n(n={len(w_all[2])})"],
                          patch_artist=True, widths=0.5)
        for patch, c in zip(bp2["boxes"], [C_OP1, C_OP2, C_OP3]):
            patch.set_facecolor(c); patch.set_alpha(0.7)
        ax2.set_ylabel("Gewicht (kg)")
        ax2.set_title("Gewichtsverteilung je Zeitpunkt")

        # 2c: Individuelle Gewichtsverläufe
        ax3 = fig.add_subplot(2,2,3)
        for p in patients:
            ws = []
            ok = True
            for oi in range(3):
                v = p["ops"][oi]["values"].get("Gewicht_kg")
                if v is None: ok=False; break
                ws.append(v)
            if ok:
                ax3.plot([0,1,2], ws, "-", color=C_OP1, alpha=0.3, lw=0.7)
        ax3.set_xticks([0,1,2])
        ax3.set_xticklabels(["Op1","Op2","Op3"])
        ax3.set_ylabel("Gewicht (kg)")
        ax3.set_title("Individuelle Gewichtsverläufe")

        # 2d: BMI-Veränderung Op1→Op3
        ax4 = fig.add_subplot(2,2,4)
        bmi_ch = []
        for p in patients:
            b1 = p["ops"][0]["values"].get("BMI")
            b3 = p["ops"][2]["values"].get("BMI")
            if b1 is not None and b3 is not None:
                bmi_ch.append(b3 - b1)
        ax4.hist(bmi_ch, bins=20, color=C_OP1, edgecolor="white")
        mean_ch = np.mean(bmi_ch)
        ax4.axvline(mean_ch, color="orange", ls="--", label=f"Mittelwert={mean_ch:.1f}")
        ax4.axvline(0, color="red", ls="-.", alpha=0.5)
        ax4.set_xlabel("Δ BMI (Op1→Op3)")
        ax4.set_ylabel("Anzahl Patienten")
        ax4.set_title("BMI-Veränderung (Op1→Op3)")
        ax4.legend(fontsize=8)

        plt.tight_layout(rect=[0,0,1,0.94])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 3: Körperzusammensetzung ═══════════════════
        fig = plt.figure(figsize=(13.5, 9.5))
        fig.suptitle("Körperzusammensetzung: Fett- und fettfreie Masse", fontsize=16, fontweight="bold", y=0.98)

        # 3a: FM% Boxplots
        ax1 = fig.add_subplot(2,2,1)
        fm_pct = [vals(patients,oi,"FM_pct") for oi in range(3)]
        bp = ax1.boxplot(fm_pct, tick_labels=[f"Op1\n(n={len(fm_pct[0])})",
                         f"Op2\n(n={len(fm_pct[1])})", f"Op3\n(n={len(fm_pct[2])})"],
                         patch_artist=True, widths=0.5)
        for patch, c in zip(bp["boxes"], [C_OP1, C_OP2, C_OP3]):
            patch.set_facecolor(c); patch.set_alpha(0.7)
        ax1.set_ylabel("Fettmasse (%)")
        ax1.set_title("Fettmasseanteil je Zeitpunkt")

        # 3b: FFM% Boxplots
        ax2 = fig.add_subplot(2,2,2)
        ffm_pct = [vals(patients,oi,"FFM_pct") for oi in range(3)]
        bp2 = ax2.boxplot(ffm_pct, tick_labels=[f"Op1\n(n={len(ffm_pct[0])})",
                          f"Op2\n(n={len(ffm_pct[1])})", f"Op3\n(n={len(ffm_pct[2])})"],
                          patch_artist=True, widths=0.5)
        for patch, c in zip(bp2["boxes"], [C_OP1, C_OP2, C_OP3]):
            patch.set_facecolor(c); patch.set_alpha(0.7)
        ax2.set_ylabel("Fettfreie Masse (%)")
        ax2.set_title("Fettfreie Masse je Zeitpunkt")

        # 3c: SMM-Verläufe (Geschlecht farblich)
        ax3 = fig.add_subplot(2,2,3)
        for p in patients:
            smms = []
            ok = True
            for oi in range(3):
                v = p["ops"][oi]["values"].get("SMM_kg")
                if v is None: ok=False; break
                smms.append(v)
            if ok:
                col = C_OP2 if p["gender"]=="W" else C_OP1
                ax3.plot([0,1,2], smms, "-", color=col, alpha=0.3, lw=0.7)
        ax3.set_xticks([0,1,2])
        ax3.set_xticklabels(["Op1","Op2","Op3"])
        ax3.set_ylabel("Skelettmuskelmasse (kg)")
        ax3.set_title("Skelettmuskelmasse-Dynamik\n(orange=Frauen, blau=Männer)")

        # 3d: FM-Verlust vs FFM-Verlust (Scatter)
        ax4 = fig.add_subplot(2,2,4)
        for p in patients:
            fm1 = p["ops"][0]["values"].get("FM_kg")
            fm2 = p["ops"][1]["values"].get("FM_kg")
            ffm1 = p["ops"][0]["values"].get("FFM_kg")
            ffm2 = p["ops"][1]["values"].get("FFM_kg")
            if all(v is not None for v in [fm1,fm2,ffm1,ffm2]):
                col = C_OP2 if p["gender"]=="W" else C_OP1
                mk = "o" if p["gender"]=="W" else "s"
                ax4.scatter(fm2-fm1, ffm2-ffm1, c=col, marker=mk, alpha=0.5, s=25, edgecolors="none")
        ax4.axhline(0, color="gray", ls=":", alpha=0.5)
        ax4.axvline(0, color="gray", ls=":", alpha=0.5)
        ax4.set_xlabel("Δ Fettmasse (kg)")
        ax4.set_ylabel("Δ Fettfreie Masse (kg)")
        ax4.set_title("FM- vs FFM-Verlust (Op1→Op2)")
        ax4.legend([Line2D([0],[0],marker="o",color=C_OP2,ls="",ms=6),
                    Line2D([0],[0],marker="s",color=C_OP1,ls="",ms=6)],
                   ["Frauen","Männer"], fontsize=8)

        plt.tight_layout(rect=[0,0,1,0.94])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 4: Metabolische Indikatoren ════════════════
        fig = plt.figure(figsize=(13.5, 9.5))
        fig.suptitle("Metabolische und funktionelle Indikatoren", fontsize=16, fontweight="bold", y=0.98)

        def boxplot_3(ax, field, ylabel, title, threshold=None, thr_label=None):
            data = [vals(patients,oi,field) for oi in range(3)]
            bp = ax.boxplot(data, tick_labels=[f"Op1\n(n={len(data[0])})",
                            f"Op2\n(n={len(data[1])})", f"Op3\n(n={len(data[2])})"],
                            patch_artist=True, widths=0.5)
            for patch, c in zip(bp["boxes"], [C_OP1, C_OP2, C_OP3]):
                patch.set_facecolor(c); patch.set_alpha(0.7)
            ax.set_ylabel(ylabel)
            ax.set_title(title)
            if threshold is not None:
                ax.axhline(threshold, color="red", ls="--", alpha=0.6, label=thr_label)
                ax.legend(fontsize=7)

        ax1 = fig.add_subplot(2,2,1)
        boxplot_3(ax1, "VAT_l", "VAT (l)", "Viszerales Fett je Zeitpunkt", 4, "Risikoschwelle (4 l)")
        ax2 = fig.add_subplot(2,2,2)
        boxplot_3(ax2, "phi_deg", "Phasenwinkel (°)", "Phasenwinkel je Zeitpunkt", 4, "Schwellenwert")
        ax3 = fig.add_subplot(2,2,3)
        boxplot_3(ax3, "ECW_TBW_pct", "ECW/TBW (%)", "Wasserhaushalt je Zeitpunkt", 50, "Ödemschwelle (50%)")
        ax4 = fig.add_subplot(2,2,4)
        boxplot_3(ax4, "Taillenumfang_cm", "Taillenumfang (cm)", "Taillenumfang je Zeitpunkt")

        plt.tight_layout(rect=[0,0,1,0.94])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 5: Korrelationsanalyse ═════════════════════
        fig = plt.figure(figsize=(13.5, 9.5))
        fig.suptitle("Korrelationsanalyse und Prädiktoren", fontsize=16, fontweight="bold", y=0.98)

        # 5a: Ausgangs-BMI vs Gewichtsverlust % (Op1→Op3)
        ax1 = fig.add_subplot(2,2,1)
        for p in patients:
            b1 = p["ops"][0]["values"].get("BMI")
            w1 = p["ops"][0]["values"].get("Gewicht_kg")
            w3 = p["ops"][2]["values"].get("Gewicht_kg")
            if all(v is not None for v in [b1,w1,w3]) and w1>0:
                pct = (w3-w1)/w1*100
                col = C_OP2 if p["gender"]=="W" else C_OP1
                mk = "o" if p["gender"]=="W" else "s"
                ax1.scatter(b1, pct, c=col, marker=mk, alpha=0.5, s=25, edgecolors="none")
        ax1.set_xlabel("Ausgangs-BMI (kg/m²)")
        ax1.set_ylabel("Gewichtsverlust (%)")
        ax1.set_title("Ausgangs-BMI vs Gewichtsverlust (Op1→Op3)")
        ax1.legend([Line2D([0],[0],marker="o",color=C_OP2,ls="",ms=6),
                    Line2D([0],[0],marker="s",color=C_OP1,ls="",ms=6)],
                   ["Frauen","Männer"], fontsize=8)

        # 5b: Ausgangs-VAT vs VAT-Reduktion
        ax2 = fig.add_subplot(2,2,2)
        vat_x, vat_y = [], []
        for p in patients:
            v1 = p["ops"][0]["values"].get("VAT_l")
            v3 = p["ops"][2]["values"].get("VAT_l")
            if v1 is not None and v3 is not None:
                vat_x.append(v1); vat_y.append(v3-v1)
        ax2.scatter(vat_x, vat_y, c=C_OP3, alpha=0.5, s=25, edgecolors="none")
        ax2.axhline(0, color="gray", ls=":", alpha=0.5)
        if vat_x:
            corr = np.corrcoef(vat_x, vat_y)[0,1]
            ax2.text(0.05,0.95, f"r = {corr:.2f}", transform=ax2.transAxes, fontsize=10,
                     va="top", bbox=dict(boxstyle="round",facecolor="lightyellow",alpha=0.8))
        ax2.set_xlabel("Ausgangs-VAT (l)")
        ax2.set_ylabel("Δ VAT (l)")
        ax2.set_title("Ausgangs-VAT vs VAT-Reduktion (Op1→Op3)")

        # 5c: Gewichtsverlust vs Muskelverlust
        ax3 = fig.add_subplot(2,2,3)
        dw_list, ds_list = [], []
        for p in patients:
            w1 = p["ops"][0]["values"].get("Gewicht_kg")
            w3 = p["ops"][2]["values"].get("Gewicht_kg")
            s1 = p["ops"][0]["values"].get("SMM_kg")
            s3 = p["ops"][2]["values"].get("SMM_kg")
            if all(v is not None for v in [w1,w3,s1,s3]):
                dw_list.append(w3-w1); ds_list.append(s3-s1)
        ax3.scatter(dw_list, ds_list, c=C_OP1, alpha=0.5, s=25, edgecolors="none")
        ax3.axhline(0, color="gray", ls=":", alpha=0.5)
        ax3.axvline(0, color="gray", ls=":", alpha=0.5)
        if dw_list:
            corr = np.corrcoef(dw_list, ds_list)[0,1]
            ax3.text(0.05,0.95, f"r = {corr:.2f}", transform=ax3.transAxes, fontsize=10,
                     va="top", bbox=dict(boxstyle="round",facecolor="lightyellow",alpha=0.8))
        ax3.set_xlabel("Δ Gewicht (kg)")
        ax3.set_ylabel("Δ Skelettmuskelmasse (kg)")
        ax3.set_title("Gewichtsverlust vs Muskelverlust (Op1→Op3)")

        # 5d: BMI vs Phasenwinkel (Op1)
        ax4 = fig.add_subplot(2,2,4)
        for p in patients:
            b = p["ops"][0]["values"].get("BMI")
            ph = p["ops"][0]["values"].get("phi_deg")
            if b is not None and ph is not None:
                col = C_OP2 if p["gender"]=="W" else C_OP1
                mk = "o" if p["gender"]=="W" else "s"
                ax4.scatter(b, ph, c=col, marker=mk, alpha=0.5, s=25, edgecolors="none")
        ax4.set_xlabel("BMI (kg/m²)")
        ax4.set_ylabel("Phasenwinkel (°)")
        ax4.set_title("BMI vs Phasenwinkel (Op1)")
        ax4.legend([Line2D([0],[0],marker="o",color=C_OP2,ls="",ms=6),
                    Line2D([0],[0],marker="s",color=C_OP1,ls="",ms=6)],
                   ["Frauen","Männer"], fontsize=8)

        plt.tight_layout(rect=[0,0,1,0.94])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 6: Mittelwerte je Zeitpunkt ════════════════
        fig = plt.figure(figsize=(13.5, 9.5))
        fig.suptitle("Kennzahlen je Zeitpunkt (Mittelwerte)", fontsize=16, fontweight="bold", y=0.98)

        def mean_safe(lst):
            return np.mean(lst) if lst else 0

        # 6a: BMI, FMI, FFMI — grouped by Op
        ax1 = fig.add_subplot(2,2,1)
        fields_idx = ["BMI","FMI","FFMI"]
        x = np.arange(len(fields_idx))
        w = 0.25
        for oi, (label, col) in enumerate([("Op1",C_OP1),("Op2",C_OP2),("Op3",C_OP3)]):
            means = [mean_safe(vals(patients,oi,f)) for f in fields_idx]
            ax1.bar(x+oi*w, means, w, label=label, color=col, edgecolor="white")
        ax1.set_xticks(x+w)
        ax1.set_xticklabels(fields_idx)
        ax1.set_ylabel("kg/m²")
        ax1.set_title("Körpermasseindizes je Zeitpunkt")
        ax1.legend(fontsize=8)

        # 6b: FM% vs FFM%
        ax2 = fig.add_subplot(2,2,2)
        fields2 = [("FM_pct","Fettmasse %"),("FFM_pct","Fettfr. Masse %")]
        x2 = np.arange(len(fields2))
        for oi, (label, col) in enumerate([("Op1",C_OP1),("Op2",C_OP2),("Op3",C_OP3)]):
            means = [mean_safe(vals(patients,oi,f)) for f,_ in fields2]
            ax2.bar(x2+oi*w, means, w, label=label, color=col, edgecolor="white")
        ax2.set_xticks(x2+w)
        ax2.set_xticklabels([l for _,l in fields2])
        ax2.set_ylabel("%")
        ax2.set_title("Fett- und fettfreie Masse im Verhältnis")
        ax2.legend(fontsize=8)

        # 6c: Wasserhaushalt
        ax3 = fig.add_subplot(2,2,3)
        fields3 = [("TBW_pct","TBW %"),("ECW_pct","ECW %"),("ECW_TBW_pct","ECW/TBW %")]
        x3 = np.arange(len(fields3))
        for oi, (label, col) in enumerate([("Op1",C_OP1),("Op2",C_OP2),("Op3",C_OP3)]):
            means = [mean_safe(vals(patients,oi,f)) for f,_ in fields3]
            ax3.bar(x3+oi*w, means, w, label=label, color=col, edgecolor="white")
        ax3.set_xticks(x3+w)
        ax3.set_xticklabels([l for _,l in fields3])
        ax3.set_ylabel("%")
        ax3.set_title("Wasserhaushalt je Zeitpunkt")
        ax3.legend(fontsize=8)

        # 6d: Viszerales Fett
        ax4 = fig.add_subplot(2,2,4)
        vat_means = [mean_safe(vals(patients,oi,"VAT_l")) for oi in range(3)]
        ax4.bar(["Op1","Op2","Op3"], vat_means, color=[C_OP1,C_OP2,C_OP3], edgecolor="white")
        ax4.set_ylabel("Viszerales Fett (l)")
        ax4.set_title("Viszerales Fett je Zeitpunkt")

        plt.tight_layout(rect=[0,0,1,0.94])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 7: BMI-Klassifikation ══════════════════════
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.5))
        fig.suptitle("BMI-Klassifikation: präoperativ vs letzte Kontrolle", fontsize=16, fontweight="bold", y=0.98)

        bmi_cats = [("<30","Norm.\n<30"), ("30-35","Adip. I\n30-35"), ("35-40","Adip. II\n35-40"),
                    ("40-50","Adip. III\n40-50"), ("50-60","Extrem\n50-60"), ("≥60","Super\n≥60")]
        cat_colors = ["#2ca02c","#FFDD44","#FFA500","#FF4444","#CC0000","#880000"]

        def classify_bmi_detailed(bmi):
            if bmi<30: return 0
            elif bmi<35: return 1
            elif bmi<40: return 2
            elif bmi<50: return 3
            elif bmi<60: return 4
            else: return 5

        for ax, oi, title in [(ax1,0,f"Präoperativ (Op1) (n={len(bmi_all[0])})"),
                               (ax2,2,f"Letzte Kontrolle (Op3) (n={len(bmi_all[2])})")]:
            data = vals(patients,oi,"BMI")
            counts = [0]*6
            for b in data:
                counts[classify_bmi_detailed(b)] += 1
            bars = ax.bar([l for _,l in bmi_cats], counts, color=cat_colors, edgecolor="white")
            for b, v in zip(bars, counts):
                if v>0:
                    ax.text(b.get_x()+b.get_width()/2, v+0.5, str(v), ha="center", fontweight="bold", fontsize=10)
            ax.set_ylabel("Anzahl Patienten")
            ax.set_title(title)

        plt.tight_layout(rect=[0,0,1,0.92])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 8: Heatmap ═════════════════════════════════
        fig, ax = plt.subplots(1, 1, figsize=(13.5, 7))
        fig.suptitle("Mittlere Veränderungen der Schlüsselparameter je Zeitraum",
                     fontsize=16, fontweight="bold", y=0.98)

        hm_fields = [
            ("Gewicht_kg","Gewicht"),("BMI","BMI"),("FM_kg","FM (kg)"),("FM_pct","FM (%)"),
            ("FFM_kg","FFM (kg)"),("SMM_kg","Muskeln"),("VAT_l","Visz. Fett"),
            ("Taillenumfang_cm","Taillenumf."),("phi_deg","Phasenw."),
            ("TBW_pct","TBW %"),("ECW_TBW_pct","ECW/TBW %")
        ]
        periods = ["Op1→Op2","Op2→Op3","Op1→Op3"]
        hm_data = np.zeros((3, len(hm_fields)))

        for fi, (field, _) in enumerate(hm_fields):
            for pi, (oi_from, oi_to) in enumerate([(0,1),(1,2),(0,2)]):
                changes = []
                baselines = []
                for p in patients:
                    v_from = p["ops"][oi_from]["values"].get(field)
                    v_to = p["ops"][oi_to]["values"].get(field)
                    if v_from is not None and v_to is not None and v_from != 0:
                        changes.append((v_to - v_from)/abs(v_from)*100)
                if changes:
                    hm_data[pi, fi] = np.mean(changes)

        cmap = plt.cm.RdYlGn_r
        norm = mcolors.TwoSlopeNorm(vmin=-40, vcenter=0, vmax=40)
        im = ax.imshow(hm_data, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(len(hm_fields)))
        ax.set_xticklabels([l for _,l in hm_fields], rotation=45, ha="right", fontsize=9)
        ax.set_yticks(range(3))
        ax.set_yticklabels(periods, fontsize=11)
        ax.set_title("Heatmap der Veränderungen (% vom Ausgangswert)", fontsize=12)

        for i in range(3):
            for j in range(len(hm_fields)):
                v = hm_data[i,j]
                color = "white" if abs(v)>25 else "black"
                ax.text(j, i, f"{v:.1f}%", ha="center", va="center", fontsize=9, color=color)

        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Veränderung (%)", fontsize=10)

        plt.tight_layout(rect=[0,0,1,0.93])
        pdf.savefig(fig); plt.close(fig)

        # ═══════════════ PAGE 9: Top/Flop ════════════════════════════════
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.5))
        fig.suptitle("Beste und schlechteste Ergebnisse (Op1→Op3)", fontsize=16, fontweight="bold", y=0.98)

        # Collect Op1→Op3 weight change %
        wc_list = []
        for p in patients:
            w1 = p["ops"][0]["values"].get("Gewicht_kg")
            w3 = p["ops"][2]["values"].get("Gewicht_kg")
            if w1 is not None and w3 is not None and w1>0:
                pct = (w3-w1)/w1*100
                nm = p["name"].split()[-1] if p["name"] else p["id"]
                wc_list.append((nm, pct))

        wc_list.sort(key=lambda x: x[1])
        top10 = wc_list[:10]  # most loss (most negative)
        bot10 = wc_list[-10:]  # least loss / regain

        # Top 10
        names_t = [x[0] for x in top10][::-1]
        vals_t = [x[1] for x in top10][::-1]
        ax1.barh(names_t, vals_t, color="#70AD47", edgecolor="white")
        ax1.set_xlabel("Gewichtsverlust (%)")
        ax1.set_title("Top 10: größter Gewichtsverlust")

        # Bottom 10
        names_b = [x[0] for x in bot10][::-1]
        vals_b = [x[1] for x in bot10][::-1]
        colors_b = ["#FF4444" if v>0 else "#FFAA00" for v in vals_b]
        ax2.barh(names_b, vals_b, color=colors_b, edgecolor="white")
        ax2.axvline(0, color="black", ls="--", alpha=0.5)
        ax2.set_xlabel("Gewichtsveränderung (%)")
        ax2.set_title("Top 10: geringster Gewichtsverlust")

        plt.tight_layout(rect=[0,0,1,0.92])
        pdf.savefig(fig); plt.close(fig)

    print(f"PDF gespeichert: {out_path}")


# ── run ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    patients = load_data("/home/user/hospital/sheet_data_fresh.csv")
    print(f"{len(patients)} Patienten geladen")
    generate_pdf(patients, "/home/user/hospital/bia_analysis_visualizations.pdf")
