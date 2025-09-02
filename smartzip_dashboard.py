import streamlit as st
import pandas as pd
import json
import os
import time
import sqlite3
import statistics
import matplotlib.pyplot as plt
from smartzip_catalog import DB_FILE
import subprocess
import sys
from datetime import datetime

# ----------------------------
# Anomaly Check
# ----------------------------
def check_anomalies(catalog_df, entropy_slope_limit=1.0, size_slope_limit=5_000_000):
    warnings = []

    if catalog_df.empty or len(catalog_df) < 2:
        return ["Not enough data for anomaly detection."]

    # Compression Quality
    if (catalog_df["compression_ratio"] < 0.1).any():
        warnings.append("⚠️ Very low compression ratios detected (<0.1).")

    # Entropy Drift (beyond ±2 std dev from mean)
    mean_entropy = catalog_df["entropy"].mean()
    std_entropy = catalog_df["entropy"].std()
    if ((catalog_df["entropy"] < mean_entropy - 2*std_entropy) |
        (catalog_df["entropy"] > mean_entropy + 2*std_entropy)).any():
        warnings.append("⚠️ Entropy drift detected (outliers).")

    # Algorithm Instability
    if "algorithm" in catalog_df.columns:
        algo_flips = (catalog_df["algorithm"] != catalog_df["algorithm"].shift()).sum()
        if algo_flips > len(catalog_df) // 3:
            warnings.append("⚠️ Algorithm switching too often (unstable).")

    # Size Growth
    if (catalog_df["original_size"].diff() > size_slope_limit).any():
        warnings.append("⚠️ Sudden file size growth detected.")

    return warnings


# ----------------------------
# Threshold Recalibration
# ----------------------------
def auto_recalibrate_from_log(log_file="smartzip/adaptive_log.jsonl", threshold_file="smartzip/smartzip_thresholds.json", window=500):
    """
    Recalibrate Smartzip thresholds (entropy, size) based on historical log data or DB fallback.
    """
    import json, os, sqlite3, statistics

    # --- 1. Try log file ---
    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except Exception:
                    continue

    # --- 2. Fallback to catalog DB if no logs ---
    if not logs:
        try:
            conn = sqlite3.connect("smartzip_catalog.db")
            c = conn.cursor()
            c.execute("SELECT entropy, original_size FROM files WHERE entropy IS NOT NULL LIMIT ?", (window,))
            rows = c.fetchall()
            for r in rows:
                logs.append({"entropy": r[0], "size": r[1]})
            conn.close()
        except Exception as e:
            print("⚠️ DB fallback failed:", e)

    if not logs:
        print("⚠️ No historical data available for recalibration.")
        return None

    # --- 3. Extract entropy & size distributions ---
    entropies = [entry.get("entropy") for entry in logs if entry.get("entropy") is not None]
    sizes = [entry.get("size") for entry in logs if entry.get("size") is not None]

    if not entropies or not sizes:
        print("⚠️ Missing entropy/size data in logs.")
        return None

    candidate_entropy = statistics.median(entropies)
    candidate_size = statistics.median(sizes)

    # --- 4. Load old thresholds ---
    thresholds = {"entropy_threshold": 3.5, "size_threshold": 5_000_000}
    if os.path.exists(threshold_file):
        try:
            with open(threshold_file, "r", encoding="utf-8") as f:
                thresholds = json.load(f)
        except Exception:
            pass

    # --- 5. Smooth update ---
    new_entropy = thresholds["entropy_threshold"] * 0.7 + candidate_entropy * 0.3
    new_size = thresholds["size_threshold"] * 0.7 + candidate_size * 0.3

    thresholds["entropy_threshold"] = round(new_entropy, 3)
    thresholds["size_threshold"] = int(new_size)

    # --- 6. Save back ---
    with open(threshold_file, "w", encoding="utf-8") as f:
        json.dump(thresholds, f, indent=2)

    print(f"✅ Recalibration complete. New thresholds: {thresholds}")
    return thresholds

