# SLA Training Dashboard - New Structure
# ระบบ Dashboard สำหรับติดตาม SLA การลงทะเบียนช่าง
# รองรับ SLA 6 ขั้นตอน: Training > OJT > GenID > Inspection > DFlow > Registration

from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
from datetime import datetime
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# ===============================
# SUPABASE CONFIGURATION
# ===============================

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===============================
# COLUMN MAPPINGS
# ===============================

# SLA Steps - 8 ขั้นตอนหลัก
# เพิ่ม start_col และ end_col สำหรับตรวจสอบว่ามีการดำเนินการจริง
SLA_STEPS = [
    {'key': 'doc', 'name': 'เอกสาร', 'sla_col': 'sla_doc', 'status_col': 'status_doc', 'result_col': 'result_doc', 'start_col': 'doc_start', 'end_col': 'doc_end'},
    {'key': 'training', 'name': 'อบรมทฤษฎี', 'sla_col': 'sla_training', 'status_col': 'status_result_round', 'result_col': 'result_round', 'start_col': 'training_start', 'end_col': 'training_end'},
    {'key': 'ojt', 'name': 'OJT', 'sla_col': 'sla_ojt', 'status_col': 'status_result_ojt', 'result_col': 'result_round_ojt', 'start_col': 'ojt_start', 'end_col': 'ojt_end'},
    {'key': 'genid', 'name': 'Gen ID', 'sla_col': 'sla_genid', 'status_col': 'status_genid', 'result_col': 'result_genid', 'start_col': 'genid_start', 'end_col': 'genid_end'},
    {'key': 'printcard', 'name': 'Print Card', 'sla_col': 'sla_printcard', 'status_col': 'status_printcard', 'result_col': 'result_printcard', 'start_col': 'printcard_start', 'end_col': 'printcard_end'},
    {'key': 'inspection', 'name': 'ตรวจความพร้อม', 'sla_col': 'sla_inspection', 'status_col': 'status_inspection', 'result_col': 'result_inspection', 'start_col': 'inspection_start', 'end_col': 'inspection_end'},
    {'key': 'dflow', 'name': 'DFlow', 'sla_col': 'sla_dflow', 'status_col': 'status_dflow', 'result_col': 'result_dflow', 'start_col': 'dflow_start', 'end_col': 'dflow_end'},
    {'key': 'registration', 'name': 'ขึ้นทะเบียน', 'sla_col': 'sla_registration', 'status_col': 'status_registration', 'result_col': 'result_registration', 'start_col': 'registration_start', 'end_col': 'registration_end'}
]

# ===============================
# CONTEXT PROCESSOR
# ===============================

@app.context_processor
def inject_current_date():
    """ส่งวันที่ปัจจุบันไปทุก template"""
    from datetime import datetime
    # แสดงวันที่แบบ "24 December 2025"
    now = datetime.now()
    current_date = now.strftime("%d %B %Y")
    return {'current_date': current_date}

# ===============================
# DATA LOADING & PROCESSING
# ===============================

def load_data():
    """โหลดข้อมูลจาก Supabase table: training_sla"""
    try:
        # ดึงข้อมูลจาก Supabase
        response = supabase.table('training_sla').select('*').execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            return df
        else:
            print("No data found in training_sla table")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading data from Supabase: {e}")
        # Fallback to CSV if Supabase fails
        try:
            df = pd.read_csv('sla.csv', encoding='utf-8')
            print("Fallback: Using sla.csv")
            return df
        except:
            return pd.DataFrame()

def process_data(df):
    """ประมวลผลข้อมูลเบื้องต้น"""
    if df.empty:
        return df
    
    # แปลงคอลัมน์ SLA เป็นตัวเลข (ไม่รวม sla_doc)
    sla_columns = ['sla_total', 'sla_training', 'sla_ojt', 
                   'sla_genid_card', 'sla_inspection', 'sla_dflow', 'sla_registration']
    
    for col in sla_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            # กรอง SLA ที่เป็นค่าลบมากๆ ออก (ข้อมูลผิดปกติ)
            df.loc[df[col] < -1000, col] = np.nan
    
    return df

# ===============================
# STATISTICS FUNCTIONS
# ===============================

