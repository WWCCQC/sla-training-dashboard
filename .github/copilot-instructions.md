# SLA Training Dashboard - AI Coding Instructions

## Project Overview
Flask-based dashboard tracking technician registration SLA (Service Level Agreement) through 8 process steps: Document → Training → OJT → GenID → PrintCard → Inspection → DFlow → Registration. Data stored in Supabase, deployed on Vercel.

## Architecture

### Data Flow
1. **Supabase** (`training_sla` table) → `load_data()` → **Pandas DataFrame** → processing functions → **Jinja2 templates**
2. Fallback: CSV file (`sla.csv`) if Supabase connection fails

### Key Files
- [app.py](../app.py) - Main Flask application with all routes and data processing
- [create_training_sla_table.sql](../create_training_sla_table.sql) - Database schema reference
- [templates/layout.html](../templates/layout.html) - Base template with Tailwind CSS, Chart.js, sidebar navigation

## Critical Patterns

### SLA Step Configuration (lines 35-48 in app.py)
Each SLA step requires 6 columns defined in `SLA_STEPS`:
```python
{'key': 'training', 'name': 'อบรมทฤษฎี', 'sla_col': 'sla_training', 
 'status_col': 'status_result_round', 'result_col': 'result_round', 
 'start_col': 'training_start', 'end_col': 'training_end'}
```
When adding new SLA steps, update this configuration with all 6 column mappings.

### SLA Calculation Rules
**Always filter SLA values with these conditions:**
```python
valid_df = df[
    (df[sla_col] >= 0) & 
    (df[sla_col].notna()) & 
    (df[start_col].notna()) & 
    (df[end_col].notna())
]
```
This ensures only completed steps with valid dates are included in SLA metrics.

### Status Hierarchy
The `result` column contains 4 main statuses: `Completed`, `Onprocess`, `Closed`, `Cancel`  
The `status` column contains detailed sub-statuses (Thai language) mapped to result statuses:
- **Completed**: `ขึ้นทะเบียนเรียบร้อย`
- **Onprocess**: `ตัวแทนยังไม่ส่งขึ้นทะเบียน`, `เอกสารยังไม่ครบ`, `อยู่ระหว่างอบรมทฤษฎี/ปฏิบัติ`, etc.
- **Closed**: `ไม่ผ่านอบรม`, `ไม่ผ่านคุณสมบัติ`, `ไม่เข้าอบรม`
- **Cancel**: `ช่างลาออก`, `ติดประวัติอาชญากรรม`

### Area Sorting Convention
Areas follow RSM (Regional Service Manager) naming: `RSM1`, `RSM2`, `RSM3`...  
Use regex extraction for natural sorting:
```python
match = re.search(r'RSM(\d+)', area)
return int(match.group(1)) if match else 999
```

## Development

### Environment Setup
```bash
pip install -r requirements.txt
```
Required `.env` file:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

### Running Locally
```bash
python app.py  # Runs on http://localhost:5000
```

### Frontend Stack
- **Tailwind CSS** via CDN
- **Chart.js 4.4.1** with `chartjs-plugin-datalabels`
- **Font Awesome 6.4.0** for icons
- Thai font: `Noto Sans Thai`

## API Routes
All API endpoints return JSON, load fresh data via `load_data()` → `process_data()`:
- `/api/summary` - Overall KPIs
- `/api/technicians?status=&area=&province=&depot_code=&depot_name=` - Filtered technician list
- `/api/provinces-map` - All provinces for map visualization
- `/api/bottleneck` - SLA bottleneck analysis

## Conventions

### Safe Value Handling
Use `safe_int()` and `safe_str()` helpers for DataFrame values to handle None/NaN:
```python
'sla_total': safe_int(row.get('sla_total')),
'name': safe_str(row.get('full_name_th'))
```

### Template Context
`@app.context_processor` injects `current_date` globally (format: "24 December 2025")

### Deployment
Vercel deployment configured in `vercel.json` - all routes handled by `app.py`
