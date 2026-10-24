import os
import shutil
import sqlite3

src = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\omr.db"
backup_dir = r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\backups"
os.makedirs(backup_dir, exist_ok=True)
dst = os.path.join(backup_dir, "omr_backup_pre_postgres.db")
shutil.copy2(src, dst)
print("Backed up omr.db to:", dst)

conn = sqlite3.connect(dst)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cur.fetchall()]
print("Tables in SQLite:")
for t in tables:
    cur.execute(f"SELECT count(*) FROM {t};")
    count = cur.fetchone()[0]
    print(f" - {t}: {count} rows")

cur.execute("SELECT id, code, title, question_count FROM examinations;")
exams = cur.fetchall()
print("\nExisting Examinations in SQLite:")
for e in exams:
    print(f" - #{e[0]}: {e[1]} - {e[2]} ({e[3]}Q)")

conn.close()
