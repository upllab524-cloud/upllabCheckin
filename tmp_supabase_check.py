from pathlib import Path
from dotenv import load_dotenv
import os
from supabase import create_client

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_ANON_KEY')
print('SUPABASE_URL=', url)
print('SUPABASE_KEY=', 'YES' if key else 'NO')
if not url or not key:
    raise SystemExit('missing SUPABASE_URL or SUPABASE key')
client = create_client(url, key)
print('client', client)
try:
    res = client.table('students').select('*').limit(1).execute()
    print('res type', type(res))
    print('res', res)
    print('data', res.data)
    print('error', res.error)
except Exception as e:
    print('exception', repr(e))
