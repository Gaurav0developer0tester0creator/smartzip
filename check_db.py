import sqlite3

# Connect to the DB
conn = sqlite3.connect("smartzip_catalog.db")
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables in DB:", cursor.fetchall())

# Example: Preview first 5 rows from 'files' table if it exists
try:
    cursor.execute("SELECT * FROM files LIMIT 5;")
    rows = cursor.fetchall()
    print("\nSample rows from 'files':")
    for row in rows:
        print(row)
except Exception as e:
    print("\nNo 'files' table found or error:", e)

conn.close()