def get_summary_stats(df):
    """สรุปสถิติภาพรวม"""
    if df.empty:
        return {
            'total': 0,
            'completed': 0,
            'onprocess': 0,
            'closed': 0,
            'completed_rate': 0,
            'closed_rate': 0,
            'theory_pass': 0,
            'theory_fail': 0,
            'theory_rate': 0,
            'ojt_pass': 0,
            'ojt_fail': 0,
            'ojt_rate': 0,
            'avg_sla_total': 0,
            'sla_by_step': {},
            'status_counts': {}
        }
    
    total = len(df)
    
    # นับจากคอลัมน์ result โดยตรง
    result_col = 'result'
    result_counts = df[result_col].value_counts().to_dict() if result_col in df.columns else {}
    
    # นับตาม result: Completed, Closed, Cancel, Onprocess
    completed = result_counts.get('Completed', 0)
    closed = result_counts.get('Closed', 0)
    cancel = result_counts.get('Cancel', 0)
    onprocess = result_counts.get('Onprocess', 0)
    
    # เก็บ status_counts สำหรับแสดงรายละเอียด
    status_col = 'status'
    status_counts = df[status_col].value_counts().to_dict() if status_col in df.columns else {}
    
    # ผลอบรมทฤษฎี
    theory_pass = len(df[df['result_round'] == 'ผ่าน']) if 'result_round' in df.columns else 0
    theory_fail = len(df[df['result_round'] == 'ไม่ผ่าน']) if 'result_round' in df.columns else 0
    
    # ผล OJT
    ojt_pass = len(df[df['result_round_ojt'] == 'ผ่าน']) if 'result_round_ojt' in df.columns else 0
    ojt_fail = len(df[df['result_round_ojt'] == 'ไม่ผ่าน']) if 'result_round_ojt' in df.columns else 0
    
    # SLA เฉลี่ยรวม (เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง)
    try:
        if 'sla_total' in df.columns and 'start_date' in df.columns and 'end_date' in df.columns:
            valid_sla_df = df[
                (df['sla_total'] >= 0) & 
                (df['sla_total'].notna()) & 
                (df['start_date'].notna()) & 
                (df['end_date'].notna())
            ]
            avg_sla_total = valid_sla_df['sla_total'].mean() if len(valid_sla_df) > 0 else 0
        else:
            avg_sla_total = 0
        if pd.isna(avg_sla_total):
            avg_sla_total = 0
    except:
        avg_sla_total = 0
    
    # SLA เฉลี่ยแต่ละขั้นตอน
    # เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง
    sla_by_step = {}
    for step in SLA_STEPS:
        try:
            sla_col = step['sla_col']
            start_col = step['start_col']
            end_col = step['end_col']
            
            if sla_col in df.columns and start_col in df.columns and end_col in df.columns:
                # รวมเฉพาะที่มี sla >= 0 และมี start/end date จริง (ไม่เป็น null)
                valid_df = df[
                    (df[sla_col] >= 0) & 
                    (df[sla_col].notna()) & 
                    (df[start_col].notna()) & 
                    (df[end_col].notna())
                ]
                valid_sla = valid_df[sla_col]
                sla_by_step[step['key']] = round(valid_sla.mean(), 1) if len(valid_sla) > 0 else 0
            else:
                sla_by_step[step['key']] = 0
        except:
            sla_by_step[step['key']] = 0
    
    return {
        'total': total,
        'completed': completed,
        'onprocess': onprocess,
        'closed': closed,
        'cancel': cancel,
        'completed_rate': round((completed / total * 100), 1) if total > 0 else 0,
        'onprocess_rate': round((onprocess / total * 100), 1) if total > 0 else 0,
        'closed_rate': round((closed / total * 100), 1) if total > 0 else 0,
        'cancel_rate': round((cancel / total * 100), 1) if total > 0 else 0,
        'theory_pass': theory_pass,
        'theory_fail': theory_fail,
        'theory_rate': round((theory_pass / (theory_pass + theory_fail) * 100), 1) if (theory_pass + theory_fail) > 0 else 0,
        'ojt_pass': ojt_pass,
        'ojt_fail': ojt_fail,
        'ojt_rate': round((ojt_pass / (ojt_pass + ojt_fail) * 100), 1) if (ojt_pass + ojt_fail) > 0 else 0,
        'avg_sla_total': round(float(avg_sla_total), 1) if avg_sla_total else 0,
        'sla_by_step': sla_by_step,
        'status_counts': status_counts
    }

def get_sla_by_step_stats(df):
    """สถิติ SLA แต่ละขั้นตอน
    เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง
    """
    if df.empty:
        return []
    
    step_stats = []
    for step in SLA_STEPS:
        sla_col = step['sla_col']
        status_col = step['status_col']
        start_col = step['start_col']
        end_col = step['end_col']
        
        if sla_col in df.columns and start_col in df.columns and end_col in df.columns:
            # รวมเฉพาะที่มี sla >= 0 และมี start/end date จริง (ไม่เป็น null)
            valid_df = df[
                (df[sla_col] >= 0) & 
                (df[sla_col].notna()) & 
                (df[start_col].notna()) & 
                (df[end_col].notna())
            ]
            total = len(valid_df)
            avg_sla = valid_df[sla_col].mean() if total > 0 else 0
            max_sla = valid_df[sla_col].max() if total > 0 else 0
            min_sla = valid_df[sla_col].min() if total > 0 else 0
            
            # นับ Complete จาก status_col = 'Complete'
            complete_count = 0
            if status_col in df.columns:
                complete_count = len(df[df[status_col] == 'Complete'])
            
            step_stats.append({
                'key': step['key'],
                'name': step['name'],
                'total': total,
                'complete': complete_count,
                'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
                'max_sla': int(max_sla) if not np.isnan(max_sla) else 0,
                'min_sla': int(min_sla) if not np.isnan(min_sla) else 0
            })
        else:
            # ถ้าไม่มี columns ให้ใส่ค่าเป็น 0
            step_stats.append({
                'key': step['key'],
                'name': step['name'],
                'total': 0,
                'complete': 0,
                'avg_sla': 0,
                'max_sla': 0,
                'min_sla': 0
            })
    
    return step_stats

