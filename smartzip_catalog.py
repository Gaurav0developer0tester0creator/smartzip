import os
import sqlite3
import hashlib
import mimetypes
import time
import compressors
import math
from smartzip_adaptive import shannon_entropy
from smartzip_adaptive import adaptive_decision
from compressors import compress_data

# directory for saving compressed files
COMPRESSED_DIR = "compressed"
os.makedirs(COMPRESSED_DIR, exist_ok=True)


# If add_decision_to_catalog is already defined in this file (it is!)
# → remove this line completely



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


def detect_file_type(file_path):
    """Detect the MIME type of a file using the mimetypes module."""
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"

DB_FILE = "smartzip_catalog.db"

# ----------------------------
# DB Setup
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Drop old table if exists (optional cleanup)
    c.execute("DROP TABLE IF EXISTS files")

    # Recreate with clean schema
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


def init_catalog_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filetype TEXT,
            algorithm TEXT,
            entropy REAL,
            original_size INTEGER,
            compressed_size INTEGER,
            compression_ratio REAL,
            entropy_threshold REAL,
            size_threshold REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

def add_decision_to_catalog(file_info, decision):
    """
    Store adaptive decision into catalog table.
    file_info: dict with file metadata (file, type, size, entropy)
    decision: dict returned by adaptive_decision()
    """
    decision_algo = decision.get("algo") or decision.get("algorithm")

    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        INSERT INTO catalog (filename, filetype, algorithm, entropy, original_size,
                             compressed_size, compression_ratio,
                             entropy_threshold, size_threshold, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        file_info.get("file"),
        file_info.get("type"),
        decision_algo,
        file_info.get("entropy"),
        file_info.get("size"),
        decision.get("compressed_size", None),
        decision.get("compression_ratio", None),
        decision.get("entropy_threshold"),
        decision.get("size_threshold"),
        decision["timestamp"]
    ))
    conn.commit()
    conn.close()

# ----------------------------
# Get File (decompress)
# ----------------------------
def get(file_id, out_path):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Allow lookup by numeric id or by file_name
    if isinstance(file_id, int) or (isinstance(file_id, str) and file_id.isdigit()):
        c.execute("SELECT file_name, algo FROM files WHERE id=?", (int(file_id),))
    else:
        c.execute("SELECT file_name, algo FROM files WHERE file_name=?", (file_id,))

    row = c.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"No file found with id or name={file_id}")

    file_name, algo = row
    comp_file = os.path.join(COMPRESSED_DIR, f"{file_name}.{algo}")
    if not os.path.exists(comp_file):
        raise FileNotFoundError(f"Compressed file missing: {comp_file}")

    # Read compressed data
    with open(comp_file, "rb") as f:
        compressed_data = f.read()

    # Decompress using the appropriate algorithm
    decompressor = getattr(compressors, f"decompress_{algo}", None)
    if not decompressor:
        raise ValueError(f"No decompressor found for algorithm: {algo}")

    data = decompressor(compressed_data)

    # Write restored file
    with open(out_path, "wb") as f:
        f.write(data)

    return out_path




def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

# ----------------------------
# Store File (compress + log)
# ----------------------------
def compress_data(data, algo):
    """Compress data using the specified algorithm from the compressors module."""
    compressor = getattr(compressors, f"compress_{algo}", None)
    if not compressor:
        raise ValueError(f"Compression algorithm '{algo}' not found in compressors module.")
    return compressor(data)

def log_to_catalog(entry):
    """Insert file metadata into the files table and return row id."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO files (
            file_name, file_hash, mime_type, algo,
            original_size, compressed_size, compression_ratio,
            entropy, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry["file_name"], entry["file_hash"], entry["mime_type"], entry["algo"],
        entry["original_size"], entry["compressed_size"], entry["compression_ratio"],
        entry["entropy"], entry["created_at"]
    ))
    row_id = c.lastrowid  # ✅ capture the auto-increment id
    conn.commit()
    conn.close()
    return row_id


# build entry dict
    entry = {
        "file_name": os.path.basename(file_path),
        "file_hash": file_hash_val,
        "mime_type": mime_type,
        "algo": algo,
        "original_size": len(data),
        "compressed_size": len(compressed),
        "compression_ratio": round(len(compressed) / len(data), 4) if len(data) else 0,
        "entropy": entropy_val,
        "created_at": time.time(),
    }

    # log to catalog and capture DB id
    entry_id = log_to_catalog(entry)
    entry["id"] = entry_id   # ✅ add id into entry

    return entry, comp_file


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
