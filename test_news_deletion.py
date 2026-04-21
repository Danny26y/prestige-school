import sqlite3
import uuid
import requests
from datetime import datetime, timezone

con = sqlite3.connect('test.db')
cur = con.cursor()

news_id = str(uuid.uuid4())
image_url = "https://res.cloudinary.com/demo/image/upload/v1612345678/prestige_news/fake_id.jpg"

cur.execute(
    "INSERT INTO News (id, title, content, imageUrl, category, is_urgent, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (news_id, "Test Deletion News", "Test content", image_url, "General", 0, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
)
con.commit()
con.close()

base_url = "http://127.0.0.1:8000"
session = requests.Session()
login_data = {"email": "admin@prestigesoh.com.ng", "password": "myadminpassword"}
session.post(f"{base_url}/login", data=login_data)

r = session.post(f"{base_url}/admin/news/delete/{news_id}", allow_redirects=False)
print("Delete status:", r.status_code)
assert r.status_code == 303

con = sqlite3.connect('test.db')
cur = con.cursor()
cur.execute("SELECT * FROM News WHERE id=?", (news_id,))
row = cur.fetchone()
print("News in DB after delete:", row)
assert row is None
con.close()

print("Deletion logic test passed.")
