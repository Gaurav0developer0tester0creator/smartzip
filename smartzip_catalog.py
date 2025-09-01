import os
import sqlite3
import hashlib
import mimetypes
import time
import compressors
import math

# ----------------------------
# Entropy Calculation
# ----------------------------
def calculate_entropy(data: bytes) -> float:
    """Shannon entropy in bits per byte"""
    if not data:
        return 0.0
    freq = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    entropy = 0.0
    length = len(data)
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


DB_FILE = "smartzip_catalog.db"

# ----------------------------
# DB Setup
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        file_hash TEXT,
        mime_type TEXT,
        algo TEXT,
        original_size INTEGER,
        compressed_size INTEGER,
        compression_ratio REAL,
        entropy REAL,
        created_at REAL
    )
    """)
    conn.commit()
    conn.close()

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

# ----------------------------
# Store File (compress + log)
# ----------------------------
def store(file_path, algo="zstd", out_dir="compressed"):
    os.makedirs(out_dir, exist_ok=True)

    # Pick compressor
    compressor = getattr(compressors, f"compress_{algo}")
    decompressor = getattr(compressors, f"decompress_{algo}")

    # Read file
    with open(file_path, "rb") as f:
        data = f.read()
    original_size = len(data)

    # Compress
    compressed_data = compressor(data)
    compressed_size = len(compressed_data)
    ratio = compressed_size / original_size if original_size else 1.0

    # Save compressed file
    file_name = os.path.basename(file_path)
    out_file = os.path.join(out_dir, f"{file_name}.{algo}")
    with open(out_file, "wb") as f:
        f.write(compressed_data)

    # Metadata
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    entropy = calculate_entropy(data)

    entry = {
        "file_name": file_name,
        "file_hash": file_hash(file_path),
        "mime_type": mime_type,
        "algo": algo,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": ratio,
        "entropy": entropy,
        "created_at": time.time(),
    }

    # Insert into DB
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT INTO files 
        (file_name, file_hash, mime_type, algo, original_size, compressed_size, compression_ratio, entropy, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry["file_name"], entry["file_hash"], entry["mime_type"], entry["algo"],
         entry["original_size"], entry["compressed_size"], entry["compression_ratio"],
         entry["entropy"], entry["created_at"])
    )
    conn.commit()
    conn.close()

    return entry, out_file

# ----------------------------
# Get File (decompress)
# ----------------------------
def get(file_id, out_path):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT file_name, algo FROM files WHERE id=?", (file_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"No file found with id={file_id}")

    file_name, algo = row
    comp_file = os.path.join("compressed", f"{file_name}.{algo}")
    if not os.path.exists(comp_file):
        raise FileNotFoundError(f"Compressed file missing: {comp_file}")

    with open(comp_file, "rb") as f:
        compressed_data = f.read()

    decompressor = getattr(compressors, f"decompress_{algo}")
    data = decompressor(compressed_data)

    with open(out_path, "wb") as f:
        f.write(data)

    return out_path

# ----------------------------
# Query Catalog
# ----------------------------
def query(filters=None):
    filters = filters or {}
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    base = """
    SELECT id, file_name, mime_type, algo,
           original_size, compressed_size, compression_ratio,
           entropy, created_at
    FROM files WHERE 1=1
    """
    params = []

    for key, val in filters.items():
        if key == "algo":
            base += " AND algo=?"
            params.append(val)
        elif key == "mime_type":
            base += " AND mime_type=?"
            params.append(val)
        elif key == "entropy<":
            base += " AND entropy < ?"
            params.append(val)
        elif key == "ratio<":
            base += " AND compression_ratio < ?"
            params.append(val)

    c.execute(base, params)
    rows = c.fetchall()
    conn.close()
    return rows

# ----------------------------
# Init DB at import
# ----------------------------
init_db()
