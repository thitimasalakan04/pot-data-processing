"""
database.py — โมดูลจัดการ Database สำหรับระบบประมวลผลข้อมูล กอง ปท.

ไฟล์นี้รวมฟังก์ชันทั้งหมดที่เกี่ยวกับ Database ไว้ที่เดียว
ถ้าอนาคตต้องการเปลี่ยน Database (เช่น ย้ายไป PostgreSQL) → แก้ไฟล์นี้ไฟล์เดียว

ใช้ SQLite เป็น Database Engine:
- ไม่ต้องติดตั้ง Server แยก
- ข้อมูลทั้งหมดเก็บอยู่ในไฟล์ .db ไฟล์เดียว
- Python มี sqlite3 มาให้ในตัว
"""

import sqlite3
import pandas as pd
import json
import hashlib
import os
from datetime import datetime
import streamlit as st


def compute_post_hash(post_url):
    """
    สร้าง Hash จาก URL โพสต์ เพื่อใช้ป้องกันข้อมูลซ้ำซ้อน
    - ใช้ URL เพราะแต่ละโพสต์มี URL ไม่ซ้ำกันโดยธรรมชาติ
    - เก็บความถี่ได้ครบ (คนเดียวโพสต์ 10 กลุ่ม = 10 URL = 10 แถว)
    - ป้องกันอัปโหลดไฟล์ซ้ำ (URL เดิม = Hash เดิม = ข้าม)
    """
    url = str(post_url).strip() if post_url and str(post_url).strip() not in ('None', 'nan', '') else ''
    return hashlib.md5(url.encode('utf-8')).hexdigest()

# ─── กำหนดที่อยู่ไฟล์ Database ───────────────────────────
# เก็บไฟล์ DB ไว้ในโฟลเดอร์ data/ ของโปรเจกต์
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),  # utils/
    '..',                                         # ขึ้นไป 1 ระดับ
    'data',                                       # โฟลเดอร์ data/
    'pot_data.db'                                  # ชื่อไฟล์ Database
)
# Normalize path ให้เป็นมาตรฐาน
DB_PATH = os.path.normpath(DB_PATH)


# ═══════════════════════════════════════════════════════════
# การเชื่อมต่อ Database
# ═══════════════════════════════════════════════════════════

def get_connection():
    """
    เปิดการเชื่อมต่อกับ Database

    - ถ้าไฟล์ .db ยังไม่มี → SQLite จะสร้างให้อัตโนมัติ
    - ถ้ามีอยู่แล้ว → เปิดไฟล์เดิม (ข้อมูลไม่หาย)
    """
    # สร้างโฟลเดอร์ data/ ถ้ายังไม่มี
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    # เปิด Foreign Key support
    conn.execute("PRAGMA foreign_keys = ON")

    # ให้ผลลัพธ์ row เข้าถึงด้วยชื่อคอลัมน์ได้ (เช่น row['filename'])
    conn.row_factory = sqlite3.Row

    return conn


# ═══════════════════════════════════════════════════════════
# สร้างตาราง (Schema)
# ═══════════════════════════════════════════════════════════

