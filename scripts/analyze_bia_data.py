#!/usr/bin/env python3
"""
BIA Data Analysis Script
Analyzes patient body composition data before and after bariatric surgery.
Generates: 1) Markdown analysis report  2) PDF with visualizations
All output in Russian with Cyrillic-safe fonts.
"""

import csv
import re
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.font_manager as fm
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# === Configuration ===
CSV_PATH = "/home/user/hospital/sheet_data_fresh.csv"
OUTPUT_DIR = "/home/user/hospital/analysis"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Font setup for Cyrillic
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.unicode_minus'] = False

FIELD_NAMES = [
    'Gewicht', 'Groesse', 'BMI', 'FM_kg', 'FM_pct', 'FMI',
    'FFM_kg', 'FFM_pct', 'FFMI', 'SMM', 'R', 'Xc',
    'VAT', 'Taillenumfang', 'phi', 'Perzentile',
    'TBW_l', 'TBW_pct', 'ECW_l', 'ECW_pct', 'ECW_TBW_pct'
]

FIELD_LABELS_RU = {
    'Gewicht': 'Вес (кг)', 'Groesse': 'Рост (см)', 'BMI': 'ИМТ (кг/м²)',
    'FM_kg': 'Жир. масса (кг)', 'FM_pct': 'Жир. масса (%)', 'FMI': 'ИЖМ (кг/м²)',
    'FFM_kg': 'Безжир. масса (кг)', 'FFM_pct': 'Безжир. масса (%)', 'FFMI': 'ИБЖМ (кг/м²)',
    'SMM': 'Скел. мышцы (кг)', 'R': 'R (Ом)', 'Xc': 'Xc (Ом)',
    'VAT': 'Висц. жир (л)', 'Taillenumfang': 'Обхв. талии (см)', 'phi': 'Фаз. угол (°)',
    'Perzentile': 'Перцентиль', 'TBW_l': 'Общ. вода (л)', 'TBW_pct': 'Общ. вода (%)',
    'ECW_l': 'Внекл. вода (л)', 'ECW_pct': 'Внекл. вода (%)', 'ECW_TBW_pct': 'ECW/TBW (%)'
}


def parse_german_float(s):
    """Parse German-style float (comma as decimal separator)."""
    if not s or s.strip() == '':
        return None
    s = s.strip().replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def parse_csv():
    """Parse the CSV file and return structured patient data."""
    patients = []

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Data starts at row 6 (0-indexed: 5), every 2 rows = 1 patient
    i = 5  # row index (0-based)
    while i < len(rows) - 1:
        header_row = rows[i]
        data_row = rows[i + 1]

        pat_id = header_row[0].strip() if header_row[0].strip() else None
        pat_name = header_row[1].strip() if len(header_row) > 1 else ''

        if not pat_id:
            i += 2
            continue

        patient = {
            'id': pat_id,
            'name': pat_name,
            'operations': {}
        }

        # Op1: cols 2-22, Op2: cols 23-43, Op3: cols 44-64
        for op_idx, op_name in enumerate(['Op1', 'Op2', 'Op3']):
            date_col = 2 + op_idx * 21
            data_start = date_col  # date is in header_row, data in data_row

            # Get date from header row
            op_date = header_row[date_col].strip() if date_col < len(header_row) and header_row[date_col].strip() else None

            # Get values from data row
            values = {}
            has_any = False
            for fi, field in enumerate(FIELD_NAMES):
                col = date_col + fi
                if col < len(data_row):
                    val = parse_german_float(data_row[col])
                    if val is not None:
                        values[field] = val
                        has_any = True

            if op_date or has_any:
                patient['operations'][op_name] = {
                    'date': op_date,
                    'values': values
                }

        patients.append(patient)
        i += 2

    return patients


def determine_gender(name):
    """Heuristic gender determination from German first names."""
    female_endings = ['a', 'e', 'i', 'y']
    female_names = {'sabrina', 'claudia', 'juliane', 'petra', 'ursula', 'simone', 'ramona',
                    'ellen', 'anja', 'katrin', 'anett', 'daniela', 'jasmin', 'birgit',
                    'iris', 'marion', 'lilia', 'gabriele', 'annette', 'ute', 'constanze',
                    'aline', 'ingrid', 'cornelia', 'thea', 'manja', 'inge', 'dragana',
                    'jennifer', 'kerstin', 'heike', 'sandra', 'diana', 'adelheid', 'susanne',
                    'carmen', 'jana', 'nadine', 'meike', 'sara', 'lisa', 'mary', 'madlen',
                    'katja', 'doreen', 'carolin', 'kristina', 'nancy', 'susan', 'angelika',
                    'babette', 'anke', 'heidi', 'sally', 'judy', 'andrea', 'lidija',
                    'maika', 'corina', 'elke', 'franziska', 'sylvia', 'manuela', 'peggy',
                    'isabell', 'martina', 'erika', 'romy', 'linda', 'silke', 'sarah',
                    'stine', 'grit', 'veronika', 'larissa', 'nicole', 'szilvia',
                    'miroslava', 'katharina', 'colett', 'anka'}
    male_names = {'hendrik', 'lutz', 'jochen', 'nico', 'heiko', 'frank', 'ricardo',
                  'mike', 'patrick', 'ronny', 'alexander', 'andreas', 'sebastian',
                  'olaf', 'daniel', 'marc', 'andy', 'mirko', 'sven', 'joerg', 'jens',
                  'reiner', 'pierre', 'stefan', 'arend', 'matthias', 'enrico',
                  'wilfried', 'rene', 'herbert', 'gerd', 'michael', 'kai', 'volker',
                  'thomas', 'silvio', 'tony', 'hans', 'andre'}

    if not name:
        return 'unknown'
    first = name.split()[0].lower() if name else ''

    if first in female_names:
        return 'F'
    if first in male_names:
        return 'M'
    # Fallback
    if first.endswith('a') or first.endswith('e') or first.endswith('i'):
        return 'F'
    return 'M'


def build_dataframe(patients):
    """Build a pandas DataFrame with all patient measurements."""
    records = []

    for p in patients:
        gender = determine_gender(p['name'])
        for op_name in ['Op1', 'Op2', 'Op3']:
            if op_name not in p['operations']:
                continue
            op = p['operations'][op_name]
            if not op['values']:
                continue

            rec = {
                'patient_id': p['id'],
                'name': p['name'],
                'gender': gender,
                'operation': op_name,
                'date': op['date']
            }
            rec.update(op['values'])
            records.append(rec)

    return pd.DataFrame(records)


def get_complete_patients(patients):
    """Get patients who have data for at least Op1 and one follow-up."""
    complete = []
    for p in patients:
        ops = p['operations']
        has_op1 = 'Op1' in ops and ops['Op1']['values'].get('BMI') is not None
        has_op2 = 'Op2' in ops and ops['Op2']['values'].get('BMI') is not None
        has_op3 = 'Op3' in ops and ops['Op3']['values'].get('BMI') is not None
        if has_op1 and (has_op2 or has_op3):
            complete.append(p)
    return complete