def get_area_step_summary(df):
    """สรุปจำนวนช่างแยกตามพื้นที่และสถานะใหญ่ (result) พร้อม breakdown สถานะย่อย"""
    if df.empty or 'area' not in df.columns:
        return []
    
    import re
    from datetime import datetime
    
    # Mapping สถานะย่อย -> คอลัมน์ start/end สำหรับคำนวณ SLA
    STATUS_SLA_MAPPING = {
        'เอกสารยังไม่ครบ': {'start_col': 'doc_start', 'end_col': 'doc_end', 'remark_col': 'remark_doc'},
        'อยู่ระหว่างอบรม': {'start_col': 'training_start', 'end_col': 'training_end', 'remark_col': 'remark_training'},
        'OJT': {'start_col': 'ojt_start', 'end_col': 'ojt_end', 'remark_col': 'remark_ojt'},
        'Gen ID': {'start_col': 'genid_start', 'end_col': 'genid_end', 'remark_col': 'remark_genid_card'},
        'Print/ส่งบัตร': {'start_col': 'printcard_start', 'end_col': 'printcard_end', 'remark_col': 'remark_genid_card'},
        'รอตรวจกองงาน': {'start_col': 'inspection_start', 'end_col': 'inspection_end', 'remark_col': 'remark_inspection'},
        'พื้นที่ขออนุมัติ': {'start_col': 'dflow_start', 'end_col': 'dflow_end', 'remark_col': 'remark_dflow'},
        'ขอสิทธิ์เข้าใช้งาน': {'start_col': 'registration_start', 'end_col': 'registration_end', 'remark_col': 'remark_registration'}
    }
    
    # Helper function สำหรับคำนวณ SLA จาก start/end date
    def calculate_sla_days(start_date, end_date):
        """คำนวณจำนวนวันจาก start_date ถึง end_date"""
        if pd.isna(start_date) or pd.isna(end_date):
            return 0
        try:
            if isinstance(start_date, str):
                start = pd.to_datetime(start_date)
            else:
                start = start_date
            if isinstance(end_date, str):
                end = pd.to_datetime(end_date)
            else:
                end = end_date
            
            if pd.isna(start) or pd.isna(end):
                return 0
                
            days = (end - start).days
            return max(0, days)  # ไม่ให้ติดลบ
        except:
            return 0
    
    # Helper function สำหรับดึงข้อมูลช่าง พร้อมคำนวณ SLA ตามสถานะ
    def get_technician_details_with_status_sla(df_subset, status_name):
        details = []
        sla_mapping = STATUS_SLA_MAPPING.get(status_name, {})
        start_col = sla_mapping.get('start_col', '')
        end_col = sla_mapping.get('end_col', '')
        remark_col = sla_mapping.get('remark_col', '')
        
        for _, row in df_subset.iterrows():
            # ใช้ safe_str helper function เพื่อจัดการ None/NaN
            depot_code = str(row['depot_code']) if pd.notna(row.get('depot_code')) else ''
            depot_name = str(row['depot_name']) if pd.notna(row.get('depot_name')) else ''
            province = str(row['province']) if 'province' in row.index and pd.notna(row['province']) else ''
            full_name_th = str(row['full_name_th']) if pd.notna(row.get('full_name_th')) else ''
            status = str(row['status']) if pd.notna(row.get('status')) else ''
            
            # ดึง remark ตามสถานะย่อย
            remark = ''
            if remark_col and remark_col in row.index and pd.notna(row[remark_col]):
                remark = str(row[remark_col])
            
            # คำนวณ SLA ตามสถานะย่อย (end_col - start_col)
            sla_days = 0
            if start_col and end_col and start_col in row.index and end_col in row.index:
                start_date = row.get(start_col)
                end_date = row.get(end_col)
                # ถ้าไม่มี end_date ให้ใช้วันปัจจุบัน
                if pd.notna(start_date):
                    if pd.isna(end_date):
                        end_date = datetime.now()
                    sla_days = calculate_sla_days(start_date, end_date)
            
            details.append({
                'depot_code': depot_code,
                'depot_name': depot_name,
                'province': province,
                'full_name_th': full_name_th,
                'remark': remark,
                'status': status,
                'sla_total': sla_days
            })
        return details
    
    # Helper function สำหรับคำนวณ SLA เฉลี่ยของ subset ตามสถานะย่อย
    def calculate_avg_sla_by_status(df_subset, status_name):
        if df_subset.empty:
            return 0
        
        sla_mapping = STATUS_SLA_MAPPING.get(status_name, {})
        start_col = sla_mapping.get('start_col', '')
        end_col = sla_mapping.get('end_col', '')
        
        if not start_col or not end_col:
            return 0
        
        sla_values = []
        for _, row in df_subset.iterrows():
            if start_col in row.index and end_col in row.index:
                start_date = row.get(start_col)
                end_date = row.get(end_col)
                # ถ้าไม่มี end_date ให้ใช้วันปัจจุบัน
                if pd.notna(start_date):
                    if pd.isna(end_date):
                        end_date = datetime.now()
                    sla_days = calculate_sla_days(start_date, end_date)
                    if sla_days >= 0:
                        sla_values.append(sla_days)
        
        if len(sla_values) > 0:
            return round(sum(sla_values) / len(sla_values), 1)
        return 0
    
    # Helper function สำหรับดึงข้อมูลช่าง (สำหรับ Completed, Cancel, Closed - ใช้ sla_total)
    def get_technician_details(df_subset):
        details = []
        for _, row in df_subset.iterrows():
            depot_code = str(row['depot_code']) if pd.notna(row.get('depot_code')) else ''
            depot_name = str(row['depot_name']) if pd.notna(row.get('depot_name')) else ''
            province = str(row['province']) if 'province' in row.index and pd.notna(row['province']) else ''
            full_name_th = str(row['full_name_th']) if pd.notna(row.get('full_name_th')) else ''
            status = str(row['status']) if pd.notna(row.get('status')) else ''
            
            # SLA total - เฉพาะค่า >= 0
            sla_total = 0
            if 'sla_total' in row.index and pd.notna(row['sla_total']):
                try:
                    sla_val = float(row['sla_total'])
                    sla_total = int(sla_val) if sla_val >= 0 else 0
                except:
                    sla_total = 0
            
            details.append({
                'depot_code': depot_code,
                'depot_name': depot_name,
                'province': province,
                'full_name_th': full_name_th,
                'status': status,
                'sla_total': sla_total
            })
        return details
    
    # Helper function สำหรับคำนวณ SLA เฉลี่ยของ subset (สำหรับ Completed, Cancel, Closed)
    def calculate_avg_sla(df_subset):
        if df_subset.empty or 'sla_total' not in df_subset.columns:
            return 0
        valid_sla = df_subset[
            (df_subset['sla_total'] >= 0) & 
            (df_subset['sla_total'].notna())
        ]['sla_total']
        if len(valid_sla) > 0:
            return round(valid_sla.mean(), 1)
        return 0
    
    # Helper function สำหรับ breakdown สถานะย่อย (Completed, Cancel, Closed)
    def get_status_breakdown(df_subset):
        breakdown = []
        if 'status' in df_subset.columns and len(df_subset) > 0:
            status_counts = df_subset['status'].value_counts().to_dict()
            for status, count in status_counts.items():
                status_df = df_subset[df_subset['status'] == status]
                breakdown.append({
                    'status': status,
                    'count': count,
                    'avg_sla': calculate_avg_sla(status_df),
                    'details': get_technician_details(status_df)
                })
        return breakdown
    
    # Helper function สำหรับ breakdown สถานะย่อย Onprocess (คำนวณ SLA ตามขั้นตอน)
    def get_onprocess_status_breakdown(df_subset):
        breakdown = []
        if 'status' in df_subset.columns and len(df_subset) > 0:
            status_counts = df_subset['status'].value_counts().to_dict()
            for status, count in status_counts.items():
                status_df = df_subset[df_subset['status'] == status]
                breakdown.append({
                    'status': status,
                    'count': count,
                    'avg_sla': calculate_avg_sla_by_status(status_df, status),
                    'details': get_technician_details_with_status_sla(status_df, status)
                })
        return breakdown
    
    area_summary = []
    
    # กำหนดลำดับสถานะย่อยของ Onprocess ตามที่ต้องการ
    # ค่าเหล่านี้ต้องตรงกับค่าจริงในคอลัมน์ status ของฐานข้อมูล
    unique_onprocess_statuses = [
        'เอกสารยังไม่ครบ',
        'อยู่ระหว่างอบรม',
        'OJT',
        'Gen ID',
        'Print/ส่งบัตร',
        'รอตรวจกองงาน',
        'พื้นที่ขออนุมัติ',
        'ขอสิทธิ์เข้าใช้งาน'
    ]
    
    # สร้าง area_summary พร้อม data ที่จัดเรียงตาม unique statuses
    for area in df['area'].dropna().unique():
        area_df = df[df['area'] == area]
        
        # จำนวนช่างทั้งหมดที่ลงทะเบียน
        total = len(area_df)
        
        # นับจากคอลัมน์ result โดยตรง
        result_counts = area_df['result'].value_counts().to_dict() if 'result' in area_df.columns else {}
        
        # Completed
        completed_count = result_counts.get('Completed', 0)
        completed_df = area_df[area_df['result'] == 'Completed'] if 'result' in area_df.columns else pd.DataFrame()
        completed_breakdown = get_status_breakdown(completed_df)
        
        # Cancel
        cancel_count = result_counts.get('Cancel', 0)
        cancel_df = area_df[area_df['result'] == 'Cancel'] if 'result' in area_df.columns else pd.DataFrame()
        cancel_breakdown = get_status_breakdown(cancel_df)
        
        # Closed
        closed_count = result_counts.get('Closed', 0)
        closed_df = area_df[area_df['result'] == 'Closed'] if 'result' in area_df.columns else pd.DataFrame()
        closed_breakdown = get_status_breakdown(closed_df)
        
        # Onprocess - ใช้ get_onprocess_status_breakdown เพื่อคำนวณ SLA ตามสถานะย่อย
        onprocess_count = result_counts.get('Onprocess', 0)
        onprocess_df = area_df[area_df['result'] == 'Onprocess'] if 'result' in area_df.columns else pd.DataFrame()
        onprocess_breakdown = get_onprocess_status_breakdown(onprocess_df)
        
        # สร้าง onprocess_by_status dict
        onprocess_by_status = {}
        for sub in onprocess_breakdown:
            onprocess_by_status[sub['status']] = {
                'count': sub['count'],
                'avg_sla': sub['avg_sla'],
                'details': sub['details']
            }
        
        # สร้าง onprocess_columns list ที่เรียงตาม unique_onprocess_statuses
        onprocess_columns = []
        for status_name in unique_onprocess_statuses:
            if status_name in onprocess_by_status:
                onprocess_columns.append({
                    'status': status_name,
                    'count': onprocess_by_status[status_name]['count'],
                    'avg_sla': onprocess_by_status[status_name]['avg_sla'],
                    'details': onprocess_by_status[status_name]['details'],
                    'has_data': True
                })
            else:
                onprocess_columns.append({
                    'status': status_name,
                    'count': 0,
                    'avg_sla': 0,
                    'details': [],
                    'has_data': False
                })
        
        area_summary.append({
            'area': area,
            'total': total,
            'completed': completed_count,
            'completed_breakdown': completed_breakdown,
            'cancel': cancel_count,
            'cancel_breakdown': cancel_breakdown,
            'closed': closed_count,
            'closed_breakdown': closed_breakdown,
            'onprocess': onprocess_count,
            'onprocess_breakdown': onprocess_breakdown,
            'onprocess_columns': onprocess_columns,
            'unique_onprocess_statuses': unique_onprocess_statuses
        })
    
    # เรียงตามชื่อ area (RSM1, RSM2, RSM3...)
    def get_area_sort_key(item):
        match = re.search(r'RSM(\d+)', item.get('area', ''))
        if match:
            return int(match.group(1))
        return 999
    
    return sorted(area_summary, key=get_area_sort_key)