def init_db():
    """
    สร้างตารางทั้งหมดใน Database (ถ้ายังไม่มี)

    - CREATE TABLE IF NOT EXISTS = ถ้ามีตารางอยู่แล้ว ไม่ทำอะไร (ข้อมูลไม่หาย)
    - ถ้ายังไม่มี = สร้างตารางใหม่

    เรียกฟังก์ชันนี้ทุกครั้งตอนเปิดเว็บ → ปลอดภัยเสมอ
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ─── ตาราง upload_batches ─────────────────────────
    # เก็บประวัติการอัปโหลดไฟล์ (เหมือนใบปะหน้า)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS upload_batches (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT    NOT NULL,
            uploaded_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_rows      INTEGER DEFAULT 0,
            cleaned_rows    INTEGER DEFAULT 0,
            provinces_found INTEGER DEFAULT 0,
            line_ids_found  INTEGER DEFAULT 0,
            status          TEXT    DEFAULT 'completed',
            notes           TEXT
        )
    """)

    # ─── ตาราง posts ─────────────────────────────────
    # เก็บข้อมูลโพสต์ที่ผ่านการคลีนแล้ว (ตัวข้อมูลจริง)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id        INTEGER NOT NULL,
            publisher       TEXT,
            post_content    TEXT,
            province        TEXT,
            line_contact    TEXT,
            date_collected  TEXT,
            date_parsed     DATE,
            source_sheet    TEXT,
            channel         TEXT,
            extra_data      TEXT,
            FOREIGN KEY (batch_id) REFERENCES upload_batches(id)
                ON DELETE CASCADE
        )
    """)

    # ─── ตาราง processing_logs ───────────────────────
    # บันทึกขั้นตอนการประมวลผล (สำหรับ Debug)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id        INTEGER NOT NULL,
            step_name       TEXT    NOT NULL,
            status          TEXT    DEFAULT 'success',
            message         TEXT,
            rows_affected   INTEGER DEFAULT 0,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (batch_id) REFERENCES upload_batches(id)
                ON DELETE CASCADE
        )
    """)

    # ─── สร้าง Index (ดัชนีค้นหา) ────────────────────
    # ทำให้ค้นหาข้อมูลตาม province, date_parsed เร็วขึ้นมาก
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_province ON posts(province)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_date     ON posts(date_parsed)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_batch    ON posts(batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_line     ON posts(line_contact)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_batch     ON processing_logs(batch_id)")

    # ─── Migration: เพิ่มระบบ Hash กันซ้ำ ─────────────
    # ตรวจว่าคอลัมน์ post_hash มีอยู่แล้วหรือยัง
    cursor.execute("PRAGMA table_info(posts)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    if 'post_hash' not in existing_columns:
        print("[DB Migration] Adding post_hash column...")

        # 1) เพิ่มคอลัมน์
        cursor.execute("ALTER TABLE posts ADD COLUMN post_hash TEXT")

        # 2) คำนวณ Hash ย้อนหลังให้ข้อมูลเก่าทั้งหมด
        cursor.execute("SELECT id, extra_data FROM posts")
        rows = cursor.fetchall()
        for row in rows:
            post_url = ''
            if row[1]:  # extra_data is not NULL
                ed = json.loads(row[1])
                post_url = ed.get('รายการโดเมนเนมหรือยูอาร์แอล\n(Domain name/URL)', '')
            h = compute_post_hash(post_url)
            cursor.execute("UPDATE posts SET post_hash = ? WHERE id = ?", (h, row[0]))

        # 3) ลบแถวที่ Hash ซ้ำกัน (เก็บแถวที่มี id น้อยสุด = แถวแรกที่เข้ามา)
        cursor.execute("""
            DELETE FROM posts
            WHERE id NOT IN (
                SELECT MIN(id) FROM posts GROUP BY post_hash
            )
        """)
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            print(f"[DB Migration] Removed {deleted_count} duplicate rows")

        # 4) สร้าง Unique Index
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_hash ON posts(post_hash)")
        print("[DB Migration] Unique Index created successfully")
    else:
        # กรณีคอลัมน์มีแล้ว แต่ Index ยังไม่มี (เผื่อ edge case)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_hash ON posts(post_hash)")

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════
# C — CREATE: บันทึกข้อมูลเข้า Database
# ═══════════════════════════════════════════════════════════

def save_batch(filename, df_cleaned, skipped_sheets=None):
    """
    บันทึก DataFrame ที่คลีนแล้วเข้า Database (พร้อมระบบกันซ้ำด้วย Hash)

    Parameters:
        filename (str): ชื่อไฟล์ที่อัปโหลด เช่น "data_jan.xlsx"
        df_cleaned (DataFrame): ข้อมูลที่ผ่านการคลีน + สกัดจังหวัด + Line ID แล้ว
        skipped_sheets (list): รายชื่อ Sheet ที่ถูกข้าม (ถ้ามี)

    Returns:
        dict: ผลลัพธ์การบันทึก {
            'batch_id': int,
            'total_rows': int,      # จำนวนแถวทั้งหมดในไฟล์
            'inserted': int,        # จำนวนแถวที่บันทึกจริง (ไม่ซ้ำ)
            'skipped_dup': int,     # จำนวนแถวที่ข้ามเพราะซ้ำ
        }
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # ─── ขั้นตอนที่ 1: บันทึกข้อมูล Batch (ใบปะหน้า) ───
        provinces_found = 0
        line_ids_found = 0

        if 'Province' in df_cleaned.columns:
            provinces_found = int(df_cleaned['Province'].notna().sum())
        if 'Line_Contact' in df_cleaned.columns:
            line_ids_found = int(df_cleaned['Line_Contact'].notna().sum())

        notes = None
        if skipped_sheets:
            notes = f"Skipped sheets: {', '.join(skipped_sheets)}"

        cursor.execute("""
            INSERT INTO upload_batches
                (filename, total_rows, cleaned_rows, provinces_found, line_ids_found, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            filename,
            len(df_cleaned),
            0,  # จะอัปเดตเป็นจำนวนที่ INSERT จริงทีหลัง
            provinces_found,
            line_ids_found,
            notes,
        ))

        batch_id = cursor.lastrowid

        # ─── Log: เริ่มบันทึก ──────────────────────────
        cursor.execute("""
            INSERT INTO processing_logs (batch_id, step_name, status, message, rows_affected)
            VALUES (?, 'save_to_db', 'started', 'เริ่มบันทึกข้อมูลเข้า Database', ?)
        """, (batch_id, len(df_cleaned)))

        # ─── ขั้นตอนที่ 2: บันทึกข้อมูลโพสต์ (พร้อม Hash กันซ้ำ) ───
        known_cols = {
            'ผู้เผยแพร่', 'เนื้อหาโพสต์', 'Province', 'Line_Contact',
            'วันที่จัดเก็บ', 'Date', 'source_sheet',
            'ช่องทาง (Channel)', 'ลำดับ',
        }

        # ฟังก์ชันช่วย: แปลง NaN/None → None
        def safe_val(val):
            if val is None:
                return None
            if isinstance(val, float) and pd.isna(val):
                return None
            return val

        inserted_count = 0
        total_rows = len(df_cleaned)

        for _, row in df_cleaned.iterrows():
            # เก็บคอลัมน์ที่ไม่ได้อยู่ใน known_cols เป็น extra_data (JSON)
            extra = {}
            for col in df_cleaned.columns:
                if col not in known_cols and pd.notna(row.get(col)):
                    val = row[col]
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    elif isinstance(val, (int, float)):
                        if pd.isna(val):
                            continue
                        val = val
                    else:
                        val = str(val)
                    extra[col] = val

            extra_json = json.dumps(extra, ensure_ascii=False) if extra else None

            # แปลง Date
            date_parsed = None
            date_val = row.get('Date')
            if pd.notna(date_val):
                try:
                    date_parsed = str(pd.to_datetime(date_val).date())
                except Exception:
                    date_parsed = None

            # หาค่า channel
            channel = row.get('ช่องทาง (Channel)')
            channel_is_empty = (channel is None) or (isinstance(channel, float) and pd.isna(channel)) or (channel == '')
            if channel_is_empty:
                channel = row.get('source_sheet')

            publisher = safe_val(row.get('ผู้เผยแพร่'))
            post_content = safe_val(row.get('เนื้อหาโพสต์'))

            # ─── ดึง URL โพสต์จาก extra_data สำหรับ Hash ───
            post_url = extra.get('รายการโดเมนเนมหรือยูอาร์แอล\n(Domain name/URL)', '')
            # ─── สร้าง Hash จาก URL โพสต์ ───
            post_hash = compute_post_hash(post_url)

            # INSERT OR IGNORE: ถ้า Hash ซ้ำ → ข้ามแถวนี้โดยอัตโนมัติ
            cursor.execute("""
                INSERT OR IGNORE INTO posts
                    (batch_id, publisher, post_content, province, line_contact,
                     date_collected, date_parsed, source_sheet, channel, extra_data, post_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                batch_id,
                publisher,
                post_content,
                safe_val(row.get('Province')),
                safe_val(row.get('Line_Contact')),
                safe_val(row.get('วันที่จัดเก็บ')),
                date_parsed,
                safe_val(row.get('source_sheet')),
                safe_val(channel),
                extra_json,
                post_hash,
            ))

            # rowcount = 1 ถ้า INSERT สำเร็จ, 0 ถ้าถูก IGNORE (ซ้ำ)
            if cursor.rowcount > 0:
                inserted_count += 1

        skipped_dup = total_rows - inserted_count

        # ─── อัปเดต cleaned_rows ใน batch ให้ตรงกับจำนวนที่ INSERT จริง ───
        cursor.execute("""
            UPDATE upload_batches SET cleaned_rows = ? WHERE id = ?
        """, (inserted_count, batch_id))

        # ─── Log: สำเร็จ ───────────────────────────────
        log_msg = f'บันทึกสำเร็จ {inserted_count}/{total_rows} แถว'
        if skipped_dup > 0:
            log_msg += f' (ข้ามซ้ำ {skipped_dup} แถว)'

        cursor.execute("""
            INSERT INTO processing_logs (batch_id, step_name, status, message, rows_affected)
            VALUES (?, 'save_to_db', 'success', ?, ?)
        """, (batch_id, log_msg, inserted_count))

        conn.commit()
        clear_data_cache()  # ← ล้าง cache เพื่อให้หน้ากราฟเห็นข้อมูลใหม่ทันที
        return {
            'batch_id': batch_id,
            'total_rows': total_rows,
            'inserted': inserted_count,
            'skipped_dup': skipped_dup,
        }

    except Exception as e:
        conn.rollback()

        # พยายาม Log error (อาจล้มเหลวถ้า batch_id ยังไม่ถูกสร้าง)
        try:
            if 'batch_id' in dir():
                cursor.execute("""
                    INSERT INTO processing_logs (batch_id, step_name, status, message)
                    VALUES (?, 'save_to_db', 'error', ?)
                """, (batch_id, str(e)))
                conn.commit()
        except Exception:
            pass

        raise e

    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════
# R — READ: ดึงข้อมูลจาก Database
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_all_batches():
    """
    ดึงรายการชุดข้อมูลทั้งหมดที่เคยอัปโหลด

    Returns:
        DataFrame: ตารางแสดงประวัติการอัปโหลดทั้งหมด
    """
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT id, filename, uploaded_at, total_rows, cleaned_rows,
               provinces_found, line_ids_found, status, notes
        FROM upload_batches
        ORDER BY uploaded_at DESC
    """, conn)

    conn.close()
    return df


@st.cache_data(ttl=300)
def get_batch_data(batch_id):
    """
    ดึงข้อมูลโพสต์ทั้งหมดของชุดข้อมูลที่เลือก

    Parameters:
        batch_id (int): รหัสชุดข้อมูลที่ต้องการ

    Returns:
        DataFrame: ข้อมูลโพสต์ทั้งหมดในชุดนั้น (ชื่อคอลัมน์ตรงกับที่หน้ากราฟใช้)
    """
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT publisher     AS 'ผู้เผยแพร่',
               post_content  AS 'เนื้อหาโพสต์',
               province      AS 'Province',
               line_contact  AS 'Line_Contact',
               date_collected AS 'วันที่จัดเก็บ',
               date_parsed   AS 'Date',
               source_sheet,
               channel       AS 'ช่องทาง (Channel)'
        FROM posts
        WHERE batch_id = ?
    """, conn, params=[batch_id])

    # แปลง Date เป็น datetime ให้พร้อมใช้งาน
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    conn.close()
    return df


@st.cache_data(ttl=300)
def get_all_data():
    """
    ดึงข้อมูลโพสต์ทั้งหมดจากทุกชุดข้อมูล (รวมทุก Batch)

    Returns:
        DataFrame: ข้อมูลโพสต์ทั้งหมดในระบบ
    """
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT p.publisher     AS 'ผู้เผยแพร่',
               p.post_content  AS 'เนื้อหาโพสต์',
               p.province      AS 'Province',
               p.line_contact  AS 'Line_Contact',
               p.date_collected AS 'วันที่จัดเก็บ',
               p.date_parsed   AS 'Date',
               p.source_sheet,
               p.channel       AS 'ช่องทาง (Channel)',
               b.filename      AS 'ไฟล์ต้นทาง'
        FROM posts p
        JOIN upload_batches b ON p.batch_id = b.id
        ORDER BY p.date_parsed DESC
    """, conn)

    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

    conn.close()
    return df


