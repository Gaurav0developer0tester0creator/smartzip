import gzip, bz2, lzma, brotli
import lz4.frame
import zstandard as zstd
import os, time, math, mimetypes, json

# ----------------------
# Threshold Loader & Saver
# ----------------------
def load_thresholds(file="smartzip_thresholds.json"):
    defaults = {"entropy_threshold": 3.5, "size_threshold": 5_000_000}
    if os.path.exists(file):
        try:
            with open(file) as f:
                return json.load(f)
        except Exception:
            return defaults
    return defaults

def save_thresholds(thresholds, file="smartzip_thresholds.json"):
    with open(file, "w") as f:
        json.dump(thresholds, f, indent=2)

THRESHOLDS = load_thresholds()

# ----------------------
# Helpers
# ----------------------
def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    entropy = 0
    for f in freq:
        if f > 0:
            p = f / len(data)
            entropy -= p * math.log2(p)
    return entropy

def detect_file_type(file_path: str):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"

def choose_algorithm(entropy: float, size: int, thresholds=None) -> str:
    if thresholds is None:
        thresholds = THRESHOLDS

    if entropy > thresholds["entropy_threshold"]:
        return "brotli"
    elif size > thresholds["size_threshold"]:
        return "lz4"
    return "zstd"

# ----------------------
# Adaptive Decision Logic
# ----------------------
def adaptive_decision(file_info, thresholds=None, auto_recalibrate_enabled=False, window=500):
    """
    Decide best algorithm based on entropy and size thresholds.
    """
    # Load thresholds
    if thresholds is None:
        thresholds = load_thresholds()

    entropy_threshold = thresholds.get("entropy_threshold", 3.5)
    size_threshold = thresholds.get("size_threshold", 5_000_000)

    # Optional: update thresholds dynamically
    if auto_recalibrate_enabled:
        try:
            from smartzip_dashboard import auto_recalibrate_from_log
            thresholds = auto_recalibrate_from_log(window=window)
            if thresholds:
                entropy_threshold = thresholds["entropy_threshold"]
                size_threshold = thresholds["size_threshold"]
        except Exception as e:
            print("⚠️ Auto-recalibration failed:", e)

    # --- Decision Logic ---
    algo = "zstd"   # default

    if file_info["entropy"] > entropy_threshold:
        algo = "brotli"
    elif file_info["size"] > size_threshold:
        algo = "lz4"
    elif file_info["size"] < 1000:  # very small files
        algo = "gzip"
    elif 1000 <= file_info["size"] <= 100000 and file_info["entropy"] < 2.5:
        algo = "bz2"
    elif file_info["entropy"] < 1.5:  # very repetitive data
        algo = "lzma"
    else:
        algo = "zstd"

    decision = {
        "algo": algo,
        "entropy_threshold": entropy_threshold,
        "size_threshold": size_threshold,
        "file_entropy": file_info.get("entropy"),
        "file_size": file_info.get("size"),
        "timestamp": time.time()
    }

    # Optional: log to catalog
    try:
        from smartzip_catalog import add_decision_to_catalog
        add_decision_to_catalog(file_info.get("name", "unknown"), decision)
    except Exception as e:
        print("⚠️ Catalog logging failed:", e)

    return decision

# ----------------------
# Adaptive Compression Wrapper
# ----------------------
def adaptive_compress(file_path: str, thresholds=None, auto_recalibrate_enabled=False):
    if thresholds is None:
        thresholds = load_thresholds()

    with open(file_path, "rb") as f:
        data = f.read()

    entropy = shannon_entropy(data)
    size = len(data)

    file_info = {"name": os.path.basename(file_path), "entropy": entropy, "size": size}
    decision = adaptive_decision(file_info, thresholds, auto_recalibrate_enabled)

    algo = decision["algo"]
    compressed = None

    if algo == "zstd":
        compressed = zstd.ZstdCompressor().compress(data)
    elif algo == "brotli":
        compressed = brotli.compress(data)
    elif algo == "lz4":
        compressed = lz4.frame.compress(data)
    elif algo == "gzip":
        compressed = gzip.compress(data)
    elif algo == "bz2":
        compressed = bz2.compress(data)
    elif algo == "lzma":
        compressed = lzma.compress(data)

    return compressed, decision

# ----------------------
# Threshold Database (Optional Future Use)
# ----------------------
def init_threshold_db():
    # Placeholder for DB-based threshold management
    pass

def log_thresholds(entropy_threshold, size_threshold):
    log_entry = {
        "timestamp": time.time(),
        "entropy_threshold": entropy_threshold,
        "size_threshold": size_threshold,
    }
    with open("adaptive_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

# ----------------------
# Auto Recalibration
# ----------------------
def auto_recalibrate(window=500, log_file="adaptive_log.jsonl"):
    """
    Wrapper to recalibrate thresholds from log or DB.
    """
    try:
        from smartzip_dashboard import auto_recalibrate_from_log
        thresholds = auto_recalibrate_from_log(log_file=log_file, window=window)
        if thresholds:
            return thresholds
    except ImportError:
        print("⚠️ Dashboard recalibration not available")
    except Exception as e:
        print("⚠️ Auto-recalibration error:", e)

    return load_thresholds()

# ----------------------
# Catalog Integration
# ----------------------
def add_decision_to_catalog(file_name, decision):
    try:
        import sqlite3
        conn = sqlite3.connect("smartzip_catalog.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                algo TEXT,
                entropy REAL,
                size INTEGER,
                entropy_threshold REAL,
                size_threshold INTEGER,
                timestamp REAL
            )
        """)
        c.execute("""
            INSERT INTO decisions (file_name, algo, entropy, size, entropy_threshold, size_threshold, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            file_name,
            decision.get("algo"),
            decision.get("file_entropy"),
            decision.get("file_size"),
            decision.get("entropy_threshold"),
            decision.get("size_threshold"),
            decision.get("timestamp"),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print("⚠️ Failed to log decision to catalog:", e)
