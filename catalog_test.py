from smartzip_catalog import store, query, get

# 1. Store file into catalog
entry, comp_file = store("sample.txt", algo="zstd")
print("Stored:", entry)
print("Compressed file saved at:", comp_file)

# 2. Query catalog for all zstd files
print("\nQuery results (algo=zstd):")
rows = query({"algo": "zstd"})
for r in rows:
    print(r)

# 3. Query catalog for low-entropy files (entropy < 4.0)
print("\nQuery results (entropy < 4.0):")
rows = query({"entropy<": 4.0})
for r in rows:
    print(r)

# 4. Restore file from catalog by ID (first one)
get(1, "restored_sample.txt")
print("\nRestored file written to restored_sample.txt")