def get_area_stats(df):
    """สรุปสถิติตามพื้นที่ (area) - นับจากคอลัมน์ result"""
    if df.empty or 'area' not in df.columns:
        return []
    
    area_stats = []
    for area in df['area'].dropna().unique():
        area_df = df[df['area'] == area]
        
        # นับจากคอลัมน์ result โดยตรง
        result_counts = area_df['result'].value_counts().to_dict() if 'result' in area_df.columns else {}
        
        completed = result_counts.get('Completed', 0)
        closed = result_counts.get('Closed', 0)
        cancel = result_counts.get('Cancel', 0)
        onprocess = result_counts.get('Onprocess', 0)
        
        # คำนวณ avg_sla เฉพาะที่มี sla_total >= 0 และมี start/end date
        if 'sla_total' in area_df.columns and 'start_date' in area_df.columns and 'end_date' in area_df.columns:
            valid_sla_df = area_df[
                (area_df['sla_total'] >= 0) & 
                (area_df['sla_total'].notna()) & 
                (area_df['start_date'].notna()) & 
                (area_df['end_date'].notna())
            ]
            avg_sla = valid_sla_df['sla_total'].mean() if len(valid_sla_df) > 0 else 0
        else:
            avg_sla = 0
        
        area_stats.append({
            'area': area,
            'total': len(area_df),
            'completed': completed,
            'onprocess': onprocess,
            'closed': closed,
            'cancel': cancel,
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'success_rate': round((completed / len(area_df) * 100), 1) if len(area_df) > 0 else 0
        })
    
    # เรียงตามชื่อ area (RSM1, RSM2, RSM3...)
    # ดึงตัวเลขจากชื่อ area เช่น RSM3_UPC-East -> 3
    def get_area_sort_key(area):
        import re
        match = re.search(r'RSM(\d+)', area.get('area', ''))
        if match:
            return int(match.group(1))
        return 999  # ถ้าไม่มีตัวเลข ให้ไปท้ายสุด
    
    return sorted(area_stats, key=get_area_sort_key)

