import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd

load_dotenv()
supabase = create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY'))
df = pd.DataFrame(supabase.table('training_sla').select('result, status').execute().data)

data = df[df['status'] == 'ไม่เข้าอบรม']
print(f'ช่าง "ไม่เข้าอบรม": {len(data)} คน')
if len(data) > 0:
    print(f'อยู่ในสถานะใหญ่: {data["result"].unique()[0]}')
else:
    print('ไม่พบข้อมูล')
