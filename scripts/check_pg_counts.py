import psycopg2

URL = "postgresql://vidyakashi_user:CemjwfuW4GbhBz1q8NjigsX4SYKfOuGg@dpg-dbe7v0avcj2c73c1tf1g-a.singapore-postgres.render.com:5432/vidyakashi_omr?sslmode=require"
conn = psycopg2.connect(URL)
cur = conn.cursor()
tables = ['users', 'students', 'template_versions', 'examinations', 'answer_keys', 'upload_batches', 'uploaded_images', 'submissions', 'detected_responses', 'audit_logs']
for t in tables:
    try:
        cur.execute(f'SELECT count(*) FROM "{t}";')
        print(f"{t}: {cur.fetchone()[0]}")
    except Exception as e:
        print(f"{t} error: {e}")
        conn.rollback()

cur.execute('SELECT id, code, title FROM examinations;')
exams = cur.fetchall()
print("\nExaminations in PG:")
for e in exams:
    print(f" - #{e[0]}: {e[1]} - {e[2]}")

cur.close()
conn.close()
