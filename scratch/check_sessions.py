import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
db = sqlite3.connect('deeptalk-demo.db')

# Transcript events per session
rows = db.execute('SELECT session_id, count(*) FROM transcript_event GROUP BY session_id').fetchall()
print('Transcript events:')
for r in rows:
    print(f'  {r[0]}: {r[1]}')

# Timeline entries per session
rows = db.execute('SELECT session_id, count(*) FROM timeline_entry GROUP BY session_id').fetchall()
print('Timeline entries:')
for r in rows:
    print(f'  {r[0]}: {r[1]}')

# Show timeline details
rows = db.execute('SELECT session_id, label, end_ts FROM timeline_entry ORDER BY session_id, end_ts').fetchall()
for r in rows:
    print(f'  [{r[0]}] {r[1]} @ {r[2]}')

db.close()
