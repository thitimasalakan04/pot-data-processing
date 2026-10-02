import pandas as pd


def clean_raw_data(uploaded_file) -> pd.DataFrame:
    """
    ฟังก์ชันคลีนข้อมูลจากไฟล์ Raw Excel (หลายชีท)

    ขั้นตอน:
    1. อ่านทุก Sheet ด้วย header=2 (หัวคอลัมน์อยู่แถวที่ 3 ใน Excel)
    2. กรอง Sheet ที่ว่าง (เช่น 'website' ที่บางทีไม่มีข้อมูล)
    3. รวมข้อมูลทุก Sheet เป็น DataFrame เดียว
    4. ลบแถวที่เป็นหัวข้อซ้ำ (จากการ merge ข้าม sheet)
    5. ลบคอลัมน์ที่ไม่ต้องการ
    6. สร้างคอลัมน์ 'ลำดับ' ใหม่
    """

    # ─── 1. อ่านทุก Sheet ─────────────────────────────────
    # header=2 เพราะชื่อคอลัมน์จริงอยู่ที่แถวที่ 3 ใน Excel (0-indexed = 2)
    all_sheets = pd.read_excel(uploaded_file, header=2, sheet_name=None)

    df_list = []

    # ─── 2. กรอง Sheet ที่ว่าง ────────────────────────────
    skipped_sheets = []
    for sheet_name, df in all_sheets.items():
        if df is None or df.empty or len(df) == 0:
            skipped_sheets.append(sheet_name)
            continue

        # เช็คเพิ่ม: ถ้ามีแค่ NaN ทั้งหมด ถือว่าว่าง
        if df.dropna(how='all').empty:
            skipped_sheets.append(sheet_name)
            continue

        # เพิ่มคอลัมน์ source_sheet เผื่อใช้ในอนาคต
        df['source_sheet'] = sheet_name
        df_list.append(df)

    if not df_list:
        raise ValueError(
            "ไม่พบข้อมูลในไฟล์ Excel ที่อัปโหลด — "
            "ทุก Sheet ว่างเปล่า กรุณาตรวจสอบไฟล์อีกครั้ง"
        )

    # ─── 3. รวมข้อมูลทุก Sheet ────────────────────────────
    df_raw = pd.concat(df_list, ignore_index=True)

    # ─── 4. ลบแถวหัวข้อซ้ำ ────────────────────────────────
    # กรณี merge หลาย Sheet จะมีแถวที่เป็นชื่อ header ติดเข้ามาด้วย
    # ตรวจจับโดยดูคอลัมน์แรก ถ้ามีคำว่า 'ลำดับ' = แถว header ซ้ำ → ลบทิ้ง
    first_col = df_raw.columns[0]
    mask_header_row = df_raw[first_col].astype(str).str.contains('ลำดับ', na=False)
    df_raw = df_raw[~mask_header_row]

    # ─── 5. ลบคอลัมน์ที่ไม่ต้องการ ────────────────────────
    cols_to_drop = [
        'ลำดับ',
        'Keyword ที่จับคู่ได้',
        'หัวเรื่อง (Title)',
        'URL ไลน์ (lineUrl)',
        'หน่วยงาน (Agency)',
        'Website',
        '1',                      # คอลัมน์ตัวเลข 1 ที่ติดมา
        'URL ไฟล์ประกอบ  (2)',
        'URL ไฟล์ประกอบ  (3)',
        'ไฟล์ประกอบ  (2)',
        'ไฟล์ประกอบ  (3)',
    ]

    # ลบเฉพาะคอลัมน์ที่มีอยู่จริง (กันไม่ให้ Error)
    existing_cols_to_drop = [c for c in cols_to_drop if c in df_raw.columns]
    df_clean = df_raw.drop(columns=existing_cols_to_drop)

    # ลบแถวที่ว่างทุกคอลัมน์
    df_clean = df_clean.dropna(how='all')

    # Reset index
    df_clean = df_clean.reset_index(drop=True)

    # ─── 6. สร้างคอลัมน์ 'ลำดับ' ใหม่ ────────────────────
    df_clean.insert(0, 'ลำดับ', range(1, len(df_clean) + 1))

    return df_clean, skipped_sheets
