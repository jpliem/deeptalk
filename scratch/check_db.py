import sqlite3
import json

db_path = "deeptalk-demo.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== TRANSCIPT EVENTS ===")
rows = conn.execute("SELECT seq, session_id, ts, text, is_final, source, speaker, span_id FROM transcript_event ORDER BY seq").fetchall()
for r in rows:
    print(f"{r['seq']}: [{r['source']}] (ts={r['ts']}) {r['text']}")

print("\n=== ARTIFACTS ===")
rows = conn.execute("SELECT seq, id, session_id, agent, status, title, payload, created_at, latency_ms, error FROM artifact ORDER BY seq").fetchall()
for r in rows:
    print(f"[{r['agent']}] Status: {r['status']}, Title: '{r['title']}'")
    if r['error']:
        print(f"  Error: {r['error']}")
    else:
        try:
            p = json.loads(r['payload'])
            print(f"  Keys in payload: {list(p.keys())}")
            if 'answer' in p:
                print(f"  Answer: {p['answer'][:150]}...")
            if 'pros' in p:
                print(f"  Pros: {p['pros']}")
            if 'cons' in p:
                print(f"  Cons: {p['cons']}")
            if 'diagram' in p:
                print(f"  Diagram: {p['diagram'][:150]}...")
        except Exception as e:
            print(f"  Error parsing payload: {e}")

conn.close()
