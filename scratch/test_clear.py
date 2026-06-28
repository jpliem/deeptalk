import sqlite3
db_path = "deeptalk-demo.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("Before direct clear:")
print("Transcripts count:", conn.execute("SELECT count(*) FROM transcript_event WHERE session_id = 'demo'").fetchone()[0])
print("Artifacts count:", conn.execute("SELECT count(*) FROM artifact WHERE session_id = 'demo'").fetchone()[0])

conn.execute("DELETE FROM transcript_event WHERE session_id = 'demo'")
conn.execute("DELETE FROM artifact WHERE session_id = 'demo'")
conn.commit()

print("After direct clear:")
print("Transcripts count:", conn.execute("SELECT count(*) FROM transcript_event WHERE session_id = 'demo'").fetchone()[0])
print("Artifacts count:", conn.execute("SELECT count(*) FROM artifact WHERE session_id = 'demo'").fetchone()[0])

conn.close()
