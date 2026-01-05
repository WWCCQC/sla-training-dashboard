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

# SLA Steps - 6 ขั้นตอนหลัก (ไม่รวมเอกสาร)
# เพิ่ม start_col และ end_col สำหรับตรวจสอบว่ามีการดำเนินการจริง
SLA_STEPS = [
    {'key': 'training', 'name': 'อบรม', 'sla_col': 'sla_training', 'status_col': 'status_result_round', 'result_col': 'result_round', 'start_col': 'training_start', 'end_col': 'training_end'},
    {'key': 'ojt', 'name': 'OJT', 'sla_col': 'sla_ojt', 'status_col': 'status_result_ojt', 'result_col': 'result_round_ojt', 'start_col': 'ojt_start', 'end_col': 'ojt_end'},
    {'key': 'genid', 'name': 'ทำบัตร', 'sla_col': 'sla_genid_card', 'status_col': 'status_genid_card_card', 'result_col': 'result_genid_card_card', 'start_col': 'genid_card_start', 'end_col': 'genid_card_end'},
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
    
    # นับสถานะหลัก (status) - ใช้ค่าภาษาไทยตามข้อมูลจริง
    status_col = 'status'
    status_counts = df[status_col].value_counts().to_dict() if status_col in df.columns else {}
    
    completed = status_counts.get('ขึ้นทะเบียนเรียบร้อย', 0)
    
    # Status ที่ปิดงาน/ไม่ผ่าน
    closed_statuses = ['ไม่ผ่านคุณสมบัติ', 'ไม่ผ่านอบรม', 'ไม่เข้าอบรม', 'ช่างลาออก']
    closed = sum(status_counts.get(s, 0) for s in closed_statuses)
    
    # เพิ่ม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result = "Closed" เข้า closed
    if 'status' in df.columns and 'result' in df.columns:
        closed += len(df[(df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (df['result'] == 'Closed')])
    
    # Status ที่อยู่ระหว่างดำเนินการ (ไม่รวม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result=Closed)
    onprocess_statuses = ['OJT', 'อบรม', 'ขออนุมัติDflow ขึ้นทะเบียนช่าง', 'Genid/ปริ้นบัตร/ส่งบัตร', 'ขอ User', 'ขึ้นทะเบียน']
    onprocess = sum(status_counts.get(s, 0) for s in onprocess_statuses)
    
    # เพิ่ม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result != "Closed" เข้า onprocess
    if 'status' in df.columns and 'result' in df.columns:
        onprocess += len(df[(df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (df['result'] != 'Closed')])
    
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
        'completed_rate': round((completed / total * 100), 1) if total > 0 else 0,
        'onprocess_rate': round((onprocess / total * 100), 1) if total > 0 else 0,
        'closed_rate': round((closed / total * 100), 1) if total > 0 else 0,
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
            
            # นับ Complete
            complete_count = 0
            result_col = step.get('result_col', '')
            
            # DFlow: นับจาก result_dflow = 'Approve' หรือ 'Reject' หรือ 'Resend'
            if step['key'] == 'dflow' and 'result_dflow' in df.columns:
                complete_count = len(df[df['result_dflow'].isin(['Approve', 'Reject', 'Resend'])])
            elif status_col in df.columns:
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
    
    return step_stats

def get_area_step_summary(df):
    """สรุปจำนวนช่างและ SLA เฉลี่ยแยกตามพื้นที่และขั้นตอน"""
    if df.empty or 'area' not in df.columns:
        return []
    
    import re
    
    # Status ที่ปิดงาน/ไม่ผ่าน
    closed_statuses = ['ไม่ผ่านคุณสมบัติ', 'ไม่ผ่านอบรม', 'ไม่เข้าอบรม', 'ช่างลาออก']
    
    area_summary = []
    
    for area in df['area'].dropna().unique():
        area_df = df[df['area'] == area]
        
        # จำนวนช่างทั้งหมดที่ลงทะเบียน
        total = len(area_df)
        
        # จำนวน Closed (รวม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result = "Closed")
        closed = len(area_df[area_df['status'].isin(closed_statuses)])
        if 'result' in area_df.columns:
            closed += len(area_df[(area_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (area_df['result'] == 'Closed')])
        
        # Helper function สำหรับดึงข้อมูลช่าง
        def get_technician_details(df_subset):
            details = []
            for _, row in df_subset.iterrows():
                details.append({
                    'depot_code': str(row.get('depot_code', '')),
                    'depot_name': str(row.get('depot_name', '')),
                    'full_name_th': str(row.get('full_name_th', ''))
                })
            return details
        
        # คำนวณแต่ละขั้นตอน
        steps_data = {}
        
        # 1. อบรม - นับจาก status_result_round = 'Onprocess'
        if 'status_result_round' in area_df.columns:
            training_df = area_df[area_df['status_result_round'] == 'Onprocess']
            training_count = len(training_df)
        else:
            training_count = 0
            training_df = pd.DataFrame()
        if 'sla_training' in training_df.columns and len(training_df) > 0:
            valid = training_df[training_df['sla_training'].notna() & (training_df['sla_training'] >= 0)]
            avg_sla = valid['sla_training'].mean() if len(valid) > 0 else 0
        else:
            avg_sla = 0
        steps_data['training'] = {
            'count': training_count, 
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'details': get_technician_details(training_df) if len(training_df) > 0 else []
        }
        
        # 2. OJT - นับจาก status_result_ojt = 'Onprocess'
        if 'status_result_ojt' in area_df.columns:
            ojt_df = area_df[area_df['status_result_ojt'] == 'Onprocess']
            ojt_count = len(ojt_df)
        else:
            ojt_count = 0
            ojt_df = pd.DataFrame()
        if 'sla_ojt' in ojt_df.columns and len(ojt_df) > 0:
            valid = ojt_df[ojt_df['sla_ojt'].notna() & (ojt_df['sla_ojt'] >= 0)]
            avg_sla = valid['sla_ojt'].mean() if len(valid) > 0 else 0
        else:
            avg_sla = 0
        steps_data['ojt'] = {
            'count': ojt_count, 
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'details': get_technician_details(ojt_df) if len(ojt_df) > 0 else []
        }
        
        # 3. ทำบัตร - นับจาก status_genid_card_card = 'Onprocess'
        if 'status_genid_card_card' in area_df.columns:
            genid_df = area_df[area_df['status_genid_card_card'] == 'Onprocess']
            genid_count = len(genid_df)
        else:
            genid_count = 0
            genid_df = pd.DataFrame()
        if 'sla_genid_card' in genid_df.columns and len(genid_df) > 0:
            valid = genid_df[genid_df['sla_genid_card'].notna() & (genid_df['sla_genid_card'] >= 0)]
            avg_sla = valid['sla_genid_card'].mean() if len(valid) > 0 else 0
        else:
            avg_sla = 0
        steps_data['genid'] = {
            'count': genid_count, 
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'details': get_technician_details(genid_df) if len(genid_df) > 0 else []
        }
        
        # 4. ตรวจความพร้อม - นับจาก status_inspection = 'Onprocess'
        if 'status_inspection' in area_df.columns:
            inspection_df = area_df[area_df['status_inspection'] == 'Onprocess']
            inspection_count = len(inspection_df)
        else:
            inspection_count = 0
            inspection_df = pd.DataFrame()
        if 'sla_inspection' in inspection_df.columns and len(inspection_df) > 0:
            valid = inspection_df[inspection_df['sla_inspection'].notna() & (inspection_df['sla_inspection'] >= 0)]
            avg_sla = valid['sla_inspection'].mean() if len(valid) > 0 else 0
        else:
            avg_sla = 0
        steps_data['inspection'] = {
            'count': inspection_count, 
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'details': get_technician_details(inspection_df) if len(inspection_df) > 0 else []
        }
        
        # 5. DFlow - นับจาก result_dflow = 'Onprocess'
        if 'result_dflow' in area_df.columns:
            dflow_df = area_df[area_df['result_dflow'] == 'Onprocess']
            dflow_count = len(dflow_df)
        else:
            dflow_count = 0
            dflow_df = pd.DataFrame()
        if 'sla_dflow' in dflow_df.columns and len(dflow_df) > 0:
            valid = dflow_df[dflow_df['sla_dflow'].notna() & (dflow_df['sla_dflow'] >= 0)]
            avg_sla = valid['sla_dflow'].mean() if len(valid) > 0 else 0
        else:
            avg_sla = 0
        steps_data['dflow'] = {
            'count': dflow_count, 
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'details': get_technician_details(dflow_df) if len(dflow_df) > 0 else []
        }
        
        # 6. ขึ้นทะเบียน - นับจาก status_registration = 'Onprocess'
        if 'status_registration' in area_df.columns:
            reg_df = area_df[area_df['status_registration'] == 'Onprocess']
            reg_count = len(reg_df)
        else:
            reg_count = 0
            reg_df = pd.DataFrame()
        if 'sla_registration' in reg_df.columns and len(reg_df) > 0:
            valid = reg_df[reg_df['sla_registration'].notna() & (reg_df['sla_registration'] >= 0)]
            avg_sla = valid['sla_registration'].mean() if len(valid) > 0 else 0
        else:
            avg_sla = 0
        steps_data['registration'] = {
            'count': reg_count, 
            'avg_sla': round(avg_sla, 1) if not np.isnan(avg_sla) else 0,
            'details': get_technician_details(reg_df) if len(reg_df) > 0 else []
        }
        
        # 7. เสร็จสิ้น (ขึ้นทะเบียนเรียบร้อย)
        completed = len(area_df[area_df['status'] == 'ขึ้นทะเบียนเรียบร้อย'])
        
        # คำนวณ onprocess = รวมทุก step ที่ยังไม่เสร็จ
        onprocess = (steps_data['training']['count'] + steps_data['ojt']['count'] + 
                     steps_data['genid']['count'] + steps_data['inspection']['count'] + 
                     steps_data['dflow']['count'] + steps_data['registration']['count'])
        
        area_summary.append({
            'area': area,
            'total': total,
            'closed': closed,
            'onprocess': onprocess,
            'completed': completed,
            'steps': steps_data
        })
    
    # เรียงตามชื่อ area (RSM1, RSM2, RSM3...)
    def get_area_sort_key(item):
        match = re.search(r'RSM(\d+)', item.get('area', ''))
        if match:
            return int(match.group(1))
        return 999
    
    return sorted(area_summary, key=get_area_sort_key)

def get_area_stats(df):
    """สรุปสถิติตามพื้นที่ (area)
    เงื่อนไขใหม่: รวมค่า >= 0 ที่มี start_date และ end_date จริง
    พร้อม breakdown ของ onprocess และ closed status
    """
    if df.empty or 'area' not in df.columns:
        return []
    
    # Status ที่ปิดงาน/ไม่ผ่าน
    closed_statuses = ['ไม่ผ่านคุณสมบัติ', 'ไม่ผ่านอบรม', 'ไม่เข้าอบรม', 'ช่างลาออก']
    # Status ที่อยู่ระหว่างดำเนินการ
    onprocess_statuses = ['OJT', 'อบรม', 'ขออนุมัติDflow ขึ้นทะเบียนช่าง', 'Genid/ปริ้นบัตร/ส่งบัตร', 'ขอ User', 'ตัวแทนยังไม่ส่งขึ้นทะเบียน', 'ขึ้นทะเบียน']
    
    area_stats = []
    for area in df['area'].dropna().unique():
        area_df = df[df['area'] == area]
        
        # นับ completed
        completed = len(area_df[area_df['status'] == 'ขึ้นทะเบียนเรียบร้อย'])
        
        # นับ closed พร้อม breakdown (รวม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result = "Closed")
        closed = 0
        closed_breakdown = []
        for s in closed_statuses:
            count = len(area_df[area_df['status'] == s])
            if count > 0:
                closed += count
                closed_breakdown.append({'status': s, 'count': count})
        
        # เพิ่ม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result = "Closed"
        if 'result' in area_df.columns:
            agent_closed = len(area_df[(area_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (area_df['result'] == 'Closed')])
            if agent_closed > 0:
                closed += agent_closed
                closed_breakdown.append({'status': 'ตัวแทนยังไม่ส่งขึ้นทะเบียน (Closed)', 'count': agent_closed})
        
        # นับ onprocess พร้อม breakdown (ไม่รวม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result = "Closed")
        onprocess = 0
        onprocess_breakdown = []
        for s in onprocess_statuses:
            if s == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน':
                continue
            count = len(area_df[area_df['status'] == s])
            if count > 0:
                onprocess += count
                onprocess_breakdown.append({'status': s, 'count': count})
        
        # เพิ่ม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result != "Closed"
        if 'result' in area_df.columns:
            agent_onprocess = len(area_df[(area_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (area_df['result'] != 'Closed')])
            if agent_onprocess > 0:
                onprocess += agent_onprocess
                onprocess_breakdown.append({'status': 'ตัวแทนยังไม่ส่งขึ้นทะเบียน', 'count': agent_onprocess})
        
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
            'onprocess_breakdown': onprocess_breakdown,
            'closed': closed,
            'closed_breakdown': closed_breakdown,
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
    """สรุปสถิติรายเดือน"""
    if df.empty or 'training_month' not in df.columns:
        return []
    
    monthly_stats = []
    for month in df['training_month'].dropna().unique():
        month_df = df[df['training_month'] == month]
        
        # ขึ้นทะเบียนเรียบร้อย
        completed = len(month_df[month_df['status'] == 'ขึ้นทะเบียนเรียบร้อย'])
        
        # ปิดงาน/ไม่ผ่าน
        closed_statuses = ['ไม่ผ่านคุณสมบัติ', 'ไม่ผ่านอบรม', 'ไม่เข้าอบรม', 'ช่างลาออก']
        closed = len(month_df[month_df['status'].isin(closed_statuses)])
        # เพิ่ม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result = 'Closed'
        if 'result' in month_df.columns:
            closed += len(month_df[(month_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (month_df['result'] == 'Closed')])
        
        # อยู่ระหว่างดำเนินการ
        onprocess_statuses = ['OJT', 'อบรม', 'ขออนุมัติDflow ขึ้นทะเบียนช่าง', 'Genid/ปริ้นบัตร/ส่งบัตร', 'ขอ User', 'ขึ้นทะเบียน']
        onprocess = len(month_df[month_df['status'].isin(onprocess_statuses)])
        # เพิ่ม "ตัวแทนยังไม่ส่งขึ้นทะเบียน" ที่ result != 'Closed'
        if 'result' in month_df.columns:
            onprocess += len(month_df[(month_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (month_df['result'] != 'Closed')])
        
        monthly_stats.append({
            'month': month,
            'total': len(month_df),
            'completed': completed,
            'onprocess': onprocess,
            'closed': closed
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
    
    # Status ที่ถือว่า Completed
    completed_statuses = ['ขึ้นทะเบียนเรียบร้อย']
    # Status ที่ถือว่า Onprocess
    onprocess_statuses = ['อบรม', 'OJT', 'ขออนุมัติDflow ขึ้นทะเบียนช่าง', 'ขอ User', 'Genid/ปริ้นบัตร/ส่งบัตร', 'ขึ้นทะเบียน']
    # Status ที่ถือว่า Closed
    closed_statuses = ['ช่างลาออก', 'ไม่ผ่านคุณสมบัติ', 'ไม่เข้าอบรม', 'ไม่ผ่านอบรม']
    
    if status_filter and status_filter != 'all':
        if status_filter == 'Completed':
            filtered_df = filtered_df[filtered_df['status'].isin(completed_statuses)]
        elif status_filter == 'Onprocess':
            # Onprocess = status ใน onprocess_statuses หรือ (ตัวแทนยังไม่ส่งขึ้นทะเบียน และ result != Closed)
            mask_onprocess = filtered_df['status'].isin(onprocess_statuses)
            mask_agent_onprocess = (filtered_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (filtered_df['result'] != 'Closed')
            filtered_df = filtered_df[mask_onprocess | mask_agent_onprocess]
        elif status_filter == 'Closed':
            # Closed = status ใน closed_statuses หรือ (ตัวแทนยังไม่ส่งขึ้นทะเบียน และ result = Closed)
            mask_closed = filtered_df['status'].isin(closed_statuses)
            mask_agent_closed = (filtered_df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (filtered_df['result'] == 'Closed')
            filtered_df = filtered_df[mask_closed | mask_agent_closed]
        else:
            # กรองตรงๆ
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
    onprocess_statuses = ['OJT', 'อบรม', 'ขออนุมัติDflow ขึ้นทะเบียนช่าง', 'Genid/ปริ้นบัตร/ส่งบัตร', 'ขอ User', 'ขึ้นทะเบียน']
    
    # กรอง status อยู่ระหว่างดำเนินการ หรือ (ตัวแทนยังไม่ส่งขึ้นทะเบียน และ result != Closed)
    pending_df = df[
        (df['status'].isin(onprocess_statuses)) | 
        ((df['status'] == 'ตัวแทนยังไม่ส่งขึ้นทะเบียน') & (df['result'] != 'Closed'))
    ].copy()
    
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
        'total': 0, 'completed': 0, 'onprocess': 0, 'closed': 0,
        'completed_rate': 0, 'onprocess_rate': 0, 'closed_rate': 0,
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
    trainers = get_trainer_stats(df)
    status_detail = get_status_detail_stats(df)
    sla_dist = get_sla_distribution(df)
    bottleneck = get_bottleneck_analysis(df)
    
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
                         trainers=trainers,
                         status_detail=status_detail,
                         sla_dist=sla_dist,
                         bottleneck=bottleneck,
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
