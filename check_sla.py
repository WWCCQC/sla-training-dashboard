import sys
sys.path.insert(0, '.')

# รีโหลด app module เพื่อให้ได้โค้ดใหม่
import importlib
import app
importlib.reload(app)

from app import load_data, process_data, get_area_step_summary

# โหลดข้อมูล
df = load_data()
df = process_data(df)

# เรียก get_area_step_summary
area_step_summary = get_area_step_summary(df)

# หา RSM3_UPC-East (ดูจากภาพ)
for area_data in area_step_summary:
    if 'RSM3' in area_data['area'] or 'RSM7' in area_data['area']:
        print(f"=== Area: {area_data['area']} ===")
        
        # ดู onprocess_columns - เฉพาะ พื้นที่ขออนุมัติ
        for col in area_data['onprocess_columns']:
            if col['status'] == 'พื้นที่ขออนุมัติ' and col['count'] > 0:
                print(f"สถานะ: {col['status']}")
                print(f"  count: {col['count']}")
                print(f"  avg_sla: {col['avg_sla']}")
                for tech in col['details']:
                    print(f"    - {tech['full_name_th']}: SLA = {tech['sla_total']} วัน")
                print()