@st.cache_data(ttl=300)
def get_summary_stats():
    """
    สถิติภาพรวมของ Database ทั้งหมด

    Returns:
        dict: สถิติต่างๆ เช่น จำนวน batch, จำนวนโพสต์, จังหวัดที่พบ
    """
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM upload_batches")
    stats['total_batches'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM posts")
    stats['total_posts'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT province) FROM posts WHERE province IS NOT NULL")
    stats['unique_provinces'] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM posts WHERE line_contact IS NOT NULL")
    stats['total_line_contacts'] = cursor.fetchone()[0]

    # วันที่เก่าสุด - ใหม่สุด
    cursor.execute("SELECT MIN(date_parsed), MAX(date_parsed) FROM posts WHERE date_parsed IS NOT NULL")
    date_row = cursor.fetchone()
    stats['date_min'] = date_row[0]
    stats['date_max'] = date_row[1]

    conn.close()
    return stats


def get_batch_info(batch_id):
    """
    ดึงข้อมูลรายละเอียดของ Batch เดียว

    Parameters:
        batch_id (int): รหัสชุดข้อมูล

    Returns:
        dict or None: ข้อมูล Batch
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, filename, uploaded_at, total_rows, cleaned_rows,
               provinces_found, line_ids_found, status, notes
        FROM upload_batches
        WHERE id = ?
    """, (batch_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return dict(row)


# ═══════════════════════════════════════════════════════════
# D — DELETE: ลบข้อมูล
# ═══════════════════════════════════════════════════════════

def delete_batch(batch_id):
    """
    ลบชุดข้อมูลออกจาก Database (ทั้ง batch + โพสต์ + logs ทั้งหมดในนั้น)

    Parameters:
        batch_id (int): รหัสชุดข้อมูลที่ต้องการลบ

    Returns:
        bool: True ถ้าลบสำเร็จ, False ถ้าไม่พบ Batch
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ตรวจสอบว่า batch มีอยู่จริง
    cursor.execute("SELECT filename, cleaned_rows FROM upload_batches WHERE id = ?", (batch_id,))
    batch = cursor.fetchone()

    if batch is None:
        conn.close()
        return False

    # ลบ logs ก่อน
    cursor.execute("DELETE FROM processing_logs WHERE batch_id = ?", (batch_id,))
    # ลบ posts
    cursor.execute("DELETE FROM posts WHERE batch_id = ?", (batch_id,))
    # ลบ batch
    cursor.execute("DELETE FROM upload_batches WHERE id = ?", (batch_id,))

    conn.commit()
    conn.close()
    clear_data_cache()  # ← ล้าง cache เพื่อให้ตารางประวัติอัปเดตทันที
    return True


# ═══════════════════════════════════════════════════════════
# ฟังก์ชันเสริม
# ═══════════════════════════════════════════════════════════

def check_duplicate_filename(filename):
    """
    ตรวจสอบว่าเคยอัปโหลดไฟล์ชื่อนี้มาก่อนหรือยัง

    Returns:
        DataFrame: รายการ batch ที่ใช้ชื่อไฟล์เดียวกัน (ว่าง = ไม่เคยอัปโหลด)
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, filename, uploaded_at, cleaned_rows FROM upload_batches WHERE filename = ?",
        conn,
        params=[filename]
    )
    conn.close()
    return df


def get_processing_logs(batch_id=None):
    """
    ดึง log การประมวลผล

    Parameters:
        batch_id (int, optional): ถ้าระบุ จะดึงเฉพาะ log ของ batch นั้น

    Returns:
        DataFrame: ตาราง log
    """
    conn = get_connection()

    if batch_id:
        df = pd.read_sql_query("""
            SELECT l.*, b.filename
            FROM processing_logs l
            JOIN upload_batches b ON l.batch_id = b.id
            WHERE l.batch_id = ?
            ORDER BY l.created_at DESC
        """, conn, params=[batch_id])
    else:
        df = pd.read_sql_query("""
            SELECT l.*, b.filename
            FROM processing_logs l
            JOIN upload_batches b ON l.batch_id = b.id
            ORDER BY l.created_at DESC
            LIMIT 100
        """, conn)

    conn.close()
    return df


def clear_data_cache():
    """
    ล้าง Cache ข้อมูลทั้งหมด — เรียกหลังจากบันทึกหรือลบข้อมูล
    เพื่อให้หน้าเว็บโหลดข้อมูลใหม่จาก DB ทันที
    """
    st.cache_data.clear()


# ═══════════════════════════════════════════════════════════
# ทดสอบ — รันไฟล์นี้โดยตรง: python utils/database.py
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("[DB] Database Module -- Self Test")
    print("=" * 50)

    print("\n[*] Creating Database...")
    init_db()
    print(f"[OK] Database ready at: {os.path.abspath(DB_PATH)}")

    print("\n[*] Current stats:")
    stats = get_summary_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\n[*] All batches:")
    batches = get_all_batches()
    if batches.empty:
        print("   (No data yet -- upload a file via the web app first)")
    else:
        print(f"   Found {len(batches)} batch(es)")

    print("\n[OK] Self Test completed successfully!")
