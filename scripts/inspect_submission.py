import psycopg2

URL = "postgresql://vidyakashi_user:CemjwfuW4GbhBz1q8NjigsX4SYKfOuGg@dpg-dbe7v0avcj2c73c1tf1g-a.singapore-postgres.render.com:5432/vidyakashi_omr?sslmode=require"
conn = psycopg2.connect(URL)
cur = conn.cursor()

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'submissions';")
cols = [r[0] for r in cur.fetchall()]
print("Columns in submissions:", cols)

cur.execute("SELECT id, examination_id, detected_roll_number, uploaded_image_id FROM submissions;")
subs = cur.fetchall()
print(f"Total Submissions: {len(subs)}")
for s in subs:
    print(f" - Submission #{s[0]}: Exam {s[1]}, Roll: {s[2]}, ImgID: {s[3]}")

cur.execute("SELECT id, original_filename, storage_key, rectified_storage_key, diagnostic_storage_key FROM uploaded_images;")
imgs = cur.fetchall()
print(f"\nTotal Uploaded Images: {len(imgs)}")
for im in imgs:
    print(f" - Image #{im[0]}: {im[1]}, Storage: {im[2]}, Rectified: {im[3]}, Diag: {im[4]}")

conn.close()