def get_province_stats(df):
    """สรุปสถิติตามจังหวัด - นับจำนวนลงทะเบียนและขึ้นทะเบียนเรียบร้อย"""
    if df.empty or 'province' not in df.columns:
        return []
    
    province_stats = []
    for province in df['province'].dropna().unique():
        prov_df = df[df['province'] == province]
        # นับขึ้นทะเบียนเรียบร้อย (ใช้ค่าภาษาไทย)
        completed = len(prov_df[prov_df['status'] == 'ขึ้นทะเบียนเรียบร้อย'])
        
        province_stats.append({
            'province': province.strip(),
            'total': len(prov_df),
            'completed': completed,
            'success_rate': round((completed / len(prov_df) * 100), 1) if len(prov_df) > 0 else 0
        })
    
    return sorted(province_stats, key=lambda x: x['total'], reverse=True)[:10]

def get_province_stats_all(df):
    """สรุปสถิติตามจังหวัด - ทุกจังหวัดสำหรับแผนที่"""
    if df.empty or 'province' not in df.columns:
        return []
    
    province_stats = []
    for province in df['province'].dropna().unique():
        prov_df = df[df['province'] == province]
        # นับสถานะทั้งภาษาไทยและอังกฤษ
        completed = len(prov_df[prov_df['status'].isin(['Completed', 'ขึ้นทะเบียนเรียบร้อย'])])
        onprocess = len(prov_df[prov_df['status'].isin(['Onprocess', 'อยู่ระหว่างดำเนินการ'])])
        
        province_stats.append({
            'province': province.strip(),
            'total': len(prov_df),
            'completed': completed,
            'onprocess': onprocess,
            'success_rate': round((completed / len(prov_df) * 100), 1) if len(prov_df) > 0 else 0
        })
    
    return sorted(province_stats, key=lambda x: x['total'], reverse=True)

def get_monthly_stats(df):
    """สรุปสถิติรายเดือน - นับจากคอลัมน์ result"""
    if df.empty or 'training_month' not in df.columns:
        return []
    
    monthly_stats = []
    for month in df['training_month'].dropna().unique():
        month_df = df[df['training_month'] == month]
        
        # นับจากคอลัมน์ result โดยตรง
        result_counts = month_df['result'].value_counts().to_dict() if 'result' in month_df.columns else {}
        
        completed = result_counts.get('Completed', 0)
        closed = result_counts.get('Closed', 0)
        cancel = result_counts.get('Cancel', 0)
        onprocess = result_counts.get('Onprocess', 0)
        
        monthly_stats.append({
            'month': month,
            'total': len(month_df),
            'completed': completed,
            'onprocess': onprocess,
            'closed': closed,
            'cancel': cancel
        })
    
    # เรียงตามลำดับเดือน
    month_order = ['Oct25', 'Nov25', 'Dec25', 'Jan26', 'Feb26']
    monthly_stats.sort(key=lambda x: month_order.index(x['month']) if x['month'] in month_order else 99)
    
    return monthly_stats

def get_trainer_stats(df):
    """สรุปสถิติตามผู้อบรม - นับจำนวนอบรมทั้งหมดและผ่านอบรม (result_round = 'ผ่าน')"""
    if df.empty or 'training_by' not in df.columns:
        return []
    
    trainer_stats = []
    for trainer in df['training_by'].dropna().unique():
        trainer_df = df[df['training_by'] == trainer]
        # นับผ่านอบรม (result_round = 'ผ่าน')
        passed = len(trainer_df[trainer_df['result_round'] == 'ผ่าน']) if 'result_round' in trainer_df.columns else 0
        
        trainer_stats.append({
            'trainer': trainer,
            'total': len(trainer_df),
            'passed': passed,
            'pass_rate': round((passed / len(trainer_df) * 100), 1) if len(trainer_df) > 0 else 0
        })
    
    return sorted(trainer_stats, key=lambda x: x['total'], reverse=True)[:10]

def get_monthly_area_stats(df):
    """สรุปสถิติรายเดือนแยกตามพื้นที่ - สำหรับกราฟ trend"""
    if df.empty or 'training_month' not in df.columns or 'area' not in df.columns:
        return []
    
    import re
    month_order = ['Oct25', 'Nov25', 'Dec25', 'Jan26', 'Feb26']
    
    # รวบรวมข้อมูลแต่ละพื้นที่
    area_monthly_data = []
    for area in df['area'].dropna().unique():
        area_df = df[df['area'] == area]
        
        monthly_data = []
        for month in month_order:
            month_df = area_df[area_df['training_month'] == month]
            
            # นับจากคอลัมน์ result
            result_counts = month_df['result'].value_counts().to_dict() if 'result' in month_df.columns else {}
            completed = result_counts.get('Completed', 0)
            
            monthly_data.append({
                'month': month,
                'total': len(month_df),
                'completed': completed
            })
        
        area_monthly_data.append({
            'area': area,
            'monthly': monthly_data
        })
    
    # เรียงตามชื่อ area (RSM1, RSM2, RSM3...)
    def get_area_sort_key(item):
        match = re.search(r'RSM(\d+)', item.get('area', ''))
        if match:
            return int(match.group(1))
        return 999
    
    return sorted(area_monthly_data, key=get_area_sort_key)

