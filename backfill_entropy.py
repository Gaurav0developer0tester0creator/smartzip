import sqlite3
import os
import sys
import compressors
from smartzip_catalog import calculate_entropy

DB_FILE = "smartzip_catalog.db"

def backfill_entropy(recalc_all=False, check_only=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Count total rows
    c.execute("SELECT COUNT(*) FROM files")
    total_rows = c.fetchone()[0]

    if recalc_all:
        c.execute("SELECT id, file_name, algo FROM files")
        rows = c.fetchall()
        print(f"🔄 Recalculating entropy for ALL {len(rows)} rows...")
    else:
        c.execute("SELECT id, file_name, algo FROM files WHERE entropy IS NULL")
        rows = c.fetchall()
        if not rows:
            print(f"✅ No missing entropy values. Catalog already clean ({total_rows} rows).")
            conn.close()
            return
        print(f"📊 Catalog rows: {total_rows}")
        print(f"🔍 Found {len(rows)} rows with missing entropy.")

    if check_only:
        print("\n📋 Missing entropy rows:")
        for row in rows:
            print(f" - id={row[0]}, file={row[1]}, algo={row[2]}")
        print("\nℹ️ Check-only mode: no changes made.")
        conn.close()
        return

    updated = 0
    skipped = 0

    for row in rows:
        file_id, file_name, algo = row
        comp_file = os.path.join("compressed", f"{file_name}.{algo}")

        if not os.path.exists(comp_file):
            print(f"⚠️ Skipping id={file_id} ({comp_file} not found)")
            skipped += 1
            continue

        try:
            # Decompress
            decompressor = getattr(compressors, f"decompress_{algo}")
            with open(comp_file, "rb") as f:
                compressed_data = f.read()
            data = decompressor(compressed_data)

            # Calculate entropy
            entropy = calculate_entropy(data)

            # Update DB
            c.execute("UPDATE files SET entropy=? WHERE id=?", (entropy, file_id))
            if recalc_all:
                print(f"🔄 Recalculated id={file_id} -> entropy={entropy:.3f}")
            else:
                print(f"✔️ Updated id={file_id} -> entropy={entropy:.3f}")
            updated += 1
        except Exception as e:
            print(f"❌ Failed id={file_id}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print("\n🎉 Backfill complete.")
    print(f"   ➕ Updated: {updated}")
    print(f"   ⚠️ Skipped: {skipped}")
    print(f"   📊 Total rows: {total_rows}")


if __name__ == "__main__":
    recalc_all = "--recalc-all" in sys.argv
    check_only = "--check-only" in sys.argv
    backfill_entropy(recalc_all=recalc_all, check_only=check_only)
