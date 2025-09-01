import sqlite3
import statistics

DB_FILE = "smartzip_catalog.db"

def catalog_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Count rows
    c.execute("SELECT COUNT(*) FROM files")
    total_rows = c.fetchone()[0]
    print(f"📊 Catalog contains {total_rows} rows.")

    if total_rows == 0:
        print("⚠️ No entries found.")
        return

    # Global entropy stats
    c.execute("SELECT entropy FROM files WHERE entropy IS NOT NULL")
    entropies = [row[0] for row in c.fetchall()]
    if entropies:
        print("\n🌐 Global Entropy Stats")
        print(f" - Avg entropy: {statistics.mean(entropies):.3f}")
        print(f" - Min entropy: {min(entropies):.3f}")
        print(f" - Max entropy: {max(entropies):.3f}")

    # Per-algorithm stats
    c.execute("SELECT DISTINCT algo FROM files")
    algos = [row[0] for row in c.fetchall()]
    print("\n⚙️ Per-Algorithm Stats")
    for algo in algos:
        c.execute("""
            SELECT entropy, compression_ratio
            FROM files WHERE algo=? AND entropy IS NOT NULL
        """, (algo,))
        rows = c.fetchall()
        if not rows:
            continue
        entropies = [r[0] for r in rows]
        ratios = [r[1] for r in rows]
        print(f"\n🔹 {algo.upper()}")
        print(f"   - Files: {len(rows)}")
        print(f"   - Avg entropy: {statistics.mean(entropies):.3f}")
        print(f"   - Min entropy: {min(entropies):.3f}")
        print(f"   - Max entropy: {max(entropies):.3f}")
        print(f"   - Avg ratio: {statistics.mean(ratios):.4f}")
        print(f"   - Best ratio: {min(ratios):.4f}")
        print(f"   - Worst ratio: {max(ratios):.4f}")

    conn.close()

if __name__ == "__main__":
    catalog_stats()