def get_depot_agent_stats(df):
    """สรุปสถิติตัวแทน (Depot) พร้อม area, จำนวนลงทะเบียน, สำเร็จ, และ %"""
    if df.empty or 'depot_name' not in df.columns:
        return []
    
    import re
    
    depot_stats = []
    for depot in df['depot_name'].dropna().unique():
        depot_df = df[df['depot_name'] == depot]
        total = len(depot_df)
        # นับขึ้นทะเบียนสำเร็จจาก result = 'Completed'
        completed = len(depot_df[depot_df['result'] == 'Completed']) if 'result' in depot_df.columns else 0
        success_rate = round((completed / total * 100), 1) if total > 0 else 0
        
        depot_stats.append({
            'area': depot_df['area'].iloc[0] if 'area' in depot_df.columns else '',
            'depot_code': depot_df['depot_code'].iloc[0] if 'depot_code' in depot_df.columns else '',
            'depot_name': depot,
            'province': depot_df['province'].iloc[0] if 'province' in depot_df.columns else '',
            'total': total,
            'completed': completed,
            'success_rate': success_rate
        })
    
    # เรียงตาม total จากมากไปน้อย
    return sorted(depot_stats, key=lambda x: x['total'], reverse=True)

def get_depot_stats(df):
    """สรุปสถิติตาม Depot
    เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง
    """
    if df.empty or 'depot_name' not in df.columns:
        return []
    
    depot_stats = []
    for depot in df['depot_name'].dropna().unique():
        depot_df = df[df['depot_name'] == depot]
        completed = len(depot_df[depot_df['status'] == 'Completed'])
        
        # คำนวณ avg_sla เฉพาะที่มี sla_total >= 0 และมี start/end date
        if 'sla_total' in depot_df.columns and 'start_date' in depot_df.columns and 'end_date' in depot_df.columns:
            valid_sla_df = depot_df[
                (depot_df['sla_total'] >= 0) & 
                (depot_df['sla_total'].notna()) & 
                (depot_df['start_date'].notna()) & 
                (depot_df['end_date'].notna())
            ]
            avg_sla = valid_sla_df['sla_total'].mean() if len(valid_sla_df) > 0 else 0
        else:
            avg_sla = 0
        
        depot_stats.append({
            'depot': depot,
            'code': depot_df['depot_code'].iloc[0] if 'depot_code' in depot_df.columns else '',
            'total': len(depot_df),
            'completed': completed,
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0
        })
    
    return sorted(depot_stats, key=lambda x: x['total'], reverse=True)[:20]

def get_status_detail_stats(df):
    """สรุปรายละเอียดสถานะ (result column)"""
    if df.empty or 'result' not in df.columns:
        return []
    
    result_counts = df['result'].value_counts()
    return [{'result': k, 'count': int(v)} for k, v in result_counts.items() if pd.notna(k) and k != '']

def get_sla_distribution(df):
    """การกระจายตัวของ SLA รวม
    เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง
    """
    if df.empty or 'sla_total' not in df.columns:
        return []
    
    bins = [0, 30, 45, 60, 90, float('inf')]
    labels = ['0-30 วัน', '31-45 วัน', '46-60 วัน', '61-90 วัน', '>90 วัน']
    
    # กรองเฉพาะที่มี sla_total >= 0 และมี start/end date
    if 'start_date' in df.columns and 'end_date' in df.columns:
        valid_df = df[
            (df['sla_total'] >= 0) & 
            (df['sla_total'].notna()) & 
            (df['start_date'].notna()) & 
            (df['end_date'].notna())
        ]
        sla_values = valid_df['sla_total']
    else:
        sla_values = df['sla_total'].dropna()
        sla_values = sla_values[sla_values >= 0]
    
    if len(sla_values) == 0:
        return []
    
    distribution = pd.cut(sla_values, bins=bins, labels=labels).value_counts()
    return [{'range': k, 'count': int(v)} for k, v in distribution.items()]

def get_bottleneck_analysis(df):
    """วิเคราะห์จุดคอขวด - ขั้นตอนไหนใช้เวลานานสุด
    เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง
    """
    if df.empty:
        return []
    
    bottleneck = []
    for step in SLA_STEPS:
        sla_col = step['sla_col']
        start_col = step['start_col']
        end_col = step['end_col']
        
        if sla_col in df.columns and start_col in df.columns and end_col in df.columns:
            # รวมเฉพาะที่มี sla >= 0 และมี start/end date จริง (ไม่เป็น null)
            valid_df = df[
                (df[sla_col] >= 0) & 
                (df[sla_col].notna()) & 
                (df[start_col].notna()) & 
                (df[end_col].notna())
            ]
            valid_sla = valid_df[sla_col]
            if len(valid_sla) > 0:
                avg_sla = valid_sla.mean()
                bottleneck.append({
                    'step': step['name'],
                    'key': step['key'],
                    'avg_days': round(avg_sla, 1)
                })
    
    return sorted(bottleneck, key=lambda x: x['avg_days'], reverse=True)

def safe_int(val, default=0):
    """แปลงค่าเป็น int อย่างปลอดภัย"""
    try:
        if val is None or pd.isna(val):
            return default
        return int(float(val)) if float(val) >= 0 else default
    except:
        return default

