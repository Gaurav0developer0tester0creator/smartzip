import os
import sqlite3
import importlib.util
import subprocess
import sys
import zstandard as zstd
from datetime import datetime

DB_PATH = "smartzip_catalog.db"

def install_package(pkg):
    """Try installing a missing package."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        return True
    except Exception as e:
        print(f"❌ Failed to install {pkg}: {e}")
        return False

def check_requirements(auto_fix=True):
    required = ["zstandard", "streamlit", "pandas"]
    missing = []
    for pkg in required:
        if importlib.util.find_spec(pkg) is None:
            missing.append(pkg)

    if missing and auto_fix:
        print("⚠️ Missing packages detected:", ", ".join(missing))
        for pkg in missing:
            print(f"➡️ Installing {pkg}...")
            install_package(pkg)

        # re-check
        still_missing = [pkg for pkg in missing if importlib.util.find_spec(pkg) is None]
        return still_missing
    return missing

def init_database():
    """Ensure DB and tables exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            filehash TEXT,
            algo TEXT,
            original_size INTEGER,
            compressed_size INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS health_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            requirements_status TEXT,
            database_status TEXT,
            dashboard_status TEXT,
            compression_status TEXT
        );
    """)
    conn.commit()
    conn.close()

def check_database(auto_fix=True):
    if not os.path.exists(DB_PATH):
        if auto_fix:
            print("⚠️ Database not found → creating new one...")
            try:
                init_database()
                return True, "Database created"
            except Exception as e:
                return False, f"Database creation failed: {e}"
        return False, "Database not found"
    else:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("SELECT name FROM sqlite_master LIMIT 1;")
            conn.close()
            return True, "Database OK"
        except Exception as e:
            return False, f"Database error: {e}"

def check_dashboard():
    return os.path.exists("smartzip_dashboard.py")

def check_compression_roundtrip():
    sample = b"Smartzip health check sample text"
    try:
        compressor = zstd.ZstdCompressor()
        compressed = compressor.compress(sample)

        decompressor = zstd.ZstdDecompressor()
        restored = decompressor.decompress(compressed)

        return restored == sample
    except Exception as e:
        print("❌ Compression error:", e)
        return False

def log_results(requirements_status, database_status, dashboard_status, compression_status):
    """Log health check results into DB."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO health_logs (timestamp, requirements_status, database_status, dashboard_status, compression_status)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now(), requirements_status, database_status, dashboard_status, compression_status))
    conn.commit()
    conn.close()

def run_health_check(auto_fix=True):
    print("🔍 Smartzip Health Check (with Auto-Fix + Logging)\n")

    # Init DB if needed
    init_database()

    # Requirements
    missing = check_requirements(auto_fix=auto_fix)
    req_status = "OK" if not missing else f"Missing: {', '.join(missing)}"
    print("✅ All required packages installed" if not missing else f"❌ {req_status}")

    # Database
    db_ok, db_msg = check_database(auto_fix=auto_fix)
    db_status = "OK" if db_ok else db_msg
    print("✅" if db_ok else "❌", db_msg)

    # Dashboard
    dash_ok = check_dashboard()
    dash_status = "OK" if dash_ok else "Missing"
    print("✅ Dashboard found (smartzip_dashboard.py)" if dash_ok else "❌ Dashboard missing")

    # Compression Roundtrip
    comp_ok = check_compression_roundtrip()
    comp_status = "OK" if comp_ok else "Failed"
    print("✅ Compression roundtrip works" if comp_ok else "❌ Compression roundtrip failed")

    # Log results
    log_results(req_status, db_status, dash_status, comp_status)
    print("\n📋 Results logged into smartzip_catalog.db (table: health_logs)")

if __name__ == "__main__":
    run_health_check(auto_fix=True)
# To run: python project_check.py