import sqlite3

# Connect to the database
conn = sqlite3.connect("smartzip_catalog.db")
cursor = conn.cursor()

# Show all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables found:", tables)

# Preview 5 rows from the first table (if exists)
if tables:
    first_table = tables[0][0]
    print(f"\nPreviewing first 5 rows from table: {first_table}")
    cursor.execute(f"SELECT * FROM {first_table} LIMIT 5;")
    for row in cursor.fetchall():
        print(row)

conn.close()