def safe_str(val, default=''):
    """แปลงค่าเป็น string อย่างปลอดภัย"""
    try:
        if val is None or pd.isna(val):
            return default
        return str(val).strip()
    except:
        return default

def get_technician_list(df, status_filter=None, area_filter=None, province_filter=None, depot_code_filter=None, depot_name_filter=None, limit=None):
    """รายชื่อช่างพร้อมข้อมูล"""
    if df.empty:
        return []
    
    filtered_df = df.copy()
    
    # สถานะย่อยของ Onprocess (ต้องตรงกับค่าในฐานข้อมูล)
    onprocess_sub_statuses = [
        'เอกสารยังไม่ครบ',
        'อยู่ระหว่างอบรม',
        'OJT',
        'Gen ID',
        'Print/ส่งบัตร',
        'รอตรวจกองงาน',
        'พื้นที่ขออนุมัติ',
        'ขอสิทธิ์เข้าใช้งาน'
    ]
    
    if status_filter and status_filter != 'all':
        if status_filter == 'Completed':
            # กรองจาก result column
            filtered_df = filtered_df[filtered_df['result'] == 'Completed']
        elif status_filter == 'Onprocess':
            filtered_df = filtered_df[filtered_df['result'] == 'Onprocess']
        elif status_filter == 'Closed':
            filtered_df = filtered_df[filtered_df['result'] == 'Closed']
        elif status_filter == 'Cancel':
            filtered_df = filtered_df[filtered_df['result'] == 'Cancel']
        elif status_filter in onprocess_sub_statuses:
            # กรองตามสถานะย่อย (status column)
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
        else:
            # กรองตรงๆ จาก status column
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
    
    if area_filter and area_filter != 'all':
        filtered_df = filtered_df[filtered_df['area'] == area_filter]
    
    if province_filter and province_filter != 'all':
        filtered_df = filtered_df[filtered_df['province'] == province_filter]
    
    # กรองตาม depot_code (ค้นหาแบบ contains, case-insensitive)
    if depot_code_filter and depot_code_filter.strip():
        filtered_df = filtered_df[filtered_df['depot_code'].astype(str).str.lower().str.contains(depot_code_filter.lower(), na=False)]
    
    # กรองตาม depot_name (ค้นหาแบบ contains, case-insensitive)
    if depot_name_filter and depot_name_filter.strip():
        filtered_df = filtered_df[filtered_df['depot_name'].astype(str).str.lower().str.contains(depot_name_filter.lower(), na=False)]
    
    # ถ้าไม่กำหนด limit ให้ดึงทั้งหมด
    if limit:
        data_df = filtered_df.head(limit)
    else:
        data_df = filtered_df
    
    technicians = []
    for _, row in data_df.iterrows():
        technicians.append({
            'no': safe_str(row.get('no')),
            'name': safe_str(row.get('full_name_th')),
            'name_en': f"{safe_str(row.get('first_name_en'))} {safe_str(row.get('last_name_en'))}".strip(),
            'depot': safe_str(row.get('depot_name')),
            'depot_code': safe_str(row.get('depot_code')),
            'province': safe_str(row.get('province')),
            'area': safe_str(row.get('area')),
            'education': safe_str(row.get('education')),
            'workgroup': safe_str(row.get('workgroup_status')),
            'theory_result': safe_str(row.get('result_round')),
            'ojt_result': safe_str(row.get('result_round_ojt')),
            'status': safe_str(row.get('status')),
            'result': safe_str(row.get('result')),
            'sla_total': safe_int(row.get('sla_total')),
            'training_month': safe_str(row.get('training_month')),
            'training_round': safe_str(row.get('training_round_date')),
            'trainer': safe_str(row.get('training_by')),
            # SLA แต่ละขั้นตอน
            'sla_training': safe_int(row.get('sla_training')),
            'sla_ojt': safe_int(row.get('sla_ojt')),
            'sla_doc': safe_int(row.get('sla_doc')),
            'sla_genid': safe_int(row.get('sla_genid_card')),
            'sla_inspection': safe_int(row.get('sla_inspection')),
            'sla_dflow': safe_int(row.get('sla_dflow')),
            'sla_registration': safe_int(row.get('sla_registration'))
        })
    
    return technicians

def get_pending_technicians(df):
    """รายชื่อช่างที่อยู่ระหว่างดำเนินการ (Onprocess)
    ใช้เงื่อนไข SLA แบบใหม่: sla >= 0 ที่มี start/end date จริง
    """
    if df.empty:
        return []
    
    # Status ที่ถือว่าอยู่ระหว่างดำเนินการ
    onprocess_statuses = [
        'ตัวแทนยังไม่ส่งขึ้นทะเบียน', 'เอกสารยังไม่ครบ',
        'อยู่ระหว่างอบรมทฤษฎี/ปฏิบัติ', 'อยู่ระหว่างOJT/สอบประเมินความพร้อม',
        'ส่ง Gen ID', 'Print/ส่งบัตร',
        'อยู่ระหว่างตรวจกองงาน', 'อยู่ระหว่างขอ User',
        'อยู่ระหว่างขออนุมัติDflow ขึ้นทะเบียนช่าง'
    ]
    
    # กรอง status อยู่ระหว่างดำเนินการ
    pending_df = df[df['status'].isin(onprocess_statuses)].copy()
    
    # เรียงลำดับตาม sla_total มากที่สุดก่อน (เฉพาะที่มีค่า >= 0)
    # ถ้า sla_total เป็น NaN หรือ < 0 ให้ไปท้ายสุด
    pending_df['sla_sort'] = pending_df['sla_total'].apply(lambda x: x if pd.notna(x) and x >= 0 else -9999)
    pending_df = pending_df.sort_values('sla_sort', ascending=False)
    pending_df = pending_df.drop(columns=['sla_sort'])
    
    # ส่งคืนทั้งหมด ไม่จำกัด limit
    return get_technician_list(pending_df)