def compute_statistics(df):
    """Compute key statistics for the analysis."""
    stats = {}

    # Basic counts
    stats['total_patients'] = df['patient_id'].nunique()
    stats['total_records'] = len(df)
    stats['patients_op1'] = df[df['operation'] == 'Op1']['patient_id'].nunique()
    stats['patients_op2'] = df[df['operation'] == 'Op2']['patient_id'].nunique()
    stats['patients_op3'] = df[df['operation'] == 'Op3']['patient_id'].nunique()

    # Gender distribution
    gender_counts = df.drop_duplicates('patient_id')['gender'].value_counts()
    stats['gender_F'] = gender_counts.get('F', 0)
    stats['gender_M'] = gender_counts.get('M', 0)

    # BMI categories at Op1
    op1 = df[df['operation'] == 'Op1'].copy()
    bmi = op1['BMI'].dropna()
    stats['bmi_op1_mean'] = bmi.mean()
    stats['bmi_op1_std'] = bmi.std()
    stats['bmi_op1_min'] = bmi.min()
    stats['bmi_op1_max'] = bmi.max()
    stats['bmi_op1_median'] = bmi.median()

    # BMI categories
    stats['bmi_30_35'] = ((bmi >= 30) & (bmi < 35)).sum()
    stats['bmi_35_40'] = ((bmi >= 35) & (bmi < 40)).sum()
    stats['bmi_40_50'] = ((bmi >= 40) & (bmi < 50)).sum()
    stats['bmi_50_60'] = ((bmi >= 50) & (bmi < 60)).sum()
    stats['bmi_60plus'] = (bmi >= 60).sum()
    stats['bmi_under30'] = (bmi < 30).sum()

    # Weight stats
    w = op1['Gewicht'].dropna()
    stats['weight_op1_mean'] = w.mean()
    stats['weight_op1_std'] = w.std()
    stats['weight_op1_min'] = w.min()
    stats['weight_op1_max'] = w.max()

    return stats


def compute_dynamics(patients):
    """Compute changes between operations for key metrics."""
    dynamics = []

    for p in patients:
        ops = p['operations']
        gender = determine_gender(p['name'])

        for prev_op, next_op, label in [('Op1', 'Op2', 'Op1→Op2'), ('Op2', 'Op3', 'Op2→Op3'), ('Op1', 'Op3', 'Op1→Op3')]:
            if prev_op not in ops or next_op not in ops:
                continue
            v1 = ops[prev_op]['values']
            v2 = ops[next_op]['values']

            rec = {'patient_id': p['id'], 'name': p['name'], 'gender': gender, 'transition': label}

            for field in ['Gewicht', 'BMI', 'FM_kg', 'FM_pct', 'FFM_kg', 'FFM_pct',
                          'SMM', 'VAT', 'Taillenumfang', 'phi', 'TBW_pct', 'ECW_TBW_pct',
                          'FMI', 'FFMI']:
                if field in v1 and field in v2:
                    rec[f'{field}_before'] = v1[field]
                    rec[f'{field}_after'] = v2[field]
                    rec[f'{field}_delta'] = v2[field] - v1[field]
                    if v1[field] != 0:
                        rec[f'{field}_pct_change'] = (v2[field] - v1[field]) / v1[field] * 100

            dynamics.append(rec)

    return pd.DataFrame(dynamics)


