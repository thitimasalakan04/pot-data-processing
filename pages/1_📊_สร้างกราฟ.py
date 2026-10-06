import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from utils.database import init_db, get_all_batches, get_batch_data, get_all_data, get_summary_stats

# สร้าง Database ถ้ายังไม่มี
init_db()

st.set_page_config(page_title="สร้างกราฟ", page_icon="📊", layout="wide")

# ─── Custom CSS ───────────────────────────────────────────
st.markdown("""
<style>
    .tab-header { font-size: 1.3rem; font-weight: 600; margin-bottom: 1rem; }
    .insight-card {
        background: linear-gradient(135deg, #667eea11, #764ba211);
        border-left: 4px solid #667eea;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.6rem;
    }
    .spike-alert {
        background: linear-gradient(135deg, #ff6b6b11, #ee5a2411);
        border-left: 4px solid #ff6b6b;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.6rem;
    }
</style>
""", unsafe_allow_html=True)

# ─── Helper: find column by partial name match ────────────
def find_column(df, candidates):
    """Find a column by trying exact match first, then partial match."""
    for name in candidates:
        if name in df.columns:
            return name
    for name in candidates:
        for col in df.columns:
            if name in col or col in name:
                return col
    return None

# ─── Thai day/month names ─────────────────────────────────
THAI_DAYS = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
THAI_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
               'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

# ─── Region-Province Mapping (6 ภาค, 77 จังหวัด) ─────────
REGION_PROVINCES = {
    'ภาคเหนือ': [
        'เชียงราย', 'เชียงใหม่', 'น่าน', 'พะเยา', 'แพร่',
        'แม่ฮ่องสอน', 'ลำปาง', 'ลำพูน', 'อุตรดิตถ์',
    ],
    'ภาคตะวันออกเฉียงเหนือ': [
        'กาฬสินธุ์', 'ขอนแก่น', 'ชัยภูมิ', 'นครพนม', 'นครราชสีมา',
        'บึงกาฬ', 'บุรีรัมย์', 'มหาสารคาม', 'มุกดาหาร', 'ยโสธร',
        'ร้อยเอ็ด', 'เลย', 'ศรีสะเกษ', 'สกลนคร', 'สุรินทร์',
        'หนองคาย', 'หนองบัวลำภู', 'อำนาจเจริญ', 'อุดรธานี', 'อุบลราชธานี',
    ],
    'ภาคกลาง': [
        'กรุงเทพมหานคร', 'กำแพงเพชร', 'ชัยนาท', 'นครนายก', 'นครปฐม',
        'นครสวรรค์', 'นนทบุรี', 'ปทุมธานี', 'พระนครศรีอยุธยา', 'พิจิตร',
        'พิษณุโลก', 'เพชรบูรณ์', 'ลพบุรี', 'สมุทรปราการ', 'สมุทรสงคราม',
        'สมุทรสาคร', 'สระบุรี', 'สิงห์บุรี', 'สุโขทัย', 'สุพรรณบุรี',
        'อ่างทอง', 'อุทัยธานี',
    ],
    'ภาคตะวันออก': [
        'จันทบุรี', 'ฉะเชิงเทรา', 'ชลบุรี', 'ตราด',
        'ปราจีนบุรี', 'ระยอง', 'สระแก้ว',
    ],
    'ภาคตะวันตก': [
        'กาญจนบุรี', 'ตาก', 'ประจวบคีรีขันธ์', 'เพชรบุรี', 'ราชบุรี',
    ],
    'ภาคใต้': [
        'กระบี่', 'ชุมพร', 'ตรัง', 'นครศรีธรรมราช', 'นราธิวาส',
        'ปัตตานี', 'พังงา', 'พัทลุง', 'ภูเก็ต', 'ยะลา',
        'ระนอง', 'สงขลา', 'สตูล', 'สุราษฎร์ธานี',
    ],
}

# ═══════════════════════════════════════════════════════════
# Header & File Upload (Shared)
# ═══════════════════════════════════════════════════════════
st.title("📊 กราฟวิเคราะห์ข้อมูล")
st.markdown("""
เลือกแหล่งข้อมูล → เลือกแท็บเพื่อดูกราฟวิเคราะห์  
> 📱 การวิเคราะห์ตามเวลา · 📍การวิเคราะห์ตามพื้นที่  · 📊 การวิเคราะห์ทั่วไป 
""")

st.divider()