# ===============================
# ROUTES
# ===============================

@app.route('/')
def dashboard():
    """หน้า Dashboard หลัก"""
    df = load_data()
    df = process_data(df)
    
    summary = get_summary_stats(df)
    
    # ตรวจสอบให้แน่ใจว่ามี key ที่จำเป็น
    default_summary = {
        'total': 0, 'completed': 0, 'onprocess': 0, 'closed': 0, 'cancel': 0,
        'completed_rate': 0, 'onprocess_rate': 0, 'closed_rate': 0, 'cancel_rate': 0,
        'theory_pass': 0, 'theory_fail': 0, 'theory_rate': 0,
        'ojt_pass': 0, 'ojt_fail': 0, 'ojt_rate': 0,
        'avg_sla_total': 0, 'sla_by_step': {}, 'status_counts': {}
    }
    for key, val in default_summary.items():
        if key not in summary:
            summary[key] = val
    
    sla_steps = get_sla_by_step_stats(df)
    areas = get_area_stats(df)
    area_step_summary = get_area_step_summary(df)
    provinces = get_province_stats(df)
    monthly = get_monthly_stats(df)
    monthly_area = get_monthly_area_stats(df)
    trainers = get_trainer_stats(df)
    status_detail = get_status_detail_stats(df)
    sla_dist = get_sla_distribution(df)
    bottleneck = get_bottleneck_analysis(df)
    depot_agents = get_depot_agent_stats(df)
    
    # รายชื่อสำหรับ filter
    area_list = df['area'].dropna().unique().tolist() if 'area' in df.columns else []
    province_list = df['province'].dropna().unique().tolist() if 'province' in df.columns else []
    province_list = [str(p).strip() for p in province_list if pd.notna(p)]
    
    return render_template('dashboard.html',
                         summary=summary,
                         sla_steps=sla_steps,
                         areas=areas,
                         area_step_summary=area_step_summary,
                         provinces=provinces,
                         monthly=monthly,
                         monthly_area=monthly_area,
                         trainers=trainers,
                         status_detail=status_detail,
                         sla_dist=sla_dist,
                         bottleneck=bottleneck,
                         depot_agents=depot_agents,
                         area_list=sorted(area_list),
                         province_list=sorted(set(province_list)),
                         active_page='dashboard')

@app.route('/technicians')
def technicians_page():
    """หน้ารายชื่อช่าง"""
    df = load_data()
    df = process_data(df)
    
    area_list = df['area'].dropna().unique().tolist() if 'area' in df.columns else []
    province_list = df['province'].dropna().unique().tolist() if 'province' in df.columns else []
    province_list = [str(p).strip() for p in province_list if pd.notna(p)]
    
    return render_template('technicians.html', 
                          area_list=sorted(area_list),
                          province_list=sorted(set(province_list)),
                          active_page='technicians')

@app.route('/sla-analysis')
def sla_analysis_page():
    """หน้าวิเคราะห์ SLA แต่ละขั้นตอน"""
    df = load_data()
    df = process_data(df)
    
    sla_steps = get_sla_by_step_stats(df)
    bottleneck = get_bottleneck_analysis(df)
    sla_dist = get_sla_distribution(df)
    
    return render_template('sla_analysis.html',
                          sla_steps=sla_steps,
                          bottleneck=bottleneck,
                          sla_dist=sla_dist,
                          active_page='sla_analysis')

@app.route('/pending')
def pending_page():
    """หน้าช่างที่รอดำเนินการ"""
    df = load_data()
    df = process_data(df)
    
    pending = get_pending_technicians(df)
    
    return render_template('pending.html',
                          pending=pending,
                          active_page='pending')

@app.route('/thailand-map')
def thailand_map_page():
    """หน้าแผนที่ประเทศไทย - แสดงข้อมูลการอบรมรายจังหวัด"""
    return render_template('thailand_map.html',
                          active_page='thailand_map')

# ===============================
# API ROUTES
# ===============================

@app.route('/api/summary')
def api_summary():
    """API: สรุปข้อมูลภาพรวม"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_summary_stats(df))

@app.route('/api/areas')
def api_areas():
    """API: ข้อมูลตามพื้นที่"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_area_stats(df))

@app.route('/api/provinces')
def api_provinces():
    """API: ข้อมูลตามจังหวัด"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_province_stats(df))

@app.route('/api/provinces-map')
def api_provinces_map():
    """API: ข้อมูลตามจังหวัดสำหรับแผนที่ (ทุกจังหวัด)"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_province_stats_all(df))

@app.route('/api/monthly')
def api_monthly():
    """API: ข้อมูลรายเดือน"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_monthly_stats(df))

@app.route('/api/sla-steps')
def api_sla_steps():
    """API: SLA แต่ละขั้นตอน"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_sla_by_step_stats(df))

@app.route('/api/technicians')
def api_technicians():
    """API: รายชื่อช่าง"""
    df = load_data()
    df = process_data(df)
    
    status_filter = request.args.get('status', 'all')
    area_filter = request.args.get('area', 'all')
    province_filter = request.args.get('province', 'all')
    depot_code_filter = request.args.get('depot_code', '')
    depot_name_filter = request.args.get('depot_name', '')
    
    return jsonify(get_technician_list(df, status_filter, area_filter, province_filter, depot_code_filter, depot_name_filter))

@app.route('/api/pending')
def api_pending():
    """API: ช่างที่รอดำเนินการ"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_pending_technicians(df))

@app.route('/api/bottleneck')
def api_bottleneck():
    """API: วิเคราะห์จุดคอขวด"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_bottleneck_analysis(df))

@app.route('/api/depots')
def api_depots():
    """API: ข้อมูลตาม Depot"""
    df = load_data()
    df = process_data(df)
    return jsonify(get_depot_stats(df))

# ===============================
# RUN APP
# ===============================

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)