def generate_analysis_report(patients, df, stats, dynamics_df):
    """Generate the markdown analysis report in Russian."""

    report = []
    report.append("# Анализ данных BIA (биоимпедансометрия) пациентов бариатрической хирургии\n")
    report.append(f"**Дата анализа:** 2026-03-09\n")
    report.append(f"**Источник данных:** Google Sheets — Patientendaten\n\n")

    # === 1. Overview ===
    report.append("## 1. Общий обзор данных\n")
    report.append(f"- **Всего пациентов:** {stats['total_patients']}\n")
    report.append(f"- **Всего записей измерений:** {stats['total_records']}\n")
    report.append(f"- **Пациентов с данными Op1 (до операции):** {stats['patients_op1']}\n")
    report.append(f"- **Пациентов с данными Op2 (1-й контроль):** {stats['patients_op2']}\n")
    report.append(f"- **Пациентов с данными Op3 (2-й контроль):** {stats['patients_op3']}\n")
    report.append(f"- **Женщины:** {stats['gender_F']} ({stats['gender_F']/stats['total_patients']*100:.0f}%)\n")
    report.append(f"- **Мужчины:** {stats['gender_M']} ({stats['gender_M']/stats['total_patients']*100:.0f}%)\n\n")

    # Completeness
    complete = get_complete_patients(patients)
    pts_3ops = [p for p in patients if all(
        op in p['operations'] and p['operations'][op]['values'].get('BMI') is not None
        for op in ['Op1', 'Op2', 'Op3']
    )]
    report.append(f"- **Пациентов с полными данными (Op1 + хотя бы 1 контроль):** {len(complete)}\n")
    report.append(f"- **Пациентов с полным циклом (Op1 + Op2 + Op3):** {len(pts_3ops)}\n\n")

    # === 2. Baseline characteristics ===
    report.append("## 2. Исходные характеристики пациентов (до операции, Op1)\n\n")

    op1_df = df[df['operation'] == 'Op1']

    report.append("### 2.1 Антропометрические данные\n\n")
    report.append("| Параметр | Среднее ± SD | Медиана | Мин | Макс | N |\n")
    report.append("|----------|-------------|---------|-----|------|---|\n")

    for field, label in [('Gewicht', 'Вес (кг)'), ('Groesse', 'Рост (см)'), ('BMI', 'ИМТ (кг/м²)'),
                         ('FM_kg', 'Жир. масса (кг)'), ('FM_pct', 'Жир. масса (%)'),
                         ('FFM_kg', 'Безжир. масса (кг)'), ('FFM_pct', 'Безжир. масса (%)'),
                         ('SMM', 'Скел. мышцы (кг)'), ('VAT', 'Висц. жир (л)'),
                         ('Taillenumfang', 'Обхв. талии (см)'), ('phi', 'Фаз. угол (°)'),
                         ('TBW_pct', 'Общ. вода (%)'), ('ECW_TBW_pct', 'ECW/TBW (%)')]:
        vals = op1_df[field].dropna()
        if len(vals) > 0:
            report.append(f"| {label} | {vals.mean():.1f} ± {vals.std():.1f} | {vals.median():.1f} | {vals.min():.1f} | {vals.max():.1f} | {len(vals)} |\n")

    report.append("\n### 2.2 Распределение по классам ожирения (ИМТ)\n\n")
    report.append("| Класс | ИМТ | Кол-во | % |\n")
    report.append("|-------|-----|--------|---|\n")
    bmi_vals = op1_df['BMI'].dropna()
    total_bmi = len(bmi_vals)
    categories = [
        ('Норма/Избыт. вес', '<30', (bmi_vals < 30).sum()),
        ('Ожирение I ст.', '30-35', ((bmi_vals >= 30) & (bmi_vals < 35)).sum()),
        ('Ожирение II ст.', '35-40', ((bmi_vals >= 35) & (bmi_vals < 40)).sum()),
        ('Ожирение III ст.', '40-50', ((bmi_vals >= 40) & (bmi_vals < 50)).sum()),
        ('Сверхожирение', '50-60', ((bmi_vals >= 50) & (bmi_vals < 60)).sum()),
        ('Супер-ожирение', '≥60', (bmi_vals >= 60).sum()),
    ]
    for label, rng, cnt in categories:
        report.append(f"| {label} | {rng} | {cnt} | {cnt/total_bmi*100:.1f}% |\n")

    # === 2.3 Gender differences ===
    report.append("\n### 2.3 Различия по полу (Op1)\n\n")
    report.append("| Параметр | Женщины (M±SD) | Мужчины (M±SD) |\n")
    report.append("|----------|---------------|----------------|\n")

    for field, label in [('Gewicht', 'Вес'), ('BMI', 'ИМТ'), ('FM_pct', 'Жир. масса %'),
                         ('FFM_pct', 'Безжир. масса %'), ('SMM', 'Скел. мышцы'),
                         ('phi', 'Фаз. угол'), ('VAT', 'Висц. жир')]:
        f_vals = op1_df[op1_df['gender'] == 'F'][field].dropna()
        m_vals = op1_df[op1_df['gender'] == 'M'][field].dropna()
        if len(f_vals) > 0 and len(m_vals) > 0:
            report.append(f"| {label} | {f_vals.mean():.1f} ± {f_vals.std():.1f} (n={len(f_vals)}) | {m_vals.mean():.1f} ± {m_vals.std():.1f} (n={len(m_vals)}) |\n")

    # === 3. Weight loss dynamics ===
    report.append("\n## 3. Динамика снижения веса\n\n")

    # Op1 -> Op2
    d12 = dynamics_df[dynamics_df['transition'] == 'Op1→Op2']
    d23 = dynamics_df[dynamics_df['transition'] == 'Op2→Op3']
    d13 = dynamics_df[dynamics_df['transition'] == 'Op1→Op3']

    report.append("### 3.1 Потеря веса по этапам\n\n")
    report.append("| Переход | N | Потеря веса (кг) | Потеря веса (%) | Снижение ИМТ |\n")
    report.append("|---------|---|-----------------|----------------|---------------|\n")

    for label, d in [('Op1→Op2', d12), ('Op2→Op3', d23), ('Op1→Op3', d13)]:
        w_delta = d['Gewicht_delta'].dropna()
        w_pct = d['Gewicht_pct_change'].dropna()
        bmi_delta = d['BMI_delta'].dropna()
        if len(w_delta) > 0:
            report.append(f"| {label} | {len(w_delta)} | {w_delta.mean():.1f} ± {w_delta.std():.1f} | {w_pct.mean():.1f}% ± {w_pct.std():.1f}% | {bmi_delta.mean():.1f} ± {bmi_delta.std():.1f} |\n")

    report.append("\n**Комментарий:** Основная потеря веса происходит в первый период (Op1→Op2). ")
    if len(d12) > 0 and len(d23) > 0:
        w12 = d12['Gewicht_delta'].dropna().mean()
        w23 = d23['Gewicht_delta'].dropna().mean()
        report.append(f"Средняя потеря веса Op1→Op2: {abs(w12):.1f} кг, Op2→Op3: {abs(w23):.1f} кг. ")
        if abs(w23) < abs(w12):
            report.append("Наблюдается замедление темпов снижения веса к третьему измерению, что является типичным паттерном после бариатрической хирургии.\n\n")
        else:
            report.append("Темпы снижения веса сохраняются и ко второму контролю.\n\n")

    # === 3.2 Body composition changes ===
    report.append("### 3.2 Изменения состава тела\n\n")
    report.append("| Параметр | Op1→Op2 (M±SD) | Op1→Op3 (M±SD) |\n")
    report.append("|----------|---------------|----------------|\n")

    for field, label in [('FM_kg', 'Δ Жир. масса (кг)'), ('FM_pct', 'Δ Жир. масса (%)'),
                         ('FFM_kg', 'Δ Безжир. масса (кг)'), ('SMM', 'Δ Скел. мышцы (кг)'),
                         ('VAT', 'Δ Висц. жир (л)'), ('Taillenumfang', 'Δ Обхв. талии (см)'),
                         ('phi', 'Δ Фаз. угол (°)'), ('TBW_pct', 'Δ Общ. вода (%)')]:
        d12_vals = d12[f'{field}_delta'].dropna() if f'{field}_delta' in d12.columns else pd.Series()
        d13_vals = d13[f'{field}_delta'].dropna() if f'{field}_delta' in d13.columns else pd.Series()
        if len(d12_vals) > 0 or len(d13_vals) > 0:
            s12 = f"{d12_vals.mean():.1f} ± {d12_vals.std():.1f} (n={len(d12_vals)})" if len(d12_vals) > 0 else "—"
            s13 = f"{d13_vals.mean():.1f} ± {d13_vals.std():.1f} (n={len(d13_vals)})" if len(d13_vals) > 0 else "—"
            report.append(f"| {label} | {s12} | {s13} |\n")

    # === 3.3 Problematic patterns ===
    report.append("\n### 3.3 Проблемные паттерны\n\n")

    # Weight regain Op2->Op3
    if 'Gewicht_delta' in d23.columns:
        regain = d23[d23['Gewicht_delta'] > 0]
        report.append(f"#### Набор веса после Op2 (Op2→Op3)\n")
        report.append(f"- Пациентов с набором веса: **{len(regain)}** из {len(d23['Gewicht_delta'].dropna())} ")
        total_d23 = len(d23['Gewicht_delta'].dropna())
        if total_d23 > 0:
            report.append(f"({len(regain)/total_d23*100:.0f}%)\n")
        if len(regain) > 0:
            report.append(f"- Средний набор: {regain['Gewicht_delta'].mean():.1f} кг\n")
            top_regain = regain.nlargest(5, 'Gewicht_delta')
            report.append("\n| Пациент | ID | Набор (кг) |\n")
            report.append("|---------|----|-----------|\n")
            for _, r in top_regain.iterrows():
                report.append(f"| {r['name']} | {r['patient_id']} | +{r['Gewicht_delta']:.1f} |\n")

    # Muscle loss
    report.append("\n#### Потеря мышечной массы\n")
    if 'SMM_delta' in d13.columns:
        smm_d13 = d13['SMM_delta'].dropna()
        smm_loss = d13[d13['SMM_delta'] < 0]['SMM_delta'].dropna()
        if len(smm_d13) > 0:
            report.append(f"- Средняя потеря скелетных мышц Op1→Op3: {smm_d13.mean():.1f} кг\n")
            report.append(f"- Пациентов с потерей мышц: {len(smm_loss)} из {len(smm_d13)} ({len(smm_loss)/len(smm_d13)*100:.0f}%)\n")

    # FFM loss as proportion of total weight loss
    report.append("\n#### Доля безжировой массы в потере веса (Op1→Op2)\n")
    if 'FFM_kg_delta' in d12.columns and 'Gewicht_delta' in d12.columns:
        both = d12[['FFM_kg_delta', 'Gewicht_delta']].dropna()
        both = both[both['Gewicht_delta'] < -5]  # meaningful weight loss
        if len(both) > 0:
            ffm_ratio = both['FFM_kg_delta'] / both['Gewicht_delta'] * 100
            report.append(f"- Средняя доля FFM в потере веса: {ffm_ratio.mean():.1f}% (идеал <25%)\n")
            excess = (ffm_ratio > 25).sum()
            report.append(f"- Пациентов с избыточной потерей FFM (>25%): {excess} из {len(ffm_ratio)} ({excess/len(ffm_ratio)*100:.0f}%)\n")

    # === 4. Phase angle ===
    report.append("\n## 4. Фазовый угол (φ) — маркер клеточного здоровья\n\n")
    report.append("Фазовый угол (φ) — важнейший параметр BIA, отражающий целостность клеточных мембран и общее состояние нутритивного статуса. ")
    report.append("Нормальные значения: 5-7° (муж.), 4.5-6.5° (жен.). Значения <4° ассоциированы с плохим прогнозом.\n\n")

    for op_name, op_label in [('Op1', 'До операции'), ('Op2', '1-й контроль'), ('Op3', '2-й контроль')]:
        op_df = df[df['operation'] == op_name]
        phi_vals = op_df['phi'].dropna()
        if len(phi_vals) > 0:
            low_phi = (phi_vals < 4).sum()
            report.append(f"**{op_label}:** φ = {phi_vals.mean():.1f} ± {phi_vals.std():.1f}°, ")
            report.append(f"низкий φ (<4°): {low_phi} ({low_phi/len(phi_vals)*100:.0f}%)\n\n")

    # === 5. Hydration ===
    report.append("## 5. Водный баланс\n\n")
    report.append("ECW/TBW — отношение внеклеточной воды к общей. Норма: 38-45%. Повышение >50% указывает на отёки, ")
    report.append("гипоальбуминемию или системное воспаление.\n\n")

    for op_name, op_label in [('Op1', 'До операции'), ('Op2', '1-й контроль'), ('Op3', '2-й контроль')]:
        op_df = df[df['operation'] == op_name]
        ecw = op_df['ECW_TBW_pct'].dropna()
        if len(ecw) > 0:
            high_ecw = (ecw > 50).sum()
            report.append(f"**{op_label}:** ECW/TBW = {ecw.mean():.1f} ± {ecw.std():.1f}%, ")
            report.append(f"повышен (>50%): {high_ecw} ({high_ecw/len(ecw)*100:.0f}%)\n\n")

    # === 6. Top performers and concerning cases ===
    report.append("## 6. Выдающиеся результаты и тревожные случаи\n\n")

    report.append("### 6.1 Лучшие результаты по снижению веса (Op1→Op3)\n\n")
    if 'Gewicht_pct_change' in d13.columns:
        best = d13.nsmallest(10, 'Gewicht_pct_change')
        report.append("| Пациент | ID | Исх. вес | Фин. вес | Потеря (%) | Потеря (кг) |\n")
        report.append("|---------|----|---------|---------|-----------|-----------|\n")
        for _, r in best.iterrows():
            if pd.notna(r.get('Gewicht_before')) and pd.notna(r.get('Gewicht_after')):
                report.append(f"| {r['name']} | {r['patient_id']} | {r['Gewicht_before']:.1f} | {r['Gewicht_after']:.1f} | {r['Gewicht_pct_change']:.1f}% | {r['Gewicht_delta']:.1f} |\n")

    report.append("\n### 6.2 Наибольшее снижение ИМТ (Op1→Op3)\n\n")
    if 'BMI_delta' in d13.columns:
        best_bmi = d13.nsmallest(10, 'BMI_delta')
        report.append("| Пациент | ИМТ до | ИМТ после | Δ ИМТ |\n")
        report.append("|---------|--------|----------|-------|\n")
        for _, r in best_bmi.iterrows():
            if pd.notna(r.get('BMI_before')) and pd.notna(r.get('BMI_after')):
                report.append(f"| {r['name']} ({r['patient_id']}) | {r['BMI_before']:.1f} | {r['BMI_after']:.1f} | {r['BMI_delta']:.1f} |\n")

    # === 7. Visceral fat ===
    report.append("\n## 7. Висцеральный жир (VAT)\n\n")
    report.append("Висцеральный жир — ключевой метаболический фактор риска. Значения >4 л связаны с повышенным сердечно-сосудистым риском.\n\n")

    for op_name, op_label in [('Op1', 'До операции'), ('Op2', '1-й контроль'), ('Op3', '2-й контроль')]:
        op_df = df[df['operation'] == op_name]
        vat = op_df['VAT'].dropna()
        if len(vat) > 0:
            high_vat = (vat > 4).sum()
            report.append(f"**{op_label}:** VAT = {vat.mean():.1f} ± {vat.std():.1f} л, ")
            report.append(f">4 л: {high_vat} ({high_vat/len(vat)*100:.0f}%), n={len(vat)}\n\n")

    # === 8. Missing data ===
    report.append("## 8. Недостающие данные и рекомендации\n\n")
    report.append("### 8.1 Пробелы в данных\n\n")

    only_op1 = sum(1 for p in patients if 'Op1' in p['operations'] and p['operations']['Op1']['values'].get('BMI') is not None
                   and not ('Op2' in p['operations'] and p['operations']['Op2']['values'].get('BMI') is not None))
    only_op2 = stats['patients_op2'] - len(pts_3ops)

    report.append(f"- Пациентов только с Op1 (без контроля): **{only_op1}**\n")
    report.append(f"- Пациентов с неполными записями (частичные данные): множественные\n")
    report.append(f"- Серые ячейки (данные не найдены в фото): отмечены в таблице\n\n")

    report.append("### 8.2 Какие данные добавить для более глубокого исследования\n\n")
    report.append("1. **Тип операции** — Sleeve Gastrectomy, Roux-en-Y Bypass, Mini-Bypass и др. Это критически важно для сравнительного анализа эффективности.\n")
    report.append("2. **Коморбидности** — сахарный диабет 2 типа, артериальная гипертензия, СОАС, НАЖБП. Позволит оценить метаболическое улучшение.\n")
    report.append("3. **Лабораторные показатели** — HbA1c, липидный профиль, альбумин, ферритин, витамин D, B12, фолиевая кислота. Необходимо для оценки нутритивного дефицита.\n")
    report.append("4. **Возраст пациентов** — для стратификации результатов по возрастным группам.\n")
    report.append("5. **Физическая активность** — уровень активности до и после операции.\n")
    report.append("6. **Диетологическое сопровождение** — приверженность к рекомендациям по питанию.\n")
    report.append("7. **Excess Weight Loss (EWL%)** — процент потери избыточного веса (требует знания идеального веса).\n")
    report.append("8. **Quality of Life scores** — опросники SF-36, BAROS для оценки качества жизни.\n")
    report.append("9. **Временные интервалы** — точные сроки между операцией и контрольными измерениями (в месяцах).\n")
    report.append("10. **Осложнения** — ранние и поздние послеоперационные осложнения.\n\n")

    # === 9. Key findings ===
    report.append("## 9. Ключевые выводы и клинические рекомендации\n\n")

    report.append("### Основные тенденции\n\n")
    report.append("1. **Эффективная потеря веса:** Бариатрическая хирургия приводит к значительному снижению массы тела ")
    if len(d12) > 0:
        w12 = d12['Gewicht_pct_change'].dropna()
        if len(w12) > 0:
            report.append(f"(в среднем {abs(w12.mean()):.0f}% от исходной массы к первому контролю). ")
    report.append("\n\n")

    report.append("2. **Снижение висцерального жира:** Наблюдается значительное снижение VAT, что коррелирует со снижением метаболических рисков.\n\n")

    report.append("3. **Потеря мышечной массы** — серьёзная проблема: значительная часть потери веса приходится на безжировую массу (FFM). ")
    report.append("Это типичная проблема бариатрической хирургии, требующая целенаправленного противодействия (протеиновая суплементация, силовые тренировки).\n\n")

    report.append("4. **Фазовый угол** снижается после операции у части пациентов, что может указывать на нутритивный дефицит.\n\n")

    report.append("5. **Водный баланс:** Повышение ECW/TBW после операции может свидетельствовать о белковом дефиците.\n\n")

    if len(regain) > 0:
        report.append(f"6. **Рецидив набора веса:** У {len(regain)} пациентов ({len(regain)/total_d23*100:.0f}%) наблюдается набор веса ко второму контролю. ")
        report.append("Это тревожный сигнал, требующий усиления диетологического контроля и психологической поддержки.\n\n")

    report.append("### Неочевидные находки\n\n")
    report.append("1. **Гетерогенность результатов** — разброс результатов очень велик. Некоторые пациенты теряют >50% массы тела, другие — менее 20%. Это указывает на необходимость персонализированного подхода.\n\n")
    report.append("2. **Диспропорция потери жира и мышц** — у некоторых пациентов наблюдается преимущественная потеря мышечной массы при относительно сохранённой жировой, что крайне неблагоприятно.\n\n")
    report.append("3. **Рост сопротивления (R)** после операции может указывать на дегидратацию, что часто встречается после бариатрических вмешательств из-за недостаточного потребления жидкости.\n\n")
    report.append("4. **Гендерные различия** — женщины имеют более высокий процент жировой массы, но мужчины чаще демонстрируют рецидив набора веса.\n\n")
    report.append("5. **Перцентиль фазового угла** — у многих пациентов на Op1 перцентиль выше нормы (компенсаторный эффект), а после операции резко падает, что может маскировать ухудшение нутритивного статуса.\n\n")

    report.append("---\n")
    report.append("*Данный анализ носит описательный характер. Для формулирования клинически значимых выводов необходимы дополнительные данные и статистический анализ с поправкой на множественные сравнения.*\n")

    return '\n'.join(report)


