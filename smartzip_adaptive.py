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

def detect_file_type(file_path: str, data: bytes) -> str:
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime
    text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
    if all(c in text_chars for c in data[:1000]):
        return "text/plain"
    return "application/octet-stream"

# ----------------------
# Compressors
# ----------------------
compressors = {
    "gzip":   (lambda d: gzip.compress(d),   lambda d: gzip.decompress(d)),
    "bz2":    (lambda d: bz2.compress(d),    lambda d: bz2.decompress(d)),
    "lzma":   (lambda d: lzma.compress(d),   lambda d: lzma.decompress(d)),
    "lz4":    (lambda d: lz4.frame.compress(d), lambda d: lz4.frame.decompress(d)),
    "zstd":   (
        lambda d: zstd.ZstdCompressor().compress(d),
        lambda d: zstd.ZstdDecompressor().decompress(d)
    ),
    "brotli": (lambda d: brotli.compress(d), lambda d: brotli.decompress(d)),
}

# ----------------------
# Adaptive Decision Engine
# ----------------------
def choose_algorithm(file_type: str, entropy: float, size: int) -> str:
    et = THRESHOLDS.get("entropy_threshold", 3.5)
    st = THRESHOLDS.get("size_threshold", 5_000_000)

    if entropy > 7.5:
        return "SKIP"

    if "json" in file_type or "text" in file_type:
        if entropy < et:
            return "brotli"
        return "zstd"

    if "audio" in file_type or "video" in file_type or "image" in file_type:
        if size > st:
            return "lz4"
        return "zstd"

    return "zstd"

# ----------------------
# Auto-Recalibration Logic
# ----------------------
def auto_recalibrate(log_file="adaptive_log.jsonl"):
    if not os.path.exists(log_file):
        return THRESHOLDS, 0.0

    with open(log_file) as f:
        records = [json.loads(line) for line in f]

    if len(records) < 3:  # Not enough data yet
        return THRESHOLDS, 0.0

    df = records  # simple list of dicts
    entropy_range = [x/10 for x in range(20, 51)]  # 2.0–5.0
    size_range = [1_000_000, 5_000_000, 10_000_000, 20_000_000]

    best_score, best_params = -1, (THRESHOLDS["entropy_threshold"], THRESHOLDS["size_threshold"])

    for et in entropy_range:
        for st in size_range:
            correct = 0
            for row in df:
                predicted = choose_algorithm(row["type"], row["entropy"], row["original_size"])
                if predicted == row["algorithm"]:
                    correct += 1
            acc = correct / len(df)
            if acc > best_score:
                best_score, best_params = acc, (et, st)

    new_thresholds = {"entropy_threshold": best_params[0], "size_threshold": best_params[1]}
    save_thresholds(new_thresholds)
    return new_thresholds, best_score

# ----------------------
# Adaptive Compressor
# ----------------------
def adaptive_compress(file_path: str, log_file="adaptive_log.jsonl", recalibrate_every=5):
    global THRESHOLDS

    with open(file_path, "rb") as f:
        data = f.read()

    size = len(data)
    entropy = shannon_entropy(data)
    ftype = detect_file_type(file_path, data)
    algo = choose_algorithm(ftype, entropy, size)

    if algo == "SKIP":
        print(f"⚠️  Skipping {file_path} (entropy={entropy:.2f}, looks random).")
        result = {
            "file": os.path.basename(file_path),
            "type": ftype,
            "algorithm": "SKIP",
            "original_size": size,
            "compressed_size": size,
            "compression_ratio": 1.0,
            "comp_time_sec": 0,
            "decomp_time_sec": 0,
            "entropy": entropy
        }
    else:
        comp, decomp = compressors[algo]
        start = time.time()
        compressed = comp(data)
        comp_time = time.time() - start

        start = time.time()
        restored = decomp(compressed)
        decomp_time = time.time() - start
        assert restored == data, "Decompression failed!"

        ratio = len(compressed) / size
        print(f"✅ {file_path} | Algo={algo} | Entropy={entropy:.2f} | Ratio={ratio:.4f} "
              f"(Thresholds: {THRESHOLDS})")

        result = {
            "file": os.path.basename(file_path),
            "type": ftype,
            "algorithm": algo,
            "original_size": size,
            "compressed_size": len(compressed),
            "compression_ratio": ratio,
            "comp_time_sec": comp_time,
            "decomp_time_sec": decomp_time,
            "entropy": entropy
        }

    # Append to log
    with open(log_file, "a") as f:
        f.write(json.dumps(result) + "\n")

    # Auto recalibration every N files
    if os.path.getsize(log_file) % recalibrate_every == 0:  # every N entries
        new_th, acc = auto_recalibrate(log_file)
        THRESHOLDS = new_th
        print(f" Recalibrated → {THRESHOLDS} | Accuracy={acc*100:.2f}%")

    return result

# ----------------------
# Example Run
# ----------------------
if __name__ == "__main__":
    print(f" Starting with thresholds: {THRESHOLDS}")
    test_folder = "testdata"
    for fname in os.listdir(test_folder):
        fpath = os.path.join(test_folder, fname)
        adaptive_compress(fpath)
