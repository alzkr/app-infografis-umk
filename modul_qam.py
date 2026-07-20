import streamlit as st
from sqlalchemy import text
import pandas as pd
from datetime import datetime
import tempfile
from fpdf import FPDF

# --- INISIALISASI DATABASE (MENGGUNAKAN ST.CONNECTION & SQLALCHEMY) ---
# Pastikan URL disimpan di .streamlit/secrets.toml sebagai SUPABASE_DB_URL
conn = st.connection("supabase", type="sql", url=st.secrets["SUPABASE_DB_URL"])

def init_db():
    # PostgreSQL menggunakan sintaks SERIAL untuk Auto Increment
    # DATETIME diubah menjadi TIMESTAMP
    with conn.session as s:
        s.execute(text('''
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                report_type TEXT, date_str TEXT, time_str TEXT, wind TEXT,
                visibility TEXT, weather TEXT, cloud TEXT, tt_td TEXT,
                qnh TEXT, qfe TEXT, sup_info TEXT, remarks TEXT,
                trend TEXT, observer TEXT, datetime_val TIMESTAMP
            )
        '''))
        s.commit()

def calc_pressure(mb_str):
    try:
        mb_val = float(mb_str.strip())
        inch_val = mb_val * 0.02953
        return f"{int(mb_val)} mb / {inch_val:.2f} inch"
    except ValueError:
        return mb_str

# --- FUNGSI UNTUK MENGGENERATE PDF ---
def generate_pdf_bytes(rows, m, y):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    
    # === HALAMAN 1 & 2: COVER & REKAPITULASI ===
    pdf.add_page()
    qam_count = sum(1 for r in rows if r[1] == "QAM")
    speci_count = sum(1 for r in rows if r[1] == "SPECIAL")
    total_count = len(rows)

    bulan_indo = {
        "01": "JANUARI", "02": "FEBRUARI", "03": "MARET", "04": "APRIL",
        "05": "MEI", "06": "JUNI", "07": "JULI", "08": "AGUSTUS",
        "09": "SEPTEMBER", "10": "OKTOBER", "11": "NOVEMBER", "12": "DESEMBER"
    }
    nama_bulan = bulan_indo.get(m, m)

    # Cetak Cover
    pdf.ln(80)
    pdf.set_font("Courier", 'B', 18)
    pdf.cell(190, 10, "DOKUMEN REKAPITULASI LAPORAN QAM", ln=2, align='C')
    pdf.set_font("Courier", 'B', 14)
    pdf.cell(190, 8, "STAMET UMBU MEHANG KUNDA (WATU)", ln=2, align='C')
    pdf.ln(20)
    pdf.set_font("Courier", 'B', 12)
    pdf.cell(190, 6, f"PERIODE: BULAN {nama_bulan} TAHUN {y}", ln=2, align='C')
    pdf.ln(10)
    pdf.set_font("Courier", 'B', 11)
    pdf.cell(190, 6, f"TOTAL: {total_count} LAPORAN (MET REPORT: {qam_count} | SPECIAL: {speci_count})", ln=2, align='C')
    
    # === HALAMAN LAMPIRAN (GRID NARASI) ===
    pdf.add_page()
    col_w, col_h = 95, 86
    x0, y0 = 10, 15
    cur_col, cur_row = 0, 0
    
    for r in rows:
        y_pos = y0 + cur_row * col_h
        if y_pos + col_h > 290: 
            pdf.add_page()
            cur_row, y0 = 0, 15 
            y_pos = y0
            
        x = x0 + cur_col * col_w
        pdf.set_xy(x, y_pos)
        pdf.set_font("Courier", 'B', 8)
        
        if r[1] == "SPECIAL":
            title = "SPECIAL REPORT FOR TAKE OFF AND LANDING"
            pdf.set_text_color(255, 0, 0) 
        else:
            title = "METEOROLOGICAL REPORT FOR TAKE OFF AND LANDING"
            pdf.set_text_color(0, 0, 0) 
            
        pdf.cell(90, 4, title, ln=2, align='L')
        pdf.set_text_color(0, 0, 0)
        pdf.cell(90, 4, "STAMET UMBU MEHANG KUNDA (WATU)", ln=2, align='L')
        
        pdf.set_font("Courier", '', 8)
        pdf.cell(90, 4, f"DATE: {r[2]}", ln=2, align='L')
        pdf.cell(90, 4, f"TIME: {r[3]} UTC", ln=2, align='L')
        pdf.ln(3) 
        
        lines = [
            ("WIND", r[4]), ("VISIBILITY", r[5]), ("WEATHER", r[6]),
            ("CLOUD", r[7]), ("TT/TD", r[8]), ("QNH", r[9]), ("QFE", r[10]),
            ("Sup. Info", r[11]), ("REMARKS", r[12]), ("TREND FCT", r[13])
        ]
        
        for key, val in lines:
            cy = pdf.get_y()
            pdf.set_xy(x, cy)
            pdf.cell(32, 4, key, ln=0)
            
            pdf.set_xy(x + 32, cy)
            val_safe = val.encode('latin-1', 'replace').decode('latin-1') if val else "-"
            pdf.cell(58, 4, f": {val_safe}", ln=0) 
            pdf.set_y(cy + 4) 
            
        pdf.ln(2)
        cy = pdf.get_y()
        pdf.set_xy(x, cy)
        pdf.cell(90, 4, "Observer,", ln=2)
        pdf.cell(90, 4, r[14], ln=2)
        
        cur_col += 1
        if cur_col > 1: 
            cur_col = 0
            cur_row += 1

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()

