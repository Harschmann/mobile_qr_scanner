import sqlite3
import os

DB_PATH = "qr_scan.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            qr_value    TEXT NOT NULL,
            timestamp   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            image_path  TEXT NOT NULL,
            image_blob  BLOB         -- optional: store image bytes directly
        )
    """)
    conn.commit()
    conn.close()

def save_scan(qr_value: str, image_path: str, image_blob: bytes = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO scans (qr_value, image_path, image_blob) VALUES (?, ?, ?)",
        (qr_value, image_path, image_blob)
    )
    conn.commit()
    conn.close()
