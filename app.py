import streamlit as st
import pandas as pd
import io
import time

from utils.cleaner import clean_raw_data
from utils.extractor import extract_province, extract_line_contact, convert_thai_date
from utils.database import init_db, save_batch, get_all_batches, check_duplicate_filename, delete_batch, get_summary_stats, clear_data_cache

# สร้าง Database ถ้ายังไม่มี (ปลอดภัย — ถ้ามีอยู่แล้วจะไม่ทำอะไร)
init_db()

# ─── Page Config ──────────────────────────────────────────
st.set_page_config(
    page_title="POT Data Processing",
    page_icon="⚙️",
    layout="wide",
)

# ─── Custom CSS ───────────────────────────────────────────
st.markdown("""
<style>
    .main-header { font-size: 2rem; font-weight: 700; }
    .step-box {
        background: linear-gradient(135deg, #667eea11, #764ba211);
        border-left: 4px solid #667eea;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.6rem;
    }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────
st.title("⚙️ ระบบประมวลผลข้อมูลบุหรี่ไฟฟ้าอัตโนมัติ")
st.markdown("""
ระบบนี้ช่วยจัดการไฟล์ข้อมูลดิบ (Raw Data) ให้พร้อมใช้งาน  
โดยทำ **4 ขั้นตอนต่อเนื่อง** อัตโนมัติ:  
> 🧹 คลีนข้อมูล ➡️ 📍 สกัดจังหวัด ➡️ 📱 สกัดไอดีไลน์ ➡️ 📅 แปลงวันที่
""")

st.divider()

# ─── File Upload ──────────────────────────────────────────
uploaded_file = st.file_uploader(
    "📂 อัปโหลดไฟล์ Raw Excel (.xlsx)",
    type=["xlsx"],
    help="ไฟล์ Raw ที่มีหลาย Sheet (เช่น sheet หลัก + sheet website)"
)

if uploaded_file is not None:
    st.info(f"📄 ได้รับไฟล์: **{uploaded_file.name}** — กำลังเริ่มประมวลผล...")

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # ═══════════════════════════════════════════════════
        # ขั้นตอนที่ 1: คลีนข้อมูล
        # ═══════════════════════════════════════════════════
        status_text.markdown("**🧹 ขั้นตอน 1/4:** กำลังคลีนข้อมูล (อ่าน Sheet, รวมข้อมูล, ลบคอลัมน์/แถวขยะ)...")
        df_cleaned, skipped_sheets = clean_raw_data(uploaded_file)
        progress_bar.progress(25)

        # แจ้งผู้ใช้ว่ามี Sheet ไหนถูกข้ามไป
        if skipped_sheets:
            st.warning(f"⚠️ Sheet ที่ไม่มีข้อมูล (ข้ามอัตโนมัติ): **{', '.join(skipped_sheets)}**")

        # ═══════════════════════════════════════════════════
        # ขั้นตอนที่ 2: สกัดจังหวัด
        # ═══════════════════════════════════════════════════
        status_text.markdown("**📍 ขั้นตอน 2/4:** กำลังสกัดชื่อจังหวัดจากคอลัมน์ 'ผู้เผยแพร่'...")
        if 'ผู้เผยแพร่' in df_cleaned.columns:
            df_cleaned['Province'] = df_cleaned['ผู้เผยแพร่'].apply(extract_province)
        else:
            st.warning("⚠️ ไม่พบคอลัมน์ 'ผู้เผยแพร่' — ข้ามการสกัดจังหวัด")
            df_cleaned['Province'] = None
        progress_bar.progress(50)

        # ═══════════════════════════════════════════════════
        # ขั้นตอนที่ 3: สกัดไอดีไลน์
        # ═══════════════════════════════════════════════════
        status_text.markdown("**📱 ขั้นตอน 3/4:** กำลังสกัด Line ID จากคอลัมน์ 'เนื้อหาโพสต์'...")
        if 'เนื้อหาโพสต์' in df_cleaned.columns:
            df_cleaned['Line_Contact'] = df_cleaned['เนื้อหาโพสต์'].apply(extract_line_contact)
        else:
            st.warning("⚠️ ไม่พบคอลัมน์ 'เนื้อหาโพสต์' — ข้ามการสกัดไอดีไลน์")
            df_cleaned['Line_Contact'] = None
        progress_bar.progress(75)

        # ═══════════════════════════════════════════════════
        # ขั้นตอนที่ 4: แปลงวันที่
        # ═══════════════════════════════════════════════════
        status_text.markdown("**📅 ขั้นตอน 4/4:** กำลังแปลงรูปแบบวันที่ไทย...")
        if 'วันที่จัดเก็บ' in df_cleaned.columns:
            df_cleaned['Date'] = df_cleaned['วันที่จัดเก็บ'].apply(convert_thai_date)
            df_cleaned['Date'] = pd.to_datetime(df_cleaned['Date'], errors='coerce')
        else:
            st.warning("⚠️ ไม่พบคอลัมน์ 'วันที่จัดเก็บ' — ข้ามการแปลงวันที่")
            df_cleaned['Date'] = None
        progress_bar.progress(100)

        status_text.success("✅ ประมวลผลเสร็จสมบูรณ์ทั้ง 4 ขั้นตอน!")

        # ═══════════════════════════════════════════════════
        # สรุปผล
        # ═══════════════════════════════════════════════════
        st.divider()
        st.subheader("📊 สรุปผลการประมวลผล")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📋 จำนวนแถวทั้งหมด", f"{len(df_cleaned):,}")
        col2.metric("📍 จังหวัดที่สกัดได้", f"{df_cleaned['Province'].notna().sum():,}")
        col3.metric("📱 Line ID ที่สกัดได้", f"{df_cleaned['Line_Contact'].notna().sum():,}")

        if df_cleaned['Date'].notna().any():
            col4.metric("📅 วันที่แปลงได้", f"{df_cleaned['Date'].notna().sum():,}")
        else:
            col4.metric("📅 วันที่แปลงได้", "0")

        # ─── แสดงตัวอย่างผลลัพธ์ ──────────────────────────
        st.markdown("#### 🔍 ตัวอย่างผลลัพธ์ (10 แถวแรก)")
        display_cols = ['ลำดับ', 'ผู้เผยแพร่', 'Province', 'Line_Contact', 'วันที่จัดเก็บ', 'Date', 'source_sheet']
        existing_display = [c for c in display_cols if c in df_cleaned.columns]
        st.dataframe(df_cleaned[existing_display].head(10), use_container_width=True)

        # ─── แสดงคอลัมน์ทั้งหมดที่เหลือหลังคลีน ──────────
        with st.expander("📑 ดูรายชื่อคอลัมน์ทั้งหมดที่เหลือหลังคลีน"):
            st.write(list(df_cleaned.columns))

        # ─── ปุ่มดาวน์โหลด ─────────────────────────────────
        st.divider()
        st.subheader("📥 ดาวน์โหลดไฟล์ผลลัพธ์")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_cleaned.to_excel(writer, index=False, sheet_name='Result')

        st.download_button(
            label="⬇️ ดาวน์โหลดไฟล์ Excel (.xlsx)",
            data=output.getvalue(),
            file_name="POT_Cleaned_and_Extracted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

        st.caption("💡 ไฟล์นี้สามารถนำไปใช้ในหน้า **📊 สร้างกราฟ** ได้เลย!")

        # ═══════════════════════════════════════════════════
        # ขั้นตอนที่ 5: บันทึกเข้า Database
        # ═══════════════════════════════════════════════════
        st.divider()
        st.subheader("💾 บันทึกเข้า Database")
        st.markdown("บันทึกข้อมูลที่คลีนแล้วเข้า Database เพื่อใช้ในหน้า **📊 สร้างกราฟ** ได้ทันที โดยไม่ต้องอัปโหลดไฟล์ซ้ำ")

        # ตรวจสอบไฟล์ซ้ำ
        existing = check_duplicate_filename(uploaded_file.name)
        if not existing.empty:
            st.warning(
                f"⚠️ ไฟล์ชื่อ **{uploaded_file.name}** เคยอัปโหลดมาแล้ว "
                f"({len(existing)} ครั้ง) — กดบันทึกอีกครั้งจะเก็บเป็นชุดข้อมูลแยก"
            )

        if st.button("💾 บันทึกข้อมูลเข้า Database", type="primary", use_container_width=True):
            with st.spinner("กำลังบันทึกข้อมูลเข้า Database..."):
                try:
                    result = save_batch(uploaded_file.name, df_cleaned, skipped_sheets)
                    batch_id = result['batch_id']
                    inserted = result['inserted']
                    skipped = result['skipped_dup']

                    if skipped > 0:
                        st.success(
                            f"✅ บันทึกเข้า Database สำเร็จ! (Batch ID: {batch_id})\n\n"
                            f"📥 บันทึกใหม่: **{inserted:,}** แถว | "
                            f"⏭️ ข้ามซ้ำ: **{skipped:,}** แถว"
                        )
                    else:
                        st.success(f"✅ บันทึกเข้า Database สำเร็จ! (Batch ID: {batch_id}, จำนวน: {inserted:,} แถว)")
                    st.balloons()
                except Exception as db_err:
                    st.error(f"❌ บันทึกเข้า Database ไม่สำเร็จ: {str(db_err)}")

    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        st.info("🔎 กรุณาตรวจสอบว่าไฟล์เป็น Raw Data ที่ถูกต้อง และมีหัวคอลัมน์อยู่ที่แถวที่ 3")

# ═══════════════════════════════════════════════════════════
# ส่วนแสดงประวัติการอัปโหลด (แสดงเสมอ ไม่ว่าจะอัปโหลดไฟล์หรือไม่)
# ═══════════════════════════════════════════════════════════
st.divider()
st.subheader("📚 ประวัติการอัปโหลดทั้งหมด")

batches_df = get_all_batches()
if not batches_df.empty:
    # แสดงสถิติภาพรวม
    stats = get_summary_stats()
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("📁 จำนวนไฟล์ใน DB", stats['total_batches'])
    col_s2.metric("📋 โพสต์ทั้งหมด", f"{stats['total_posts']:,}")
    col_s3.metric("📍 จังหวัดที่พบ", stats['unique_provinces'])
    col_s4.metric("📱 Line ID ทั้งหมด", f"{stats['total_line_contacts']:,}")

    # ─── แสดงตารางแบบแบ่งหน้า (Pagination) ───
    import math
    ROWS_PER_PAGE = 10

    if 'batch_page' not in st.session_state:
        st.session_state.batch_page = 1

    total_pages = math.ceil(len(batches_df) / ROWS_PER_PAGE)
    if st.session_state.batch_page > total_pages and total_pages > 0:
        st.session_state.batch_page = total_pages
        
    start_idx = (st.session_state.batch_page - 1) * ROWS_PER_PAGE
    end_idx = start_idx + ROWS_PER_PAGE
    page_df = batches_df.iloc[start_idx:end_idx]

    st.dataframe(
        page_df[['id', 'filename', 'uploaded_at', 'cleaned_rows', 'provinces_found', 'line_ids_found', 'status']],
        use_container_width=True,
        hide_index=True,
        column_config={
            'id': st.column_config.NumberColumn('ID', width='small'),
            'filename': st.column_config.TextColumn('ชื่อไฟล์'),
            'uploaded_at': st.column_config.TextColumn('วันที่อัปโหลด'),
            'cleaned_rows': st.column_config.NumberColumn('จำนวนแถว', format="%d"),
            'provinces_found': st.column_config.NumberColumn('จังหวัด', format="%d"),
            'line_ids_found': st.column_config.NumberColumn('Line ID', format="%d"),
            'status': st.column_config.TextColumn('สถานะ'),
        }
    )

    # ปุ่มเปลี่ยนหน้าสำหรับตาราง
    if total_pages > 1:
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("◀ ก่อนหน้า", disabled=(st.session_state.batch_page <= 1), key='btn_prev_batch'):
                st.session_state.batch_page -= 1
                st.rerun()
        with col_info:
            st.markdown(f"<div style='text-align: center;'><b>หน้า {st.session_state.batch_page} / {total_pages}</b></div>", unsafe_allow_html=True)
        with col_next:
            if st.button("ถัดไป ▶", disabled=(st.session_state.batch_page >= total_pages), key='btn_next_batch'):
                st.session_state.batch_page += 1
                st.rerun()

    # ลบ Batch
    with st.expander("🗑️ ลบชุดข้อมูล"):
        if 'del_page' not in st.session_state:
            st.session_state.del_page = 1
            
        total_del_pages = math.ceil(len(batches_df) / ROWS_PER_PAGE)
        if st.session_state.del_page > total_del_pages and total_del_pages > 0:
            st.session_state.del_page = total_del_pages
            
        start_del_idx = (st.session_state.del_page - 1) * ROWS_PER_PAGE
        end_del_idx = start_del_idx + ROWS_PER_PAGE
        del_page_df = batches_df.iloc[start_del_idx:end_del_idx]
        
        del_options = [f"#{row['id']} — {row['filename']} ({row['cleaned_rows']:,} แถว)" for _, row in del_page_df.iterrows()]
        selected_del = st.selectbox("เลือกชุดข้อมูลที่ต้องการลบ (แสดงหน้าละ 10 รายการ)", del_options, key='del_batch')
        
        if total_del_pages > 1:
            col_dprev, col_dinfo, col_dnext = st.columns([1, 2, 1])
            with col_dprev:
                if st.button("◀ ก่อนหน้า", disabled=(st.session_state.del_page <= 1), key='btn_prev_del'):
                    st.session_state.del_page -= 1
                    st.rerun()
            with col_dinfo:
                st.markdown(f"<div style='text-align: center;'><b>หน้า {st.session_state.del_page} / {total_del_pages}</b></div>", unsafe_allow_html=True)
            with col_dnext:
                if st.button("ถัดไป ▶", disabled=(st.session_state.del_page >= total_del_pages), key='btn_next_del'):
                    st.session_state.del_page += 1
                    st.rerun()
                    
        if st.button("🗑️ ลบชุดข้อมูลนี้", type="secondary", key='btn_del_confirm'):
            if selected_del:
                del_id = int(selected_del.split("#")[1].split(" ")[0])
                if delete_batch(del_id):
                    st.success(f"✅ ลบ {selected_del} สำเร็จ!")
                    st.rerun()
                else:
                    st.error("❌ ไม่พบชุดข้อมูลนี้")
else:
    st.info("ℹ️ ยังไม่มีข้อมูลใน Database — อัปโหลดไฟล์แล้วกดปุ่ม 💾 บันทึกเข้า Database")