# --- FUNGSI UTAMA UI QAM ---
def tampilkan_ui_qam():
    init_db() # Pastikan tabel terbuat di Supabase
    
    # Inisialisasi Session State untuk fitur Peringatan Overwrite & Hasil Teks
    if 'confirm_overwrite' not in st.session_state:
        st.session_state.confirm_overwrite = False
    if 'wa_text' not in st.session_state:
        st.session_state.wa_text = ""

    st.markdown("### 📊 Laporan QAM & SPECIAL")
    st.caption("STAMET UMBU MEHANG KUNDA (WATU)")
    
    tab_input, tab_db, tab_monitor = st.tabs(["📝 Input Laporan", "🗄️ Database & Rekap", "📡 Monitoring"])

    # ==========================================
    # TAB 1: INPUT LAPORAN HARIAN
    # ==========================================
    with tab_input:
        st.markdown("#### Waktu & Jenis Laporan")
        is_speci = st.toggle("🔴 JADIKAN SPECIAL REPORT (SPECI)")
        
        col_t1, col_t2, col_t3 = st.columns(3)
        tanggal = col_t1.date_input("Tanggal", format="DD/MM/YYYY")
        time_hr = col_t2.selectbox("Jam (UTC)", [str(h).zfill(2) for h in range(24)])
        
        norm_mins = ["00", "30"]
        speci_mins = [str(m).zfill(2) for m in range(60) if m not in (0, 30)]
        time_min = col_t3.selectbox("Menit", speci_mins if is_speci else norm_mins)
        
        st.markdown("#### Angin & Jarak Pandang")
        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
        wind_dir = col_w1.text_input("Wind Dir (Arah)")
        wind_spd = col_w2.text_input("Wind Spd (KT)")
        
        is_var_wind = col_w3.toggle("VRB? (Variabel)")
        is_gusty = col_w4.toggle("Gusty? (G)")
        
        cv1, cv2, cg = st.columns(3)
        var_dir1 = cv1.text_input("Arah 1 (V1)", disabled=not is_var_wind)
        var_dir2 = cv2.text_input("Arah 2 (V2)", disabled=not is_var_wind)
        gust_spd = cg.text_input("Gust Spd (KT)", disabled=not is_gusty)
        
        col_v1, col_v2 = st.columns([3, 1])
        vis_val = col_v1.text_input("Visibility (Angka)")
        vis_unit = col_v2.selectbox("Satuan Visibilitas", ["KM", "M"])

        st.markdown("#### Cuaca & Perawanan")
        col_wx1, col_wx2 = st.columns(2)
        wx_desc = col_wx1.selectbox("Intensitas (Opsional)", ["", "FBL", "MOD", "HVY"])
        wx_main = col_wx2.selectbox("Weather", ["NIL", "RA", "DZ", "FG", "BR", "HZ", "VCTS", "TSRA", "SHRA"])
        
        st.markdown("**Cloud (Lapis 1)**")
        col_c1, col_c2 = st.columns(2)
        cloud_amt = col_c1.selectbox("Jumlah L1", ["NIL", "FEW", "SCT", "BKN", "OVC", "NSC", "CAVOK"], index=1)
        cloud_hgt = col_c2.text_input("Tinggi L1 (FEET)", value="2000")
        
        col_mid, col_cb = st.columns(2)
        with col_mid:
            is_mid = st.toggle("Ada Lapis 2?")
            mid_amt = st.selectbox("Jumlah L2", ["FEW", "SCT", "BKN", "OVC"], index=2, disabled=not is_mid)
            mid_hgt = st.text_input("Tinggi L2 (FEET)", value="10000", disabled=not is_mid)
        with col_cb:
            is_cb = st.toggle("Ada CB?")
            cb_amt = st.selectbox("Jumlah CB", ["FEW", "SCT", "BKN", "OVC"], disabled=not is_cb)
            cb_hgt = st.text_input("Tinggi CB (FEET)", value="2000", disabled=not is_cb)

        st.markdown("#### Suhu & Tekanan")
        col_tt1, col_tt2 = st.columns(2)
        tt = col_tt1.text_input("TT (°C)")
        td = col_tt2.text_input("TD (°C)")
        
        col_q1, col_q2 = st.columns(2)
        qnh = col_q1.text_input("QNH (mb)")
        qfe = col_q2.text_input("QFE (mb)")
      
        st.markdown("#### Informasi Tambahan")
        sup_info = st.text_input("Sup. Info", value="-")
        remarks = st.text_input("Remarks", value="-")
        
        col_tr1, col_tr2 = st.columns(2)
        trend = col_tr1.selectbox("Trend FCT", ["-", "NOSIG", "TEMPO", "BECMG"])
        trend_note = col_tr2.text_input("Keterangan Trend", disabled=(trend in ["-", "NOSIG"]))
            
        observer = st.text_input("Observer")
        
       # --- LOGIKA SUBMIT & PERINGATAN GANDA ---
        if st.button("1. Simpan & Buat Teks WA", type="primary"):
            report_type = "SPECI" if is_speci else "QAM"
            date_str = tanggal.strftime("%d/%m/%Y")
            time_str = f"{time_hr}.{time_min}"
            
            if is_gusty and gust_spd:
                wind = f"{wind_dir} / {wind_spd}G{gust_spd} KT"
            else:
                wind = f"{wind_dir} / {wind_spd} KT"
                
            if is_var_wind and var_dir1 and var_dir2: 
                wind += f" {var_dir1}V{var_dir2}"
            
            vis = f"{vis_val} {vis_unit}"
            weather = "NIL" if wx_main == "NIL" else f"{wx_desc} {wx_main}".strip()
            
            cloud_parts = []
            if is_cb: cloud_parts.append(f"CB {cb_amt} {cb_hgt} FEET")
            if cloud_amt not in ["NSC", "CAVOK", "NIL"]:
                cloud_parts.append(f"{cloud_amt} {cloud_hgt} FEET")
                if is_mid: cloud_parts.append(f"{mid_amt} {mid_hgt} FEET")
            else:
                cloud_parts.append(cloud_amt)
            cloud = "; ".join(cloud_parts)
            
            tt_td = f"{tt} °C / {td} °C"
            qnh_fmt = calc_pressure(qnh)
            qfe_fmt = calc_pressure(qfe)
            trend_full = f"{trend} {trend_note}".strip() if trend in ["TEMPO", "BECMG"] else trend
            
            # Format Datetime PostgreSQL (YYYY-MM-DD HH:MM:SS)
            dt_val = f"{tanggal.strftime('%Y-%m-%d')} {time_hr}:{time_min}:00"

            # ========================================================
            # MENGIRIM DATA KE MEMORI (SESSION STATE) UNTUK INFOGRAFIS
            # ========================================================
            st.session_state['qam_suhu'] = tt
            st.session_state['qam_titik_embun'] = td
            st.session_state['qam_qnh'] = qnh 
            st.session_state['qam_visibilitas'] = vis_val
            st.session_state['qam_kec_angin'] = wind_spd
            st.session_state['qam_arah_angin'] = wind_dir
            # ========================================================

            teks_laporan = f"""```
{'SPECIAL' if is_speci else 'METEOROLOGICAL'} REPORT FOR TAKE OFF AND LANDING
STAMET UMBU MEHANG KUNDA (WATU)
{'DATE':<17} : {date_str}
{'TIME':<17} : {time_str} UTC
===================================
{'WIND':<17} : {wind}
{'VISIBILITY':<17} : {vis}
{'WEATHER':<17} : {weather}
{'CLOUD':<17} : {cloud}
{'TT/TD':<17} : {tt_td}
{'QNH':<17} : {qnh_fmt}
{'QFE':<17} : {qfe_fmt}
{'SUPLEMENTARY INFO':<17} : {sup_info.upper()}
{'REMARKS':<17} : {remarks.upper()}
{'TREND FCT':<17} : {trend_full.upper()}

OBSERVER,
{observer.upper()}
```"""
            
            # Penggunaan SQLAlchemy Parameterized Query (Penghubung ke Supabase)
            param_dict = {
                "report_type": report_type, "date_str": date_str, "time_str": time_str,
                "wind": wind, "visibility": vis, "weather": weather, "cloud": cloud,
                "tt_td": tt_td, "qnh": qnh_fmt, "qfe": qfe_fmt, "sup_info": sup_info,
                "remarks": remarks, "trend": trend_full, "observer": observer, "dt_val": dt_val
            }
            
            with conn.session as s:
                cek_duplikat = s.execute(text("SELECT id FROM reports WHERE datetime_val = :dt_val"), {"dt_val": dt_val}).fetchone()
                
                if cek_duplikat:
                    st.session_state.confirm_overwrite = True
                    st.session_state.pending_data = param_dict
                    st.session_state.pending_wa = teks_laporan
                else:
                    s.execute(text('''
                        INSERT INTO reports 
                        (report_type, date_str, time_str, wind, visibility, weather, cloud, tt_td, qnh, qfe, sup_info, remarks, trend, observer, datetime_val)
                        VALUES (:report_type, :date_str, :time_str, :wind, :visibility, :weather, :cloud, :tt_td, :qnh, :qfe, :sup_info, :remarks, :trend, :observer, :dt_val)
                    '''), param_dict)
                    s.commit()
                    st.session_state.wa_text = teks_laporan
                    st.success("✅ Tersimpan di Database Supabase!")

        # Menampilkan Notifikasi Peringatan Replace / Cancel
        if st.session_state.confirm_overwrite:
            st.warning("⚠️ Data laporan dengan Tanggal & Jam tersebut sudah ada di Database.")
            col_yes, col_no = st.columns(2)
            
            if col_yes.button("✅ Replace (Timpa Data)"):
                data = st.session_state.pending_data
                with conn.session as s:
                    s.execute(text("DELETE FROM reports WHERE datetime_val = :dt_val"), {"dt_val": data["dt_val"]})
                    s.execute(text('''
                        INSERT INTO reports 
                        (report_type, date_str, time_str, wind, visibility, weather, cloud, tt_td, qnh, qfe, sup_info, remarks, trend, observer, datetime_val)
                        VALUES (:report_type, :date_str, :time_str, :wind, :visibility, :weather, :cloud, :tt_td, :qnh, :qfe, :sup_info, :remarks, :trend, :observer, :dt_val)
                    '''), data)
                    s.commit()
                    
                st.session_state.confirm_overwrite = False
                st.session_state.wa_text = st.session_state.pending_wa
                st.success("Data lama berhasil ditimpa ke Database!")
                st.rerun()
                
            if col_no.button("❌ Cancel (Batal)"):
                st.session_state.confirm_overwrite = False
                st.info("Aksi dibatalkan.")
                st.rerun()

        if st.session_state.wa_text and not st.session_state.confirm_overwrite:
            st.info("Salin (Copy) teks di bawah ini untuk dikirim ke WhatsApp:")
            st.code(st.session_state.wa_text, language="text")

    # ==========================================
    # TAB 2: DATABASE & REKAP PDF
    # ==========================================
    with tab_db:
        st.markdown("**Data Laporan Tersimpan**")
        # Pandas dapat langsung membaca query menggunakan koneksi Streamlit
        df = conn.query("SELECT id, datetime_val, report_type, observer FROM reports ORDER BY datetime_val DESC")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("#### 📄 Export Laporan Bulanan (PDF)")
        
        col_bln, col_thn, col_btn = st.columns([1, 1, 2])
        m_pilih = col_bln.selectbox("Bulan", [str(i).zfill(2) for i in range(1, 13)], index=datetime.now().month - 1)
        y_pilih = col_thn.selectbox("Tahun", [str(y) for y in range(2024, 2035)], index=2)
        
        # Proses Tarik Data menggunakan TO_CHAR() PostgreSQL untuk ekstraksi Bulan & Tahun
        with conn.session as s:
            rows = s.execute(text("""
                SELECT * FROM reports 
                WHERE TO_CHAR(datetime_val, 'MM') = :m 
                AND TO_CHAR(datetime_val, 'YYYY') = :y 
                ORDER BY datetime_val ASC
            """), {"m": m_pilih, "y": y_pilih}).fetchall()
        
        if len(rows) > 0:
            pdf_bytes = generate_pdf_bytes(rows, m_pilih, y_pilih)
            
            col_btn.markdown("<br>", unsafe_allow_html=True) 
            col_btn.download_button(
                label="⬇️ Download PDF Bulanan",
                data=pdf_bytes,
                file_name=f"Laporan_Bulanan_{m_pilih}_{y_pilih}.pdf",
                mime="application/pdf",
                type="primary"
            )
        else:
            col_btn.markdown("<br>", unsafe_allow_html=True)
            col_btn.warning(f"Data {m_pilih}/{y_pilih} kosong.")
            
        st.markdown("---")
        del_id = st.number_input("Masukkan ID untuk dihapus", min_value=0, step=1)
        if st.button("🗑️ Hapus Data by ID"):
            with conn.session as s:
                s.execute(text("DELETE FROM reports WHERE id = :id"), {"id": del_id})
                s.commit()
            st.success(f"Data ID {del_id} dihapus. Silakan muat ulang halaman.")

    # ==========================================
    # TAB 3: MONITORING
    # ==========================================
    with tab_monitor:
        st.markdown("**Status Pengiriman Sesuai Jam Operasional**")
        tgl_mon = st.date_input("Pilih Tanggal", format="DD/MM/YYYY")
        tgl_str = tgl_mon.strftime("%d/%m/%Y")
        
        with conn.session as s:
            rows_mon = s.execute(text("SELECT time_str, report_type FROM reports WHERE date_str = :tgl_str"), {"tgl_str": tgl_str}).fetchall()
        
        qam_hours = set()
        for r in rows_mon:
            if r[1] == "QAM":
                try:
                    hr = int(r[0].split('.')[0])
                    qam_hours.add(hr)
                except: pass

        op_hours = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 21, 22, 23]
        cols = st.columns(5)
        for i, hr in enumerate(op_hours):
            with cols[i % 5]:
                if hr in qam_hours:
                    st.success(f"**{hr:02d}:00 UTC**\n\n✅ TERKIRIM")
                else:
                    st.error(f"**{hr:02d}:00 UTC**\n\n❌ BELUM")