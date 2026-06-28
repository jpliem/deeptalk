import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
db = sqlite3.connect('deeptalk-demo.db')
rows = db.execute('SELECT label, summary, decisions, action_items FROM timeline_entry').fetchall()
print(f'Timeline entries: {len(rows)}')
for r in rows:
    print(f'  {r[0]}')
    print(f'    summary: {r[1][:100]}')
    print(f'    decisions: {r[2]}')
    print(f'    actions: {r[3]}')
db.close()
