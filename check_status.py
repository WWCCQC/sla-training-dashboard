import os
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd

load_dotenv()
supabase = create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY'))
df = pd.DataFrame(supabase.table('training_sla').select('result, status').execute().data)

print('=== สรุปสถานะใหญ่และสถานะย่อย ===\n')

for result in ['Completed', 'Closed', 'Cancel', 'Onprocess']:
    print(f'\n📊 {result}: {len(df[df["result"] == result])} คน')
    statuses = df[df['result'] == result]['status'].value_counts()
    for status, count in statuses.items():
        print(f'   - {status}: {count} คน')
