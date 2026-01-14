import pandas as pd
from dotenv import load_dotenv
import os
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ.get('SUPABASE_URL'), os.environ.get('SUPABASE_KEY'))
response = supabase.table('training_sla').select('status, result, area, depot_code, depot_name, full_name_th').execute()
df = pd.DataFrame(response.data)

# กรอง RSM1_BMA-West และ Onprocess
test_df = df[(df['result'] == 'Onprocess') & (df['area'] == 'RSM1_BMA-West')]
print('RSM1_BMA-West Onprocess status breakdown:')
print(test_df['status'].value_counts())
print()
print('รายละเอียด:')
for status in test_df['status'].unique():
    sub_df = test_df[test_df['status'] == status]
    print(f'{status}: {len(sub_df)} คน')
    for _, row in sub_df.iterrows():
        print(f"  - {row['depot_code']} | {row['depot_name']} | {row['full_name_th']}")
