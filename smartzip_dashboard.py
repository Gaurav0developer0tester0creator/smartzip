import streamlit as st
import pandas as pd
import json
import os
import time
import sqlite3
import statistics
import matplotlib.pyplot as plt
from smartzip_catalog import DB_FILE

# ----------------------------
# Threshold History Tracking
# ----------------------------
threshold_history_file = "threshold_history.jsonl"

def log_thresholds(thresholds):
    """Append thresholds with timestamp to history log."""
    entry = {"entropy_threshold": thresholds["entropy_threshold"],
             "size_threshold": thresholds["size_threshold"],
             "timestamp": time.time()}
    with open(threshold_history_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

def load_threshold_history(file=threshold_history_file):
    if os.path.exists(file):
        with open(file) as f:
            records = [json.loads(line) for line in f]
        return pd.DataFrame(records)
    return pd.DataFrame()

# ----------------------------
# Load/Save Thresholds
# ----------------------------
threshold_file = "smartzip_thresholds.json"

def load_thresholds(file=threshold_file):
    if os.path.exists(file):
        with open(file) as f:
            return json.load(f)
    return {"entropy_threshold": 3.5, "size_threshold": 5_000_000}

def save_thresholds(thresholds, file=threshold_file):
    with open(file, "w") as f:
        json.dump(thresholds, f, indent=2)
    log_thresholds(thresholds)  # track history

# ----------------------------
# Load Logs
# ----------------------------
log_file = "adaptive_log.jsonl"

def load_logs(file=log_file):
    if os.path.exists(file):
        with open(file) as f:
            records = [json.loads(line) for line in f]
        return pd.DataFrame(records)
    return pd.DataFrame()

# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(page_title="SmartZip Dashboard", layout="wide")

st.title("📊 SmartZip Dashboard")
st.markdown("Real-time monitoring and control for SmartZip Adaptive Protocol")

# Refresh control
from streamlit_autorefresh import st_autorefresh
refresh_rate = st.sidebar.slider("🔄 Refresh rate (seconds)", 2, 30, 5)
st_autorefresh(interval=refresh_rate * 1000, key="smartzip_dashboard_refresh")

# ----------------------------
# Threshold Controls
# ----------------------------
st.sidebar.subheader("⚙️ Threshold Controls")

thresholds = load_thresholds()

entropy_th = st.sidebar.slider(
    "Entropy Threshold (Brotli vs Zstd)",
    min_value=2.0, max_value=6.0, step=0.1,
    value=thresholds["entropy_threshold"]
)

size_th = st.sidebar.slider(
    "Size Threshold (Zstd vs LZ4, in MB)",
    min_value=1, max_value=50, step=1,
    value=thresholds["size_threshold"] // 1_000_000
)

# Apply/save button
if st.sidebar.button("💾 Save Thresholds"):
    new_th = {"entropy_threshold": entropy_th, "size_threshold": size_th * 1_000_000}
    save_thresholds(new_th)
    st.sidebar.success(f"Saved: {new_th}")

st.sidebar.json(load_thresholds())

# ----------------------------
# Log Visualization
# ----------------------------
df = load_logs()

if df.empty:
    st.warning("⚠️ No log data found yet. Run smartzip_adaptive.py first.")
else:
    st.subheader("Algorithm Usage")
    algo_counts = df["algorithm"].value_counts()
    st.bar_chart(algo_counts)

    st.subheader("Latest Decision")
    st.json(df.tail(1).to_dict(orient="records")[0])

    st.subheader("Entropy vs Compression Ratio")
    st.scatter_chart(df[["entropy", "compression_ratio"]])

    st.subheader("Algorithm Decisions Over Time")
    st.line_chart(df["algorithm"].astype("category").cat.codes)

    st.subheader("Compression & Decompression Times")
    st.line_chart(df[["comp_time_sec", "decomp_time_sec"]])

# ----------------------------
# Force Recalibration Button
# ----------------------------
def auto_recalibrate_from_log(log_file="adaptive_log.jsonl"):
    if not os.path.exists(log_file):
        return None, 0.0

    with open(log_file) as f:
        records = [json.loads(line) for line in f]
    if not records:
        return None, 0.0

    df = pd.DataFrame(records)

    entropy_range = [x/10 for x in range(20, 51)]  # 2.0–5.0
    size_range = [1_000_000, 5_000_000, 10_000_000, 20_000_000]

    best_score, best_params = -1, (3.5, 5_000_000)

    for et in entropy_range:
        for st in size_range:
            preds = df.apply(
                lambda row: (
                    "SKIP" if row["entropy"] > 7.5
                    else "brotli" if ("json" in row["type"] or "text" in row["type"]) and row["entropy"] < et
                    else "lz4" if ("audio" in row["type"] or "video" in row["type"] or "image" in row["type"]) and row["original_size"] > st
                    else "zstd"
                ),
                axis=1
            )
            acc = (preds == df["algorithm"]).mean()
            if acc > best_score:
                best_score, best_params = acc, (et, st)

    new_thresholds = {"entropy_threshold": best_params[0], "size_threshold": best_params[1]}
    return new_thresholds, best_score

st.sidebar.subheader("🔄 Auto-Recalibration")

if st.sidebar.button("Force Recalibrate Now"):
    new_th, acc = auto_recalibrate_from_log(log_file)
    if new_th:
        save_thresholds(new_th)
        st.sidebar.success(f"Recalibrated → {new_th} | Accuracy={acc*100:.2f}%")
    else:
        st.sidebar.warning("⚠️ No log data to recalibrate from.")

# ----------------------------
# Reset Threshold History
# ----------------------------
st.sidebar.subheader("🧹 History Management")

if st.sidebar.button("Reset Threshold History"):
    if os.path.exists(threshold_history_file):
        os.remove(threshold_history_file)
        st.sidebar.success("✅ Threshold history has been reset.")
    else:
        st.sidebar.info("ℹ️ No history file found to reset.")

# ----------------------------
# Threshold Evolution Plot
# ----------------------------
st.subheader("📈 Threshold Evolution Over Time")

history_df = load_threshold_history()

if history_df.empty:
    st.warning("⚠️ No threshold history yet.")
else:
    history_df["time"] = pd.to_datetime(history_df["timestamp"], unit="s")

    # Sidebar toggle
    st.sidebar.subheader("📊 History View Options")
    view_mode = st.sidebar.radio("View mode", ["Full History", "Last N Updates"])
    
    if view_mode == "Last N Updates":
        N = st.sidebar.slider("How many recent updates?", 5, 50, 10)
        history_df = history_df.tail(N)

    # Plot entropy threshold evolution
    st.line_chart(
        history_df.set_index("time")[["entropy_threshold"]],
        height=200
    )

    # Plot size threshold evolution (in MB)
    hist_size_mb = history_df.copy()
    hist_size_mb["size_threshold_mb"] = hist_size_mb["size_threshold"] / 1_000_000
    st.line_chart(
        hist_size_mb.set_index("time")[["size_threshold_mb"]],
        height=200
    )

# ----------------------------
# Threshold Trend Prediction with Confidence Bands
# ----------------------------
st.subheader("🔮 Threshold Trend Prediction (with Confidence Bands)")

from sklearn.linear_model import LinearRegression
import numpy as np
import matplotlib.pyplot as plt

slope_entropy = 0.0   # ✅ safe defaults
slope_size = 0.0

history_df = load_threshold_history()

if not history_df.empty:
    # Prepare data
    history_df["time"] = pd.to_datetime(history_df["timestamp"], unit="s")
    X = (history_df["time"].astype("int64") // 10**9).values.reshape(-1, 1)  # seconds since epoch
    
    # Entropy model
    y_entropy = history_df["entropy_threshold"].values
    model_entropy = LinearRegression().fit(X, y_entropy)
    entropy_pred = model_entropy.predict(X)

    # Size model
    y_size = history_df["size_threshold"].values
    model_size = LinearRegression().fit(X, y_size)
    size_pred = model_size.predict(X)

    # Forecast next 5 recalibrations (~500s apart)
    future_times = np.arange(X[-1][0], X[-1][0] + 500*5, 500).reshape(-1, 1)
    future_entropy = model_entropy.predict(future_times)
    future_size = model_size.predict(future_times)
    future_dates = pd.to_datetime(future_times.flatten(), unit="s")

    # --- Confidence Intervals (± std error) ---
    def conf_band(y_true, y_pred):
        residuals = y_true - y_pred
        std_err = np.std(residuals)
        return std_err

    entropy_err = conf_band(y_entropy, entropy_pred)
    size_err = conf_band(y_size, size_pred)

    # Plot Entropy
    st.subheader("📈 Entropy Threshold Forecast")
    fig_entropy, ax = plt.subplots(figsize=(8,4))
    ax.plot(history_df["time"], y_entropy, "o", label="History", alpha=0.6)
    ax.plot(future_dates, future_entropy, "-", color="blue", label="Forecast")
    ax.fill_between(future_dates,
                    future_entropy - entropy_err,
                    future_entropy + entropy_err,
                    color="blue", alpha=0.2, label="Confidence Band")
    ax.set_ylabel("Entropy Threshold")
    ax.legend()
    st.pyplot(fig_entropy)

    # Plot Size
    st.subheader("📈 Size Threshold Forecast (MB)")
    fig_size, ax2 = plt.subplots(figsize=(8,4))
    ax2.plot(history_df["time"], y_size/1_000_000, "o", label="History", alpha=0.6)
    ax2.plot(future_dates, future_size/1_000_000, "-", color="green", label="Forecast")
    ax2.fill_between(future_dates,
                     (future_size - size_err)/1_000_000,
                     (future_size + size_err)/1_000_000,
                     color="green", alpha=0.2, label="Confidence Band")
    ax2.set_ylabel("Size Threshold (MB)")
    ax2.legend()
    st.pyplot(fig_size)

    # Trend slopes
    slope_entropy = model_entropy.coef_[0]
    slope_size = model_size.coef_[0] / 1_000_000
    st.write(f"📈 Entropy trend slope: {slope_entropy:+.3f} per sec → "
             f"{'increasing' if slope_entropy > 0 else 'decreasing' if slope_entropy < 0 else 'stable'}")
    st.write(f"📈 Size threshold trend slope: {slope_size:+.3f} MB per sec → "
             f"{'increasing' if slope_size > 0 else 'decreasing' if slope_size < 0 else 'stable'}")

# ----------------------------
# Early Warning System (Configurable)
# ----------------------------
st.subheader("⚠️ Early Warning System")

st.sidebar.subheader("⚠️ Early Warning Settings")
entropy_slope_limit = st.sidebar.number_input(
    "Entropy slope warning limit (per sec)", 
    min_value=0.0001, max_value=0.01, step=0.0001, value=0.001,
    key="entropy_slope_limit"
)
size_slope_limit = st.sidebar.number_input(
    "Size slope warning limit (MB/sec)", 
    min_value=0.001, max_value=0.05, step=0.001, value=0.005,
    key="size_slope_limit"
)

warnings = []

# Check entropy slope
if abs(slope_entropy) > entropy_slope_limit:
    direction = "increasing" if slope_entropy > 0 else "decreasing"
    warnings.append(f"Entropy threshold is {direction} too quickly (slope={slope_entropy:+.4f}).")

# Check size slope
if abs(slope_size) > size_slope_limit:
    direction = "increasing" if slope_size > 0 else "decreasing"
    warnings.append(f"Size threshold is {direction} too quickly (slope={slope_size:+.4f} MB/sec).")

# Display warnings
if warnings:
    for w in warnings:
        st.error("⚠️ " + w)
else:
    st.success("✅ Threshold trends are stable. No early warnings triggered.")

# ----------------------------
# Threshold History Export
# ----------------------------
st.subheader("💾 Export Threshold History")

if not history_df.empty:
    csv_data = history_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download as CSV",
        data=csv_data,
        file_name="threshold_history.csv",
        mime="text/csv"
    )
    json_data = history_df.to_json(orient="records", indent=2).encode("utf-8")
    st.download_button(
        label="⬇️ Download as JSON",
        data=json_data,
        file_name="threshold_history.json",
        mime="application/json"
    )
else:
    st.info("ℹ️ No history available to export.")

# ----------------------------
# Threshold History Comparison
# ----------------------------
st.subheader("🔍 Compare Current vs Previous Threshold History")

uploaded_file = st.file_uploader("Upload a previous threshold history file (CSV or JSON)", type=["csv", "json"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            prev_df = pd.read_csv(uploaded_file)
        else:
            prev_df = pd.read_json(uploaded_file)

        if "timestamp" in prev_df.columns:
            prev_df["time"] = pd.to_datetime(prev_df["timestamp"], unit="s")
        elif "time" not in prev_df.columns and "entropy_threshold" in prev_df.columns:
            prev_df["time"] = pd.Series(range(len(prev_df)))

        st.write("✅ Loaded previous history file successfully.")

        current_df = history_df.copy()
        current_df["source"] = "Current"
        prev_df["source"] = "Previous"
        combined = pd.concat([current_df, prev_df], ignore_index=True)

        st.subheader("📈 Entropy Threshold Comparison")
        st.line_chart(
            combined.set_index("time")[["entropy_threshold"]],
            height=200
        )
        st.subheader("📈 Size Threshold Comparison (MB)")
        combined["size_threshold_mb"] = combined["size_threshold"] / 1_000_000
        st.line_chart(
            combined.set_index("time")[["size_threshold_mb"]],
            height=200
        )

    except Exception as e:
        st.error(f"❌ Failed to load history file: {e}")
else:
    st.info("ℹ️ Upload a CSV or JSON file to compare with current history.")

# ----------------------------
# Catalog & Statistics
# ----------------------------
st.header("📂 Catalog & Statistics")

conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query("SELECT * FROM files", conn)
conn.close()

if df.empty:
    st.warning("Catalog is empty. Add files with smartzip_catalog.store().")
else:
    st.sidebar.header("🔎 Filters")
    algo_options = ["All"] + sorted(df["algo"].dropna().unique().tolist())
    algo_filter = st.sidebar.selectbox("Algorithm", algo_options)
    mime_options = ["All"] + sorted(df["mime_type"].dropna().unique().tolist())
    mime_filter = st.sidebar.selectbox("MIME Type", mime_options)

    # Entropy range slider
entropy_min, entropy_max = float(df["entropy"].min()), float(df["entropy"].max())

# Prevent crash when min == max
if entropy_min == entropy_max:
    entropy_min = max(0.0, entropy_min - 0.1)
    entropy_max = entropy_max + 0.1

entropy_range = st.sidebar.slider(
    "Entropy Range",
    entropy_min, entropy_max,
    (entropy_min, entropy_max),
    key="entropy_range_slider"
)


    # Ratio range slider
ratio_min, ratio_max = float(df["compression_ratio"].min()), float(df["compression_ratio"].max())

# Prevent crash when min == max
if ratio_min == ratio_max:
    ratio_min = max(0.0, ratio_min - 0.01)
    ratio_max = ratio_max + 0.01

ratio_range = st.sidebar.slider(
    "Compression Ratio Range",
    ratio_min, ratio_max,
    (ratio_min, ratio_max),
    key="ratio_range_slider"
)


filtered_df = df.copy()
if algo_filter != "All":
    filtered_df = filtered_df[filtered_df["algo"] == algo_filter]
if mime_filter != "All":
    filtered_df = filtered_df[filtered_df["mime_type"] == mime_filter]
filtered_df = filtered_df[
    (filtered_df["entropy"] >= entropy_range[0]) & (filtered_df["entropy"] <= entropy_range[1])
]
filtered_df = filtered_df[
    (filtered_df["compression_ratio"] >= ratio_range[0]) & (filtered_df["compression_ratio"] <= ratio_range[1])
]

st.subheader("Catalog Entries")
st.dataframe(filtered_df)

st.subheader("Entropy Distribution")
if not filtered_df["entropy"].dropna().empty:
    fig, ax = plt.subplots()
    filtered_df["entropy"].dropna().hist(bins=20, ax=ax)
    ax.set_xlabel("Entropy (bits/byte)")
    ax.set_ylabel("Count")
    st.pyplot(fig)
else:
    st.info("No entropy data for current filter.")

st.subheader("Per-Algorithm Stats (Filtered)")
for algo, group in filtered_df.groupby("algo"):
    entropies = group["entropy"].dropna().tolist()
    ratios = group["compression_ratio"].dropna().tolist()
    if entropies and ratios:
        st.markdown(f"### 🔹 {algo.upper()}")
        st.write(f"- Files: {len(group)}")
        st.write(f"- Avg entropy: {statistics.mean(entropies):.3f}")
        st.write(f"- Min entropy: {min(entropies):.3f}")
        st.write(f"- Max entropy: {max(entropies):.3f}")
        st.write(f"- Avg ratio: {statistics.mean(ratios):.4f}")
        st.write(f"- Best ratio: {min(ratios):.4f}")
        st.write(f"- Worst ratio: {max(ratios):.4f}")

# ----------------------------
# Debug Mode (Sidebar Toggle)
# ----------------------------
st.sidebar.subheader("🛠️ Debug Mode")
debug_mode = st.sidebar.checkbox("Enable Debug Mode", value=False)

if debug_mode:
    st.subheader("🛠️ Debug Information")
    st.write("### Thresholds")
    st.json(load_thresholds())

    st.write("### Slopes & Limits")
    st.write({
        "slope_entropy": slope_entropy,
        "slope_size": slope_size,
        "entropy_slope_limit": entropy_slope_limit,
        "size_slope_limit": size_slope_limit
    })

    if not history_df.empty:
        st.write("### Last 3 Threshold Updates")
        st.dataframe(history_df.tail(3))


# ----------------------------
# Side-by-side Metrics Summary
# ----------------------------
if uploaded_file is not None and 'prev_df' in locals():
    st.subheader("📊 Metrics Summary (Current vs Previous)")

    def summarize(df, label):
        return pd.DataFrame({
            "Source": [label],
            "Avg Entropy Th": [df["entropy_threshold"].mean()],
            "Avg Size Th (MB)": [df["size_threshold"].mean() / 1_000_000],
            "Recalibrations": [len(df)]
        })

    current_df = history_df.copy()
    summary_current = summarize(current_df, "Current")
    summary_previous = summarize(prev_df, "Previous")

    summary_table = pd.concat([summary_current, summary_previous], ignore_index=True)
    st.table(summary_table)

    st.subheader("📊 Metrics Summary (Current vs Previous + Δ Differences)")

    def summarize(df, label):
        return pd.Series({
            "Avg Entropy Th": df["entropy_threshold"].mean(),
            "Avg Size Th (MB)": df["size_threshold"].mean() / 1_000_000,
            "Recalibrations": len(df)
        }, name=label)

    summary_current = summarize(current_df, "Current")
    summary_previous = summarize(prev_df, "Previous")

    summary_df = pd.concat([summary_previous, summary_current], axis=1)
    diff = summary_current - summary_previous
    diff.name = "Δ Difference"

    def fmt(val):
        if isinstance(val, (int, float)):
            return f"{val:+.2f}" if abs(val) > 0 else "0.0"
        return str(val)

    diff_formatted = diff.apply(fmt)
    final_table = pd.concat([summary_previous, summary_current, diff_formatted], axis=1)
    st.table(final_table)