# ═══════════════════════════════════════════════════════════
# เลือกแหล่งข้อมูล: จาก Database หรือ อัปโหลดไฟล์
# ═══════════════════════════════════════════════════════════
data_source = st.radio(
    "📂 เลือกแหล่งข้อมูล",
    ["🗄️ จาก Database", "📁 อัปโหลดไฟล์"],
    horizontal=True,
    help="เลือก 'จาก Database' เพื่อดึงข้อมูลที่เคยบันทึกไว้ หรือ 'อัปโหลดไฟล์' เพื่อใช้ไฟล์ใหม่",
)

df = None  # ตัวแปรเก็บข้อมูลที่จะใช้แสดงกราฟ

if data_source == "🗄️ จาก Database":
    # ─── โหลดข้อมูลจาก Database ──────────────────────
    batches = get_all_batches()

    if batches.empty:
        st.info("ℹ️ ยังไม่มีข้อมูลใน Database — กรุณาอัปโหลดและบันทึกข้อมูลที่หน้า **⚙️ ระบบประมวลผล** ก่อน")
        st.stop()

    # แสดงสถิติภาพรวม
    stats = get_summary_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📁 ไฟล์ใน DB", stats['total_batches'])
    c2.metric("📋 โพสต์ทั้งหมด", f"{stats['total_posts']:,}")
    c3.metric("📍 จังหวัดที่พบ", stats['unique_provinces'])
    c4.metric("📱 Line ID", f"{stats['total_line_contacts']:,}")

    # โหลดข้อมูลทั้งหมดจาก Database
    df = get_all_data()
    
    if not df.empty and 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        valid_dates = df['Date'].dropna()
        if not valid_dates.empty:
            years = sorted(valid_dates.dt.year.unique())
            thai_years = [int(y) + 543 for y in years]
            
            st.markdown("#### 📅 กรองข้อมูลตามเวลา")
            col_y, col_m = st.columns(2)
            
            with col_y:
                year_options = ["ทั้งหมด"] + [str(y) for y in thai_years]
                selected_year = st.selectbox("เลือกปี (พ.ศ.)", year_options)
            
            with col_m:
                selected_months = st.multiselect("เลือกเดือน", THAI_MONTHS, default=THAI_MONTHS)
            
            # Apply filter
            if selected_year != "ทั้งหมด":
                target_year = int(selected_year) - 543
                df = df[df['Date'].dt.year == target_year]
            
            if selected_months and len(selected_months) < 12:
                month_indices = [THAI_MONTHS.index(m) + 1 for m in selected_months]
                df = df[df['Date'].dt.month.isin(month_indices)]
                
            st.success(f"✅ พบข้อมูลตามที่เลือก: **{len(df):,}** แถว")
        else:
            st.success(f"✅ โหลดข้อมูลทั้งหมด สำเร็จ: **{len(df):,}** แถว")
    else:
        st.success(f"✅ โหลดข้อมูลทั้งหมด สำเร็จ: **{len(df):,}** แถว")

