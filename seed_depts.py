import sqlite3
import uuid

con = sqlite3.connect('test.db')
cur = con.cursor()

# Ensure table exists
cur.execute('''
    CREATE TABLE IF NOT EXISTS Department (
        id VARCHAR PRIMARY KEY,
        name VARCHAR NOT NULL,
        description TEXT,
        head_of_department VARCHAR,
        imageUrl VARCHAR
    )
''')

# Insert dummy data
depts = [
    (str(uuid.uuid4()), "ND Community Health Technology", "Focuses on providing essential healthcare services and promoting public health at the community level. Approved by NBTE.", "Dr. John Doe", "https://images.unsplash.com/photo-1576091160399-11cbbe98ee04?q=80&w=800&auto=format&fit=crop"),
    (str(uuid.uuid4()), "ND Medical Laboratory Technology", "Trains students in clinical laboratory tests to diagnose, treat, and prevent diseases. Approved by NBTE.", "Dr. Jane Smith", "https://images.unsplash.com/photo-1579154204601-01588f351e67?q=80&w=800&auto=format&fit=crop")
]

cur.executemany('INSERT INTO Department (id, name, description, head_of_department, imageUrl) VALUES (?, ?, ?, ?, ?)', depts)

con.commit()
con.close()
print("Departments seeded successfully.")
