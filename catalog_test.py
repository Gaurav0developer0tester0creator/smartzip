import sys
from smartzip_catalog import store, get, query

def main():
    if len(sys.argv) < 2:
        print("Usage: python catalog_test.py <filename>")
        return

    filename = sys.argv[1]

    # Store file and get entry
    entry, comp_file = store(filename)
    print(f"Stored: {entry}")
    print(f"👉 Algorithm chosen: {entry['algo']}")
    print(f"Compressed file saved at: {comp_file}\n")

    # Query by algo
    print("Query results (algo=zstd):")
    for row in query({"algo": "zstd"}):
        print(row)

    # Query by entropy
    print("\nQuery results (entropy < 4.0):")
    for row in query({"entropy<": 4.0}):
        print(row)

    # Restore test
    out_path = f"restored_{filename}"
    try:
        file_id = entry.get("id", entry["file_name"])   # ✅ prefer id, fallback to filename
        restored = get(file_id, out_path)
        print(f"\nRestored file written to {restored}")
    except Exception as e:
        print(f"⚠️ Restore failed: {e}")

if __name__ == "__main__":
    main()