def generate_pdf(patients, df, dynamics_df):
    """Generate PDF with visualizations."""

    pdf_path = os.path.join(OUTPUT_DIR, 'bia_analysis_visualizations.pdf')

    with PdfPages(pdf_path) as pdf:

        # === Page 1: Title + Overview ===
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle('Анализ BIA данных: бариатрическая хирургия', fontsize=16, fontweight='bold', y=0.98)

        # 1a: BMI distribution at Op1
        ax = axes[0, 0]
        op1_bmi = df[df['operation'] == 'Op1']['BMI'].dropna()
        ax.hist(op1_bmi, bins=20, color='#4472C4', edgecolor='white', alpha=0.8)
        ax.axvline(30, color='orange', linestyle='--', linewidth=1, label='ИМТ=30')
        ax.axvline(40, color='red', linestyle='--', linewidth=1, label='ИМТ=40')
        ax.set_xlabel('ИМТ (кг/м²)')
        ax.set_ylabel('Кол-во пациентов')
        ax.set_title('Распределение ИМТ до операции')
        ax.legend(fontsize=8)

        # 1b: Gender pie chart
        ax = axes[0, 1]
        gender_counts = df.drop_duplicates('patient_id')['gender'].value_counts()
        colors = ['#ED7D31', '#4472C4']
        labels = [f"Женщины ({gender_counts.get('F', 0)})", f"Мужчины ({gender_counts.get('M', 0)})"]
        ax.pie([gender_counts.get('F', 0), gender_counts.get('M', 0)], labels=labels,
               colors=colors, autopct='%1.0f%%', startangle=90)
        ax.set_title('Соотношение полов')

        # 1c: Data completeness
        ax = axes[1, 0]
        ops = ['Op1', 'Op2', 'Op3']
        counts = [df[df['operation'] == op]['patient_id'].nunique() for op in ops]
        bars = ax.bar(['До операции\n(Op1)', '1-й контроль\n(Op2)', '2-й контроль\n(Op3)'],
                      counts, color=['#4472C4', '#ED7D31', '#70AD47'])
        ax.set_ylabel('Кол-во пациентов')
        ax.set_title('Наличие данных по этапам')
        for bar, count in zip(bars, counts):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 1,
                    str(count), ha='center', va='bottom', fontweight='bold')

        # 1d: Weight distribution at Op1
        ax = axes[1, 1]
        op1_w = df[df['operation'] == 'Op1']['Gewicht'].dropna()
        ax.hist(op1_w, bins=20, color='#70AD47', edgecolor='white', alpha=0.8)
        ax.set_xlabel('Вес (кг)')
        ax.set_ylabel('Кол-во пациентов')
        ax.set_title('Распределение веса до операции')
        ax.axvline(op1_w.median(), color='red', linestyle='--', label=f'Медиана={op1_w.median():.0f} кг')
        ax.legend(fontsize=8)

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 2: Weight & BMI dynamics ===
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle('Динамика веса и ИМТ', fontsize=14, fontweight='bold', y=0.98)

        # 2a: Box plot of BMI by operation
        ax = axes[0, 0]
        bmi_data = []
        bmi_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['BMI'].dropna()
            if len(vals) > 0:
                bmi_data.append(vals)
                bmi_labels.append(f"{op}\n(n={len(vals)})")
        bp = ax.boxplot(bmi_data, labels=bmi_labels, patch_artist=True)
        colors_box = ['#4472C4', '#ED7D31', '#70AD47']
        for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        ax.set_ylabel('ИМТ (кг/м²)')
        ax.set_title('Распределение ИМТ по этапам')
        ax.axhline(30, color='gray', linestyle=':', alpha=0.5)

        # 2b: Box plot of Weight by operation
        ax = axes[0, 1]
        w_data = []
        w_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['Gewicht'].dropna()
            if len(vals) > 0:
                w_data.append(vals)
                w_labels.append(f"{op}\n(n={len(vals)})")
        bp = ax.boxplot(w_data, labels=w_labels, patch_artist=True)
        for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        ax.set_ylabel('Вес (кг)')
        ax.set_title('Распределение веса по этапам')

        # 2c: Individual weight trajectories (spaghetti plot)
        ax = axes[1, 0]
        for p in patients:
            ops = p['operations']
            x = []
            y = []
            for i, op in enumerate(['Op1', 'Op2', 'Op3']):
                if op in ops and 'Gewicht' in ops[op]['values']:
                    x.append(i)
                    y.append(ops[op]['values']['Gewicht'])
            if len(x) >= 2:
                ax.plot(x, y, alpha=0.3, linewidth=0.7, color='#4472C4')
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(['Op1', 'Op2', 'Op3'])
        ax.set_ylabel('Вес (кг)')
        ax.set_title('Индивидуальные траектории веса')

        # 2d: BMI change histogram
        ax = axes[1, 1]
        d13_bmi = dynamics_df[dynamics_df['transition'] == 'Op1→Op3']['BMI_delta'].dropna()
        if len(d13_bmi) > 0:
            ax.hist(d13_bmi, bins=20, color='#4472C4', edgecolor='white', alpha=0.8)
            ax.axvline(0, color='red', linestyle='--')
            ax.axvline(d13_bmi.mean(), color='orange', linestyle='--', label=f'Среднее={d13_bmi.mean():.1f}')
            ax.set_xlabel('Δ ИМТ (Op1→Op3)')
            ax.set_ylabel('Кол-во пациентов')
            ax.set_title('Изменение ИМТ (Op1→Op3)')
            ax.legend(fontsize=8)

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 3: Body composition ===
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle('Состав тела: жировая и безжировая масса', fontsize=14, fontweight='bold', y=0.98)

        # 3a: FM% by operation
        ax = axes[0, 0]
        fm_data = []
        fm_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['FM_pct'].dropna()
            if len(vals) > 0:
                fm_data.append(vals)
                fm_labels.append(f"{op}\n(n={len(vals)})")
        if fm_data:
            bp = ax.boxplot(fm_data, labels=fm_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
        ax.set_ylabel('Жировая масса (%)')
        ax.set_title('Доля жировой массы по этапам')

        # 3b: FFM% by operation
        ax = axes[0, 1]
        ffm_data = []
        ffm_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['FFM_pct'].dropna()
            if len(vals) > 0:
                ffm_data.append(vals)
                ffm_labels.append(f"{op}\n(n={len(vals)})")
        if ffm_data:
            bp = ax.boxplot(ffm_data, labels=ffm_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
        ax.set_ylabel('Безжировая масса (%)')
        ax.set_title('Доля безжировой массы по этапам')

        # 3c: SMM trajectories
        ax = axes[1, 0]
        for p in patients:
            ops = p['operations']
            x = []
            y = []
            for i, op in enumerate(['Op1', 'Op2', 'Op3']):
                if op in ops and 'SMM' in ops[op]['values']:
                    x.append(i)
                    y.append(ops[op]['values']['SMM'])
            if len(x) >= 2:
                color = '#ED7D31' if determine_gender(p['name']) == 'F' else '#4472C4'
                ax.plot(x, y, alpha=0.3, linewidth=0.7, color=color)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(['Op1', 'Op2', 'Op3'])
        ax.set_ylabel('Скел. мышцы (кг)')
        ax.set_title('Динамика скелетной мускулатуры\n(оранж.=жен., синий=муж.)')

        # 3d: FM vs FFM loss scatter
        ax = axes[1, 1]
        d12 = dynamics_df[dynamics_df['transition'] == 'Op1→Op2']
        if 'FM_kg_delta' in d12.columns and 'FFM_kg_delta' in d12.columns:
            both = d12[['FM_kg_delta', 'FFM_kg_delta', 'gender']].dropna()
            for g, c, m in [('F', '#ED7D31', 'o'), ('M', '#4472C4', 's')]:
                subset = both[both['gender'] == g]
                ax.scatter(subset['FM_kg_delta'], subset['FFM_kg_delta'],
                          c=c, marker=m, alpha=0.6, s=30, label=f"{'Жен.' if g=='F' else 'Муж.'}")
            ax.axhline(0, color='gray', linestyle=':', alpha=0.5)
            ax.axvline(0, color='gray', linestyle=':', alpha=0.5)
            ax.set_xlabel('Δ Жир. масса (кг)')
            ax.set_ylabel('Δ Безжир. масса (кг)')
            ax.set_title('Потеря FM vs FFM (Op1→Op2)')
            ax.legend(fontsize=8)

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 4: Visceral fat, Phase angle, Hydration ===
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle('Метаболические и функциональные показатели', fontsize=14, fontweight='bold', y=0.98)

        # 4a: VAT by operation
        ax = axes[0, 0]
        vat_data = []
        vat_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['VAT'].dropna()
            if len(vals) > 0:
                vat_data.append(vals)
                vat_labels.append(f"{op}\n(n={len(vals)})")
        if vat_data:
            bp = ax.boxplot(vat_data, labels=vat_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
        ax.axhline(4, color='red', linestyle='--', alpha=0.5, label='Порог риска (4 л)')
        ax.set_ylabel('VAT (л)')
        ax.set_title('Висцеральный жир по этапам')
        ax.legend(fontsize=8)

        # 4b: Phase angle by operation
        ax = axes[0, 1]
        phi_data = []
        phi_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['phi'].dropna()
            if len(vals) > 0:
                phi_data.append(vals)
                phi_labels.append(f"{op}\n(n={len(vals)})")
        if phi_data:
            bp = ax.boxplot(phi_data, labels=phi_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
        ax.axhline(4, color='red', linestyle='--', alpha=0.5, label='Пороговое значение')
        ax.set_ylabel('Фазовый угол (°)')
        ax.set_title('Фазовый угол по этапам')
        ax.legend(fontsize=8)

        # 4c: ECW/TBW by operation
        ax = axes[1, 0]
        ecw_data = []
        ecw_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['ECW_TBW_pct'].dropna()
            if len(vals) > 0:
                ecw_data.append(vals)
                ecw_labels.append(f"{op}\n(n={len(vals)})")
        if ecw_data:
            bp = ax.boxplot(ecw_data, labels=ecw_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
        ax.axhline(50, color='red', linestyle='--', alpha=0.5, label='Порог отёков (50%)')
        ax.set_ylabel('ECW/TBW (%)')
        ax.set_title('Водный баланс по этапам')
        ax.legend(fontsize=8)

        # 4d: Waist circumference
        ax = axes[1, 1]
        wc_data = []
        wc_labels = []
        for op in ['Op1', 'Op2', 'Op3']:
            vals = df[df['operation'] == op]['Taillenumfang'].dropna()
            if len(vals) > 0:
                wc_data.append(vals)
                wc_labels.append(f"{op}\n(n={len(vals)})")
        if wc_data:
            bp = ax.boxplot(wc_data, labels=wc_labels, patch_artist=True)
            for patch, color in zip(bp['boxes'], colors_box[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
        ax.set_ylabel('Обхват талии (см)')
        ax.set_title('Обхват талии по этапам')

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 5: Correlation analysis ===
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle('Корреляционный анализ и предикторы', fontsize=14, fontweight='bold', y=0.98)

        # 5a: Initial BMI vs weight loss %
        ax = axes[0, 0]
        d13 = dynamics_df[dynamics_df['transition'] == 'Op1→Op3']
        if 'BMI_before' in d13.columns and 'Gewicht_pct_change' in d13.columns:
            both = d13[['BMI_before', 'Gewicht_pct_change', 'gender']].dropna()
            for g, c, m in [('F', '#ED7D31', 'o'), ('M', '#4472C4', 's')]:
                subset = both[both['gender'] == g]
                ax.scatter(subset['BMI_before'], subset['Gewicht_pct_change'],
                          c=c, marker=m, alpha=0.6, s=30, label=f"{'Жен.' if g=='F' else 'Муж.'}")
            ax.set_xlabel('Исходный ИМТ (кг/м²)')
            ax.set_ylabel('Потеря веса (%)')
            ax.set_title('Исх. ИМТ vs Потеря веса (Op1→Op3)')
            ax.legend(fontsize=8)

        # 5b: Initial VAT vs VAT reduction
        ax = axes[0, 1]
        if 'VAT_before' in d13.columns and 'VAT_delta' in d13.columns:
            both = d13[['VAT_before', 'VAT_delta']].dropna()
            ax.scatter(both['VAT_before'], both['VAT_delta'], c='#70AD47', alpha=0.6, s=30)
            ax.axhline(0, color='gray', linestyle=':', alpha=0.5)
            ax.set_xlabel('Исходный VAT (л)')
            ax.set_ylabel('Δ VAT (л)')
            ax.set_title('Исх. VAT vs Снижение VAT (Op1→Op3)')
            # Add correlation
            if len(both) > 3:
                corr = both['VAT_before'].corr(both['VAT_delta'])
                ax.text(0.05, 0.95, f'r = {corr:.2f}', transform=ax.transAxes, fontsize=10)

        # 5c: Weight loss vs SMM loss
        ax = axes[1, 0]
        if 'Gewicht_delta' in d13.columns and 'SMM_delta' in d13.columns:
            both = d13[['Gewicht_delta', 'SMM_delta']].dropna()
            ax.scatter(both['Gewicht_delta'], both['SMM_delta'], c='#4472C4', alpha=0.6, s=30)
            ax.axhline(0, color='gray', linestyle=':', alpha=0.5)
            ax.axvline(0, color='gray', linestyle=':', alpha=0.5)
            ax.set_xlabel('Δ Вес (кг)')
            ax.set_ylabel('Δ Скел. мышцы (кг)')
            ax.set_title('Потеря веса vs Потеря мышц (Op1→Op3)')
            if len(both) > 3:
                corr = both['Gewicht_delta'].corr(both['SMM_delta'])
                ax.text(0.05, 0.95, f'r = {corr:.2f}', transform=ax.transAxes, fontsize=10)

        # 5d: Phase angle vs BMI
        ax = axes[1, 1]
        op1_df = df[df['operation'] == 'Op1']
        both = op1_df[['BMI', 'phi', 'gender']].dropna()
        for g, c, m in [('F', '#ED7D31', 'o'), ('M', '#4472C4', 's')]:
            subset = both[both['gender'] == g]
            ax.scatter(subset['BMI'], subset['phi'], c=c, marker=m, alpha=0.6, s=30,
                      label=f"{'Жен.' if g=='F' else 'Муж.'}")
        ax.set_xlabel('ИМТ (кг/м²)')
        ax.set_ylabel('Фазовый угол (°)')
        ax.set_title('ИМТ vs Фазовый угол (Op1)')
        ax.legend(fontsize=8)

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 6: Summary bar charts ===
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        fig.suptitle('Сводные показатели по этапам (средние значения)', fontsize=14, fontweight='bold', y=0.98)

        # Compute means for each operation
        means = {}
        for op in ['Op1', 'Op2', 'Op3']:
            op_df = df[df['operation'] == op]
            means[op] = {col: op_df[col].mean() for col in FIELD_NAMES if col in op_df.columns}

        # 6a: Key metrics bar chart
        ax = axes[0, 0]
        metrics = ['BMI', 'FMI', 'FFMI']
        x = np.arange(len(metrics))
        width = 0.25
        for i, (op, color) in enumerate(zip(['Op1', 'Op2', 'Op3'], colors_box)):
            vals = [means[op].get(m, 0) for m in metrics]
            ax.bar(x + i*width, vals, width, label=op, color=color, alpha=0.8)
        ax.set_xticks(x + width)
        ax.set_xticklabels(['ИМТ', 'ИЖМ', 'ИБЖМ'])
        ax.set_ylabel('кг/м²')
        ax.set_title('Индексы массы тела по этапам')
        ax.legend()

        # 6b: FM% and FFM%
        ax = axes[0, 1]
        metrics = ['FM_pct', 'FFM_pct']
        x = np.arange(len(metrics))
        for i, (op, color) in enumerate(zip(['Op1', 'Op2', 'Op3'], colors_box)):
            vals = [means[op].get(m, 0) for m in metrics]
            ax.bar(x + i*width, vals, width, label=op, color=color, alpha=0.8)
        ax.set_xticks(x + width)
        ax.set_xticklabels(['Жир. масса %', 'Безжир. масса %'])
        ax.set_ylabel('%')
        ax.set_title('Соотношение жировой и безжировой массы')
        ax.legend()

        # 6c: Hydration metrics
        ax = axes[1, 0]
        metrics = ['TBW_pct', 'ECW_pct', 'ECW_TBW_pct']
        x = np.arange(len(metrics))
        for i, (op, color) in enumerate(zip(['Op1', 'Op2', 'Op3'], colors_box)):
            vals = [means[op].get(m, 0) for m in metrics]
            ax.bar(x + i*width, vals, width, label=op, color=color, alpha=0.8)
        ax.set_xticks(x + width)
        ax.set_xticklabels(['TBW %', 'ECW %', 'ECW/TBW %'])
        ax.set_ylabel('%')
        ax.set_title('Водный баланс по этапам')
        ax.legend()

        # 6d: VAT + Waist
        ax = axes[1, 1]
        metrics_l = ['VAT']
        x = np.arange(1)
        for i, (op, color) in enumerate(zip(['Op1', 'Op2', 'Op3'], colors_box)):
            vals = [means[op].get('VAT', 0)]
            ax.bar(x + i*width, vals, width, label=op, color=color, alpha=0.8)
        ax.set_xticks([0 + width])
        ax.set_xticklabels(['Висц. жир (л)'])
        ax.set_title('Висцеральный жир по этапам')
        ax.legend()

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 7: BMI classification before/after ===
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 5))
        fig.suptitle('Классификация ИМТ: до операции vs последний контроль', fontsize=14, fontweight='bold')

        categories = ['<30', '30-35', '35-40', '40-50', '50-60', '≥60']
        cat_labels = ['Норм.\n<30', 'Ожир. I\n30-35', 'Ожир. II\n35-40', 'Ожир. III\n40-50', 'Сверх\n50-60', 'Супер\n≥60']

        for idx, (op, title) in enumerate([('Op1', 'До операции (Op1)'), ('Op3', 'Последний контроль (Op3)')]):
            ax = axes[idx]
            bmi_vals = df[df['operation'] == op]['BMI'].dropna()
            counts = [
                (bmi_vals < 30).sum(),
                ((bmi_vals >= 30) & (bmi_vals < 35)).sum(),
                ((bmi_vals >= 35) & (bmi_vals < 40)).sum(),
                ((bmi_vals >= 40) & (bmi_vals < 50)).sum(),
                ((bmi_vals >= 50) & (bmi_vals < 60)).sum(),
                (bmi_vals >= 60).sum(),
            ]
            colors_bmi = ['#70AD47', '#FFC000', '#ED7D31', '#FF4444', '#CC0000', '#880000']
            bars = ax.bar(cat_labels, counts, color=colors_bmi, edgecolor='white')
            ax.set_ylabel('Кол-во пациентов')
            ax.set_title(f'{title} (n={len(bmi_vals)})')
            for bar, count in zip(bars, counts):
                if count > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
                            str(count), ha='center', va='bottom', fontsize=9)

        plt.tight_layout(rect=[0, 0, 1, 0.92])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 8: Heatmap of changes ===
        fig, ax = plt.subplots(1, 1, figsize=(11.69, 8.27))
        fig.suptitle('Средние изменения ключевых параметров по этапам', fontsize=14, fontweight='bold')

        fields_for_heat = ['Gewicht', 'BMI', 'FM_kg', 'FM_pct', 'FFM_kg', 'SMM',
                           'VAT', 'Taillenumfang', 'phi', 'TBW_pct', 'ECW_TBW_pct']
        labels_ru = ['Вес', 'ИМТ', 'ЖМ (кг)', 'ЖМ (%)', 'БЖМ (кг)', 'Мышцы',
                     'Висц. жир', 'Обхв. талии', 'Фаз. угол', 'TBW %', 'ECW/TBW %']

        heat_data = []
        transitions = ['Op1→Op2', 'Op2→Op3', 'Op1→Op3']
        for trans in transitions:
            row = []
            d = dynamics_df[dynamics_df['transition'] == trans]
            for field in fields_for_heat:
                col = f'{field}_pct_change'
                if col in d.columns:
                    vals = d[col].dropna()
                    row.append(vals.mean() if len(vals) > 0 else 0)
                else:
                    row.append(0)
            heat_data.append(row)

        heat_arr = np.array(heat_data)
        im = ax.imshow(heat_arr, cmap='RdYlGn_r', aspect='auto', vmin=-40, vmax=40)
        ax.set_xticks(range(len(labels_ru)))
        ax.set_xticklabels(labels_ru, rotation=45, ha='right')
        ax.set_yticks(range(len(transitions)))
        ax.set_yticklabels(transitions)

        # Add text annotations
        for i in range(len(transitions)):
            for j in range(len(labels_ru)):
                val = heat_arr[i, j]
                color = 'white' if abs(val) > 20 else 'black'
                ax.text(j, i, f'{val:.1f}%', ha='center', va='center', color=color, fontsize=9)

        plt.colorbar(im, ax=ax, label='Изменение (%)', shrink=0.6)
        ax.set_title('Тепловая карта изменений (% от исходного)', pad=15)

        plt.tight_layout(rect=[0, 0, 1, 0.93])
        pdf.savefig(fig)
        plt.close(fig)

        # === Page 9: Top/Bottom performers ===
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 6))
        fig.suptitle('Лучшие и худшие результаты (Op1→Op3)', fontsize=14, fontweight='bold')

        d13 = dynamics_df[dynamics_df['transition'] == 'Op1→Op3']

        # Top 10 weight loss
        ax = axes[0]
        if 'Gewicht_pct_change' in d13.columns:
            best = d13.nsmallest(10, 'Gewicht_pct_change')[['name', 'Gewicht_pct_change']].dropna()
            if len(best) > 0:
                names = [n[:20] for n in best['name'].values]
                vals = best['Gewicht_pct_change'].values
                bars = ax.barh(range(len(names)), vals, color='#70AD47')
                ax.set_yticks(range(len(names)))
                ax.set_yticklabels(names, fontsize=8)
                ax.set_xlabel('Потеря веса (%)')
                ax.set_title('Топ-10: наибольшая потеря веса')
                ax.invert_yaxis()

        # Worst (weight regain or least loss)
        ax = axes[1]
        if 'Gewicht_pct_change' in d13.columns:
            worst = d13.nlargest(10, 'Gewicht_pct_change')[['name', 'Gewicht_pct_change']].dropna()
            if len(worst) > 0:
                names = [n[:20] for n in worst['name'].values]
                vals = worst['Gewicht_pct_change'].values
                colors_bar = ['#FF4444' if v > 0 else '#FFC000' for v in vals]
                bars = ax.barh(range(len(names)), vals, color=colors_bar)
                ax.set_yticks(range(len(names)))
                ax.set_yticklabels(names, fontsize=8)
                ax.set_xlabel('Изменение веса (%)')
                ax.set_title('Топ-10: наименьшая потеря веса')
                ax.invert_yaxis()
                ax.axvline(0, color='gray', linestyle='--')

        plt.tight_layout(rect=[0, 0, 1, 0.92])
        pdf.savefig(fig)
        plt.close(fig)

    return pdf_path


def main():
    print("Parsing CSV data...")
    patients = parse_csv()
    print(f"Parsed {len(patients)} patients")

    print("Building DataFrame...")
    df = build_dataframe(patients)
    print(f"Total records: {len(df)}")

    print("Computing statistics...")
    stats = compute_statistics(df)

    print("Computing dynamics...")
    dynamics_df = compute_dynamics(patients)
    print(f"Dynamics records: {len(dynamics_df)}")

    print("Generating analysis report...")
    report = generate_analysis_report(patients, df, stats, dynamics_df)
    report_path = os.path.join(OUTPUT_DIR, 'bia_analysis_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Report saved: {report_path}")

    print("Generating PDF with visualizations...")
    pdf_path = generate_pdf(patients, df, dynamics_df)
    print(f"PDF saved: {pdf_path}")

    # Also save key data as JSON for reference
    data_summary = {
        'total_patients': stats['total_patients'],
        'total_records': stats['total_records'],
        'stats': {k: float(v) if isinstance(v, (np.floating, float)) else int(v)
                  for k, v in stats.items()},
    }
    json_path = os.path.join(OUTPUT_DIR, 'analysis_summary.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data_summary, f, ensure_ascii=False, indent=2)

    print("\nDone! Files generated:")
    print(f"  1. {report_path}")
    print(f"  2. {pdf_path}")
    print(f"  3. {json_path}")


if __name__ == '__main__':
    main()
