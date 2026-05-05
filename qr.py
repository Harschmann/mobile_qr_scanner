import sqlite3
from db import DB_PATH

def list_scans(limit=20):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, qr_value, timestamp, image_path FROM scans ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    for r in rows:
        print(f"[{r[0]}] {r[2]}  QR={r[1]}  File={r[3]}")

if __name__ == "__main__":
    list_scans()
