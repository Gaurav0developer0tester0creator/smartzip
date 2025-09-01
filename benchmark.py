import time
import os
import csv
import mimetypes


import gzip, bz2, lzma, brotli
import lz4.frame
import zstandard as zstd

# --- Shannon Entropy Function ---
from collections import Counter
import math

def shannon_entropy(data: bytes) -> float:
    """Calculate the Shannon entropy of a byte string."""
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
    return entropy

# --- Compressor Wrappers ---
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

# --- Benchmark Function ---
def benchmark_file(file_path, results):
    with open(file_path, "rb") as f:
        data = f.read()

    original_size = len(data)
    entropy = shannon_entropy(data)
    ftype = detect_file_type(file_path, data)

    # Heuristic: incompressible if entropy > 7.5
    if entropy > 7.5:
        results.append({
            "file": os.path.basename(file_path),
            "type": ftype,
            "algorithm": "SKIPPED (high entropy)",
            "original_size": original_size,
            "compressed_size": original_size,
            "compression_ratio": 1.0,
            "comp_time_sec": 0,
            "decomp_time_sec": 0,
            "correct": True,
            "error": "",
            "entropy": entropy
        })
        return

    for name, (comp, decomp) in compressors.items():
        try:
            # Compression
            start = time.time()
            compressed = comp(data)
            comp_time = time.time() - start

            # Decompression
            start = time.time()
            restored = decomp(compressed)
            decomp_time = time.time() - start

            # Verify
            correct = restored == data

            results.append({
                "file": os.path.basename(file_path),
                "type": ftype,
                "algorithm": name,
                "original_size": original_size,
                "compressed_size": len(compressed),
                "compression_ratio": len(compressed) / original_size,
                "comp_time_sec": comp_time,
                "decomp_time_sec": decomp_time,
                "correct": correct,
                "error": "",
                "entropy": entropy
            })
        except Exception as e:
            results.append({
                "file": os.path.basename(file_path),
                "type": ftype,
                "algorithm": name,
                "error": str(e),
                "entropy": entropy
            })


def detect_file_type(file_path: str, data: bytes) -> str:
    """Try to detect file type (text/json/binary/etc.)."""
    # 1. MIME type detection
    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        return mime

    # 2. Simple heuristic: check if data is mostly printable
    text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
    if all(c in text_chars for c in data[:1000]):  # check first 1KB
        return "text/plain"

    return "application/octet-stream"  # default binary



# --- Main ---
if __name__ == "__main__":
    test_folder = "testdata"
    os.makedirs(test_folder, exist_ok=True)

    # Example test files
    if not os.listdir(test_folder):
        with open(os.path.join(test_folder, "sample_text.txt"), "w") as f:
            f.write("Hello SmartZip! " * 10000)
        with open(os.path.join(test_folder, "sample_json.json"), "w") as f:
            f.write('{"message": "Hello SmartZip!"}\n' * 5000)
        with open(os.path.join(test_folder, "sample_binary.bin"), "wb") as f:
            f.write(os.urandom(500000))  # 500 KB random binary

    results = []
    for fname in os.listdir(test_folder):
        benchmark_file(os.path.join(test_folder, fname), results)

    # Save results
with open("results.csv", "w", newline="") as csvfile:
    fieldnames = [
        "file", "type", "algorithm",
        "original_size", "compressed_size", "compression_ratio",
        "comp_time_sec", "decomp_time_sec",
        "correct", "error", "entropy"
    ]
    
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for row in results:
        # Ensure all required fields exist, fill missing ones with blanks
        cleaned_row = {key: row.get(key, "") for key in fieldnames}
        writer.writerow(cleaned_row)




    print("Benchmark complete. Results saved to results.csv")