# ----------------------------
# Threshold Management Helpers
# ----------------------------
def load_thresholds(file="smartzip_thresholds.json"):
    defaults = {"entropy_threshold": 3.5, "size_threshold": 5_000_000}
    file = os.path.join(os.path.dirname(__file__), file)
    if os.path.exists(file):
        try:
            with open(file) as f:
                return json.load(f)
        except Exception:
            return defaults
    return defaults

def save_thresholds(thresholds, file="smartzip_thresholds.json"):
    file = os.path.join(os.path.dirname(__file__), file)
    with open(file, "w") as f:
        json.dump(thresholds, f, indent=2)



def log_thresholds(entropy_threshold, size_threshold):
    log_entry = {
        "timestamp": time.time(),
        "entropy_threshold": entropy_threshold,
        "size_threshold": size_threshold,
    }
    with open("adaptive_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

# ----------------------------
# Dashboard Stubs (placeholders for your Streamlit app sections)
# ----------------------------
def threshold_dashboard():
    st.title("📦 Smartzip Dashboard")
    st.header("Smartzip Threshold Dashboard")
    st.write("Monitor and adjust thresholds.")

    # Load current thresholds
    thresholds = load_thresholds()
    st.write("### Current Thresholds")
    st.json(thresholds)

    # Button: Recalibrate thresholds from logs/DB
    if st.button("🔄 Auto-Recalibrate from History"):
        new_thresholds = auto_recalibrate_from_log()
        if new_thresholds:
            st.success(f"Recalibration complete: {new_thresholds}")
        else:
            st.warning("No data available for recalibration.")

    # Manual adjustment
    st.write("### Manually Adjust Thresholds")
    entropy_val = st.number_input(
        "Entropy Threshold", value=thresholds["entropy_threshold"], format="%.3f"
    )
    size_val = st.number_input(
        "Size Threshold (bytes)", value=thresholds["size_threshold"], step=1000
    )

    if st.button("💾 Save Thresholds"):
        save_thresholds({"entropy_threshold": entropy_val, "size_threshold": size_val})
        st.success("Thresholds saved successfully!")


import os

def health_dashboard():
    st.title("📦 Smartzip Dashboard")
    st.header("Smartzip Health Dashboard")
    st.write("System health and anomaly detection.")

    # Force absolute path
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "smartzip_catalog.db"))
    st.write(f"📂 Using database at: {db_path}")

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        df = pd.read_sql_query("SELECT * FROM files", conn)
        df = df.rename(columns={"algo": "algorithm"})
        conn.close()
    except Exception as e:
        st.error(f"Failed to load catalog: {e}")
        return

    if df.empty:
        st.warning("No data in catalog yet.")
        return

    st.write("### Catalog Data")
    st.dataframe(df)



    if df.empty:
        st.warning("No data in catalog yet.")
        return

    # Show raw table
    st.write("### Catalog Data")
    st.dataframe(df)

    # Check anomalies
    warnings = check_anomalies(df)
    if warnings:
        st.error("Anomalies detected:")
        for w in warnings:
            st.write("- " + w)
    else:
        st.success("✅ No anomalies detected.")

    # Basic plots
    st.write("### Entropy Distribution")
    st.bar_chart(df["entropy"])

    st.write("### Compression Ratios")
    st.bar_chart(df["compression_ratio"])


# ----------------------------
# Utility
# ----------------------------
def summarize(df):
    if df.empty:
        return "No data available."
    return df.describe()

def fmt(x, decimals=3):
    try:
        return round(float(x), decimals)
    except Exception:
        return x
if __name__ == "__main__":
    st.set_page_config(page_title="Smartzip Dashboard", layout="wide")

    st.title("📦 Smartzip Dashboard")
    st.sidebar.title("Navigation")

    page = st.sidebar.radio("Go to", ["Thresholds", "Health"])

    if page == "Thresholds":
        threshold_dashboard()
    elif page == "Health":
        health_dashboard()