else:
    # ─── อัปโหลดไฟล์ (เหมือนเดิม) ────────────────────
    uploaded_file = st.file_uploader(
        "📂 อัปโหลดไฟล์ที่ประมวลผลแล้ว",
        type=["xlsx", "csv"],
        help="ไฟล์ Excel (.xlsx) หรือ CSV (.csv) ที่ดาวน์โหลดจากหน้าประมวลผล"
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            st.success(f"✅ โหลดข้อมูลสำเร็จ: **{len(df):,}** แถว, **{len(df.columns)}** คอลัมน์")
        except Exception as e:
            st.error(f"❌ อ่านไฟล์ไม่ได้: {str(e)}")
            st.stop()
    else:
        st.info("ℹ️ กรุณาอัปโหลดไฟล์ หรือเลือก 'จาก Database' เพื่อดูข้อมูลที่บันทึกไว้แล้ว")
        st.stop()

# ═══════════════════════════════════════════════════════════
# ตรวจสอบว่ามีข้อมูลแล้ว → แสดงกราฟ
# ═══════════════════════════════════════════════════════════
if df is not None and not df.empty:
    with st.expander("🔍 ตัวอย่างข้อมูล (5 แถวแรก)"):
        st.dataframe(df.head(), use_container_width=True)

    # ─── Prepare common data ──────────────────────────────
    date_col = find_column(df, ['Date', 'date', 'วันที่'])
    line_col = find_column(df, ['Line_Contact', 'line_contact', 'Line_ID'])
    channel_col = find_column(df, ['ช่องทาง (Channel)', 'ช่องทาง', 'Channel', 'channel', 'source_sheet'])
    province_col = find_column(df, ['Province', 'province', 'จังหวัด'])

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

    st.divider()

    # ═══════════════════════════════════════════════════════
    # 3 Tabs
    # ═══════════════════════════════════════════════════════
    tab1, tab2, tab3 = st.tabs([
        "📱การวิเคราะห์ตามเวลา ",
        "📍การวิเคราะห์ตามพื้นที่ ",
        "📊การวิเคราะห์ทั่วไป ",
    ])

    # ═══════════════════════════════════════════════════════
    # TAB 1: การวิเคราะห์ตามเวลา
    # ═══════════════════════════════════════════════════════
    with tab1:
        st.markdown('<p class="tab-header">📱 การวิเคราะห์ตามเวลา </p>', unsafe_allow_html=True)

        has_date = date_col is not None and df[date_col].notna().any()
        has_line = line_col is not None

        if not has_date and not has_line:
            st.warning("⚠️ ไม่พบคอลัมน์ Date หรือ Line_Contact ในข้อมูล — กรุณาอัปโหลดไฟล์ที่ผ่านการประมวลผลแล้ว")
        else:
            # ─── ค้นหา Line ID ──────────────────────────
            st.markdown("#### 🔍 ค้นหา Line ID")
            search_query = st.text_input(
                "พิมพ์ Line ID ที่ต้องการค้นหา (พิมพ์บางส่วนได้)",
                placeholder="เช่น shop, vape, @line123",
                key="line_search"
            )
            
            if search_query and has_line:
                # กรอง Line ID ที่ตรงกับคำค้นหา (บางส่วนก็ได้)
                mask = df[line_col].astype(str).str.contains(search_query, case=False, na=False)
                df_search = df[mask].copy()
            
                if not df_search.empty:
                    # นับจำนวนครั้งที่ Line ID ปรากฏในแต่ละจังหวัด
                    result = (
                        df_search
                        .groupby([line_col, province_col])
                        .size()
                        .reset_index(name='จำนวนครั้งที่พบ')
                        .sort_values('จำนวนครั้งที่พบ', ascending=False)
                    )
                    result.columns = ['Line ID', 'จังหวัด', 'จำนวนครั้งที่พบ']
            
                    # สรุปสั้น
                    total_ids = result['Line ID'].nunique()
                    total_provs = result['จังหวัด'].nunique()
                    st.success(f"พบ **{total_ids}** Line ID ที่ตรงกับคำค้นหา กระจายอยู่ใน **{total_provs}** จังหวัด")
            
                    # ตารางผลลัพธ์
                    st.dataframe(result, use_container_width=True, hide_index=True)
                else:
                    st.warning(f"ไม่พบ Line ID ที่ตรงกับ \"{search_query}\"")
                    
            st.divider()

            # Prepare line contact flag
            if has_line:
                df['_has_line'] = df[line_col].notna()
                line_count = df['_has_line'].sum()
                st.markdown(f'<div class="insight-card">📊 พบ Line Contact ทั้งหมด <b>{line_count:,}</b> รายการ จากข้อมูล <b>{len(df):,}</b> แถว ({line_count/len(df)*100:.1f}%)</div>', unsafe_allow_html=True)

            # ─── 1. Line Chart: Daily Line Contact posts ──
            if has_date and has_line:
                st.markdown("#### 📈 จำนวนโพสต์ที่มี Line Contact รายวัน")
                df_with_line = df[df['_has_line'] & df[date_col].notna()].copy()
                daily = df_with_line.groupby(df_with_line[date_col].dt.date).size().reset_index()
                daily.columns = ['วันที่', 'จำนวน']
                daily = daily.sort_values('วันที่')

                fig = px.line(
                    daily, x='วันที่', y='จำนวน',
                    markers=True,
                    title='จำนวนโพสต์ที่มี Line Contact รายวัน',
                    color_discrete_sequence=['#667eea'],
                )
                fig.update_layout(
                    height=400,
                    xaxis_title='วันที่',
                    yaxis_title='จำนวนโพสต์',
                    hovermode='x unified',
                )
                st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # ─── 2. Heatmap: Day of Week × Month ─────────
            col_heat, col_pie = st.columns(2)

            with col_heat:
                if has_date:
                    st.markdown("#### 🗓️ Heatmap: วันในสัปดาห์ × เดือน")
                    df_dated = df[df[date_col].notna()].copy()
                    df_dated['_dow'] = df_dated[date_col].dt.dayofweek
                    df_dated['_month'] = df_dated[date_col].dt.month

                    pivot = df_dated.pivot_table(
                        index='_dow', columns='_month',
                        aggfunc='size', fill_value=0
                    )

                    # Ensure all days and months present
                    pivot = pivot.reindex(index=range(7), fill_value=0)
                    existing_months = sorted(pivot.columns)

                    # Map labels
                    y_labels = THAI_DAYS
                    x_labels = [THAI_MONTHS[m - 1] for m in existing_months]

                    fig = px.imshow(
                        pivot.values,
                        x=x_labels,
                        y=y_labels,
                        color_continuous_scale='YlOrRd',
                        aspect='auto',
                        title='ความเข้มข้นโพสต์: วัน × เดือน',
                        labels=dict(x='เดือน', y='วัน', color='จำนวน'),
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("ℹ️ ต้องมีคอลัมน์ Date สำหรับ Heatmap")

            # ─── 3. Monthly Share: Pie Chart ─────────────
            with col_pie:
                if has_date and has_line:
                    st.markdown("#### 🥧 สัดส่วน Line Contact แต่ละเดือน")
                    df_monthly = df[df['_has_line'] & df[date_col].notna()].copy()
                    df_monthly['_month_label'] = df_monthly[date_col].dt.strftime('%Y-%m')

                    monthly_counts = df_monthly.groupby('_month_label').size().reset_index()
                    monthly_counts.columns = ['เดือน', 'จำนวน']
                    monthly_counts = monthly_counts.sort_values('เดือน')

                    fig = px.pie(
                        monthly_counts,
                        values='จำนวน',
                        names='เดือน',
                        title='สัดส่วน Line Contact แต่ละเดือน(ซ้ำเเละไม่ซ้ำ)',
                        hole=0.35,
                        color_discrete_sequence=px.colors.sequential.Plasma_r,
                    )
                    fig.update_traces(textinfo='label+percent+value')
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("ℹ️ ต้องมีคอลัมน์ Date และ Line_Contact สำหรับ Monthly Share")

            st.divider()

            # ─── 4. Cross-Platform: Bar Chart ────────────
            col_cross, col_spike = st.columns(2)

            with col_cross:
                if channel_col and has_line:
                    st.markdown("#### 📊 จำนวน Line Contact ตามช่องทาง")
                    df_cross = df[df['_has_line'] & df[channel_col].notna()].copy()
                    cross_counts = df_cross.groupby(channel_col).size().reset_index()
                    cross_counts.columns = ['ช่องทาง', 'จำนวน']
                    cross_counts = cross_counts.sort_values('จำนวน', ascending=False)

                    fig = px.bar(
                        cross_counts,
                        x='ช่องทาง', y='จำนวน',
                        color='ช่องทาง',
                        text='จำนวน',
                        title=f'จำนวน Line Contact ตาม {channel_col}',
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig.update_traces(textposition='outside')
                    fig.update_layout(
                        height=400,
                        showlegend=False,
                        xaxis_tickangle=-30,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                elif not channel_col:
                    st.info("ℹ️ ไม่พบคอลัมน์ช่องทาง (Channel) ในข้อมูล")
                else:
                    st.info("ℹ️ ต้องมีคอลัมน์ Line_Contact สำหรับ Cross-Platform")

            # ─── 5. Peak/Spike Detection ─────────────────
            with col_spike:
                if has_date and has_line:
                    st.markdown("#### ⚡ Peak / Spike Detection")
                    df_spike = df[df['_has_line'] & df[date_col].notna()].copy()
                    spike_daily = df_spike.groupby(df_spike[date_col].dt.date).size().reset_index()
                    spike_daily.columns = ['วันที่', 'จำนวน']
                    spike_daily = spike_daily.sort_values('วันที่')

                    mean_val = spike_daily['จำนวน'].mean()
                    std_val = spike_daily['จำนวน'].std()
                    threshold = mean_val + 2 * std_val

                    spike_daily['is_spike'] = spike_daily['จำนวน'] > threshold
                    spikes = spike_daily[spike_daily['is_spike']]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=spike_daily['วันที่'], y=spike_daily['จำนวน'],
                        mode='lines', name='จำนวนรายวัน',
                        line=dict(color='#667eea', width=2),
                    ))
                    # Threshold line
                    fig.add_hline(
                        y=threshold, line_dash='dash', line_color='#ff6b6b',
                        annotation_text=f'Threshold ({threshold:.0f})',
                        annotation_position='top left',
                    )
                    # Spike markers
                    if not spikes.empty:
                        fig.add_trace(go.Scatter(
                            x=spikes['วันที่'], y=spikes['จำนวน'],
                            mode='markers', name='🔺 Spike',
                            marker=dict(color='#ff6b6b', size=12, symbol='triangle-up'),
                        ))
                    fig.update_layout(
                        title=f'Spike Detection (mean + 2σ = {threshold:.0f})',
                        height=400,
                        xaxis_title='วันที่',
                        yaxis_title='จำนวน',
                        hovermode='x unified',
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Show spike details
                    if not spikes.empty:
                        st.markdown(f'<div class="spike-alert">🔺 พบ <b>{len(spikes)}</b> วันที่มีจำนวนสูงผิดปกติ (มากกว่า mean + 2σ = {threshold:.0f})</div>', unsafe_allow_html=True)
                        with st.expander("📋 รายละเอียดวันที่ Spike"):
                            spike_display = spikes[['วันที่', 'จำนวน']].copy()
                            spike_display['วันที่'] = spike_display['วันที่'].astype(str)
                            st.dataframe(spike_display, use_container_width=True, hide_index=True)

                        # ─── Line ID ที่โพสต์เยอะสุดในวัน Spike ───
                        spike_dates = spikes['วันที่'].tolist()
                        df_spike_posts = df_spike[df_spike[date_col].dt.date.isin(spike_dates)].copy()
                        df_spike_has_line = df_spike_posts[df_spike_posts[line_col].notna() & (df_spike_posts[line_col].astype(str).str.strip() != '')]

                        if not df_spike_has_line.empty:
                            top_spike_ids = (
                                df_spike_has_line
                                .groupby(line_col)
                                .size()
                                .reset_index(name='จำนวนโพสต์ในวัน Spike')
                                .sort_values('จำนวนโพสต์ในวัน Spike', ascending=False)
                                .head(10)
                                .reset_index(drop=True)
                            )
                            top_spike_ids.insert(0, 'อันดับ', range(1, len(top_spike_ids) + 1))

                            st.markdown("##### 🏆 Line ID ที่โพสต์มากสุดในวันที่ Spike")
                            st.dataframe(top_spike_ids, use_container_width=True, hide_index=True)
                        else:
                            st.caption("ℹ️ ไม่พบ Line ID ในโพสต์วัน Spike")
                    else:
                        st.success("✅ ไม่พบวันที่มีค่าผิดปกติ (ทุกวันอยู่ในช่วง mean ± 2σ)")
                else:
                    st.info("ℹ️ ต้องมีคอลัมน์ Date และ Line_Contact สำหรับ Spike Detection")

    # ═══════════════════════════════════════════════════════
    # TAB 2: Province Map
    # ═══════════════════════════════════════════════════════
    with tab2:
        st.markdown('<p class="tab-header">📍การวิเคราะห์ตามพื้นที่  — จำนวนโพสต์ตามจังหวัด</p>', unsafe_allow_html=True)

        if not province_col:
            st.warning("⚠️ ไม่พบคอลัมน์ Province ในข้อมูล — กรุณาอัปโหลดไฟล์ที่ผ่านการสกัดจังหวัดแล้ว")
        else:
            # ─── สร้าง DataFrame ครบ 77 จังหวัด ───────────
            all_prov_rows = []
            for region, provs in REGION_PROVINCES.items():
                for p in provs:
                    all_prov_rows.append({'จังหวัด': p, 'ภาค': region})
            df_all_prov = pd.DataFrame(all_prov_rows)

            # นับจำนวนจริงจากข้อมูล
            province_counts = df[province_col].dropna().value_counts().reset_index()
            province_counts.columns = ['จังหวัด', 'จำนวน']

            # Left join: ทุกจังหวัด + จำนวนจริง (ไม่มีข้อมูล = 0)
            df_province = df_all_prov.merge(province_counts, on='จังหวัด', how='left')
            df_province['จำนวน'] = df_province['จำนวน'].fillna(0).astype(int)

            # ─── Summary (ทุกจังหวัด) ─────────────────────
            total_all = int(df_province['จำนวน'].sum())
            prov_with_data = int((df_province['จำนวน'] > 0).sum())
            st.markdown(
                f'<div class="insight-card">📍 พบข้อมูลจาก <b>{prov_with_data}</b> / 77 จังหวัด '
                f'รวม <b>{total_all:,}</b> โพสต์</div>',
                unsafe_allow_html=True,
            )

            # ═════════════════════════════════════════════
            # ส่วนที่ 1: Top 20 ทุกจังหวัด (ไม่กรอง)
            # ═════════════════════════════════════════════
            st.markdown("#### 📊 Top 20 จังหวัดที่มีโพสต์มากที่สุด")
            top20 = df_province[df_province['จำนวน'] > 0].sort_values('จำนวน', ascending=False).head(20)

            if not top20.empty:
                fig = px.bar(
                    top20,
                    x='จังหวัด', y='จำนวน',
                    color='จำนวน',
                    color_continuous_scale='YlOrRd',
                    text='จำนวน',
                    title='จำนวนโพสต์ตามจังหวัด (Top 20)',
                )
                fig.update_traces(textposition='outside')
                fig.update_layout(
                    height=500,
                    xaxis_tickangle=-45,
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ℹ️ ไม่มีจังหวัดที่มีข้อมูล")

            # ─── Top-10 Table + Bar ───────────────────────
            st.divider()
            col_table, col_bar = st.columns(2)
            with col_table:
                st.markdown("#### 🏆 Top 10 จังหวัดที่มีโพสต์มากที่สุด")
                top10 = df_province[df_province['จำนวน'] > 0].sort_values('จำนวน', ascending=False).head(10).copy()
                if not top10.empty:
                    display_top10 = top10[['จังหวัด', 'ภาค', 'จำนวน']].copy()
                    display_top10.index = range(1, len(display_top10) + 1)
                    display_top10.index.name = 'อันดับ'
                    st.dataframe(display_top10, use_container_width=True)

            with col_bar:
                st.markdown("#### 📊 Top 10 จังหวัด")
                top10_bar = df_province[df_province['จำนวน'] > 0].sort_values('จำนวน', ascending=False).head(10)
                if not top10_bar.empty:
                    fig = px.bar(
                        top10_bar,
                        y='จังหวัด', x='จำนวน',
                        orientation='h',
                        color='จำนวน',
                        color_continuous_scale='YlOrRd',
                        text='จำนวน',
                    )
                    fig.update_traces(textposition='outside')
                    fig.update_layout(
                        height=400,
                        showlegend=False,
                        yaxis=dict(autorange='reversed'),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # ─── จังหวัดที่ไม่มีข้อมูล ────────────────────
            provinces_no_data = df_province[df_province['จำนวน'] == 0]
            if not provinces_no_data.empty:
                with st.expander(f"📋 จังหวัดที่ไม่มีข้อมูล ({len(provinces_no_data)} จังหวัด)"):
                    st.dataframe(
                        provinces_no_data[['จังหวัด', 'ภาค']].reset_index(drop=True),
                        use_container_width=True,
                        hide_index=True,
                    )

            # ═════════════════════════════════════════════
            # ส่วนที่ 2: ฟิลเตอร์ภาค/จังหวัด + Choropleth Map
            # ═════════════════════════════════════════════
            st.divider()
            st.markdown("#### 🗺️ แผนที่จำนวนโพสต์ (Choropleth Map)")

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                region_options = ['ทั้งหมด'] + list(REGION_PROVINCES.keys())
                selected_region = st.selectbox(
                    '🗺️ เลือกภาค', region_options, key='map_region',
                )
            with col_m2:
                all_prov_names = sorted(df_province['จังหวัด'].unique())
                selected_map_provs = st.multiselect(
                    '📍 หรือ เลือกเปรียบเทียบเฉพาะจังหวัดที่สนใจ', all_prov_names, key='map_provs',
                    help="หากเลือกจังหวัดตรงนี้ ระบบจะแสดงแผนที่เฉพาะจังหวัดที่เลือก โดยละเว้นตัวกรองภาค"
                )

            # กรองข้อมูล
            if selected_map_provs:
                df_region = df_province[df_province['จังหวัด'].isin(selected_map_provs)].copy()
                region_label = 'จังหวัดที่เลือก'
            elif selected_region != 'ทั้งหมด':
                df_region = df_province[df_province['ภาค'] == selected_region].copy()
                region_label = selected_region
            else:
                df_region = df_province.copy()
                region_label = 'ทุกภาค'

            df_region = df_region.sort_values('จำนวน', ascending=False).reset_index(drop=True)

            # Summary ของภาคที่เลือก
            region_total = int(df_region['จำนวน'].sum())
            region_with_data = int((df_region['จำนวน'] > 0).sum())
            st.markdown(
                f'<div class="insight-card">🗺️ <b>{region_label}</b>: '
                f'<b>{len(df_region)}</b> จังหวัด | '
                f'มีข้อมูล <b>{region_with_data}</b> จังหวัด | '
                f'รวม <b>{region_total:,}</b> โพสต์</div>',
                unsafe_allow_html=True,
            )

            # ─── Choropleth Map ───────────────────────────
            choropleth_ok = False
            try:
                from utils.thai_geo import load_thailand_geojson, detect_name_property
                geojson = load_thailand_geojson()
                if geojson:
                    name_prop = detect_name_property(geojson)
                    if name_prop:
                        fig = px.choropleth(
                            df_region,
                            geojson=geojson,
                            locations='จังหวัด',
                            featureidkey=f'properties.{name_prop}',
                            color='จำนวน',
                            color_continuous_scale='YlOrRd',
                            title=f'แผนที่จำนวนโพสต์ — {region_label}',
                            labels={'จำนวน': 'จำนวนโพสต์'},
                            hover_data=['ภาค'],
                        )
                        fig.update_geos(
                            fitbounds='locations',
                            visible=False,
                        )
                        fig.update_layout(
                            height=700,
                            margin=dict(l=0, r=0, t=50, b=0),
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        choropleth_ok = True
            except Exception as e:
                st.caption(f"ℹ️ ไม่สามารถโหลดแผนที่ได้ ({str(e)[:80]})")

            # Fallback: Bar chart ของภาคที่เลือก
            if not choropleth_ok:
                st.markdown(f"#### 📊 จำนวนโพสต์ตามจังหวัด — {region_label}")
                df_region_bar = df_region[df_region['จำนวน'] > 0]
                if not df_region_bar.empty:
                    fig = px.bar(
                        df_region_bar,
                        x='จังหวัด', y='จำนวน',
                        color='จำนวน',
                        color_continuous_scale='YlOrRd',
                        text='จำนวน',
                        title=f'จำนวนโพสต์ — {region_label}',
                    )
                    fig.update_traces(textposition='outside')
                    fig.update_layout(
                        height=500,
                        xaxis_tickangle=-45,
                        showlegend=False,
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"ℹ️ ไม่มีข้อมูลใน{region_label}")

            # ตารางจังหวัดในภาคที่เลือก
            with st.expander(f"📋 ดูข้อมูลทุกจังหวัดใน{region_label} ({len(df_region)} จังหวัด)"):
                st.dataframe(
                    df_region[['จังหวัด', 'ภาค', 'จำนวน']].reset_index(drop=True),
                    use_container_width=True,
                    hide_index=True,
                )

            # ═════════════════════════════════════════════
            # ส่วนที่ 3: ค้นหาข้อมูลรายจังหวัด
            # ═════════════════════════════════════════════
            st.divider()
            st.markdown("#### 🔎 ค้นหา Line ID รายจังหวัด")
            
            # หาจังหวัดทั้งหมดที่มีข้อมูล
            available_provinces = sorted([p for p in df[province_col].dropna().unique() if str(p).strip()])
            
            selected_provs = st.multiselect(
                "เลือกจังหวัดที่ต้องการดูข้อมูล Line ID",
                options=available_provinces,
                help="สามารถเลือกได้หลายจังหวัด",
                key='prov_line_search'
            )
            
            if selected_provs:
                df_filtered_prov = df[df[province_col].isin(selected_provs)].copy()
                
                if line_col:
                    # กรองเฉพาะแถวที่มี Line ID (ไม่ว่าง)
                    df_has_line = df_filtered_prov[
                        df_filtered_prov[line_col].notna() &
                        (df_filtered_prov[line_col].astype(str).str.strip() != '')
                    ]
                    
                    if not df_has_line.empty:
                        # นับจำนวนโพสต์ของแต่ละ Line ID ในจังหวัดที่เลือก
                        line_counts = (
                            df_has_line
                            .groupby([province_col, line_col])
                            .size()
                            .reset_index(name='จำนวนโพสต์ที่พบ')
                            .sort_values('จำนวนโพสต์ที่พบ', ascending=False)
                            .reset_index(drop=True)
                        )
                        line_counts.columns = ['จังหวัด', 'Line ID', 'จำนวนโพสต์ที่พบ']
                        
                        st.caption("💡 คลิกที่แถวในตารางเพื่อดูโพสต์ของ Line ID นั้น")
                        event = st.dataframe(
                            line_counts,
                            use_container_width=True,
                            hide_index=True,
                            on_select="rerun",
                            selection_mode="single-row",
                            key='line_id_table'
                        )
                        
                        # สรุปยอดรวม
                        total_ids = line_counts['Line ID'].nunique()
                        total_posts = int(line_counts['จำนวนโพสต์ที่พบ'].sum())
                        st.success(
                            f"✅ จังหวัดที่เลือก {len(selected_provs)} จังหวัด: "
                            f"พบ **{total_ids}** Line ID (ไม่ซ้ำ) | "
                            f"รวม **{total_posts:,}** โพสต์ที่มี Line ID"
                        )
                        
                        # ─── Drill-down: แสดงโพสต์ของ Line ID ที่คลิก ───
                        content_col = find_column(df_filtered_prov, ['เนื้อหาโพสต์', 'post_content'])
                        pub_col = find_column(df_filtered_prov, ['ผู้เผยแพร่', 'publisher'])
                        
                        if event.selection.rows:
                            selected_row_idx = event.selection.rows[0]
                            selected_line_id = line_counts.iloc[selected_row_idx]['Line ID']
                            selected_prov = line_counts.iloc[selected_row_idx]['จังหวัด']
                            
                            # กรองโพสต์เฉพาะ Line ID ที่คลิก
                            df_drill = df_filtered_prov[
                                (df_filtered_prov[line_col] == selected_line_id) &
                                (df_filtered_prov[province_col] == selected_prov)
                            ].copy()
                            
                            st.markdown(f"##### 📋 โพสต์ของ `{selected_line_id}` ใน{selected_prov} ({len(df_drill)} โพสต์)")
                            
                            with st.container(height=500):
                                for i, row in df_drill.iterrows():
                                    with st.chat_message("user", avatar="📄"):
                                        pub_name = row.get(pub_col, 'ไม่ระบุ') if pub_col else 'ไม่ระบุ'
                                        st.markdown(f"**📍 {selected_prov}** | 👤 {pub_name} | 📱 {selected_line_id}")
                                        if content_col:
                                            st.info(row.get(content_col, ''))
                                        else:
                                            st.caption("ไม่มีเนื้อหาโพสต์")
                        else:
                            st.info("👆 คลิกเลือกแถวในตารางด้านบนเพื่อดูรายละเอียดโพสต์ของ Line ID นั้น")
            else:
                st.info("👆 กรุณาเลือกจังหวัดจากด้านบนเพื่อดูข้อมูล Line ID")

    # ═══════════════════════════════════════════════════════
    # TAB 3: Custom Charts
    # ═══════════════════════════════════════════════════════
    with tab3:
        st.markdown('<p class="tab-header">📊 การวิเคราะห์ทั่วไป  — เลือกคอลัมน์ + ประเภทกราฟ</p>', unsafe_allow_html=True)

        col_left, col_right = st.columns(2)

        with col_left:
            chart_type = st.selectbox(
                "📈 เลือกประเภทกราฟ",
                ["Bar Chart (แท่ง)", "Pie Chart (วงกลม)", "Line Chart (เส้น)"],
                key='custom_chart_type',
            )

            all_columns = list(df.columns)
            # Filter out internal columns
            display_columns = [c for c in all_columns if not c.startswith('_')]
            default_idx = display_columns.index(province_col) if province_col and province_col in display_columns else 0

            x_column = st.selectbox(
                "📌 เลือกคอลัมน์ที่จะวิเคราะห์ (แกน X / กลุ่มข้อมูล)",
                display_columns,
                index=default_idx,
                key='custom_x_col',
            )

        with col_right:
            top_n = st.slider("🔢 แสดง Top-N อันดับ", min_value=5, max_value=50, value=10, key='custom_top_n')

            color_theme = st.selectbox(
                "🎨 ชุดสี",
                ["plotly", "viridis", "plasma", "inferno", "magma", "cividis", "turbo"],
                key='custom_color',
            )

        if st.button("🚀 สร้างกราฟ", type="primary", use_container_width=True, key='custom_create'):
            st.divider()

            value_counts = df[x_column].dropna().value_counts().head(top_n).reset_index()
            value_counts.columns = [x_column, 'จำนวน']

            if value_counts.empty:
                st.warning("⚠️ คอลัมน์ที่เลือกไม่มีข้อมูล")
                st.stop()

            st.subheader(f"📊 ผลลัพธ์: Top {top_n} — {x_column}")

            # ═══ Bar Chart ═══
            if "Bar" in chart_type:
                fig = px.bar(
                    value_counts,
                    x=x_column, y='จำนวน',
                    color=x_column,
                    color_discrete_sequence=px.colors.qualitative.Plotly if color_theme == 'plotly'
                        else getattr(px.colors.sequential, color_theme.capitalize(), px.colors.sequential.Viridis),
                    text='จำนวน',
                    title=f'Bar Chart: จำนวนตาม {x_column} (Top {top_n})',
                )
                fig.update_traces(textposition='outside')
                fig.update_layout(xaxis_tickangle=-45, height=600, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            # ═══ Pie Chart ═══
            elif "Pie" in chart_type:
                fig = px.pie(
                    value_counts,
                    values='จำนวน', names=x_column,
                    title=f'Pie Chart: สัดส่วนตาม {x_column} (Top {top_n})',
                    hole=0.35,
                )
                fig.update_traces(textinfo='label+percent+value')
                fig.update_layout(height=600)
                st.plotly_chart(fig, use_container_width=True)

            # ═══ Line Chart ═══
            elif "Line" in chart_type:
                fig = px.line(
                    value_counts,
                    x=x_column, y='จำนวน',
                    markers=True,
                    title=f'Line Chart: แนวโน้มตาม {x_column} (Top {top_n})',
                )
                fig.update_layout(height=600)
                st.plotly_chart(fig, use_container_width=True)

            # ─── Data Table ───
            with st.expander("📋 ดูข้อมูลตาราง"):
                st.dataframe(value_counts, use_container_width=True, hide_index=True)
