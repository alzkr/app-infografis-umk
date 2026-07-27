import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ==========================================
# 1. INISIALISASI DATABASE (SUPABASE)
# ==========================================
@st.cache_resource
def get_db_engine():
    # Mengambil URL database dari .streamlit/secrets.toml
    db_url = st.secrets["connections"]["supabase"]["url"]
    return create_engine(db_url)

def init_db_cuaca():
    engine = get_db_engine()
    with engine.connect() as conn:
        # Menggunakan SERIAL untuk auto-increment dan BYTEA untuk BLOB di PostgreSQL
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS riwayat_cuaca (
                id SERIAL PRIMARY KEY,
                waktu_template TEXT,
                tanggal_str TEXT,
                jam_str TEXT,
                cuaca TEXT,
                suhu TEXT,
                arah_angin TEXT,
                kecepatan TEXT,
                gambar_blob BYTEA,
                waktu_dibuat TIMESTAMP
            )
        '''))
        conn.commit()
    return engine

# ==========================================
# 2. FUNGSI GENERATE INFOGRAFIS (GAMBAR)
# ==========================================
def generate_infografis(data):
    # Format cuaca dan waktu agar aman untuk nama file (huruf kecil & garis bawah)
    cuaca_format = data['cuaca'].lower().replace(" ", "_")
    waktu_format = data['waktu'].lower()
    
    nama_file_bg = f"template_{cuaca_format}_{waktu_format}.png"
    
    try:
        # --- LOAD BACKGROUND MOCKUP ---
        try:
            bg = Image.open(nama_file_bg).convert("RGBA")
        except FileNotFoundError:
            # Background dummy jika file template spesifik tidak ditemukan
            bg = Image.new('RGBA', (1500, 2000), color=(80, 160, 180, 255)) 
            
        draw = ImageDraw.Draw(bg)
        
        # --- LOAD CUSTOM FONTS ---
        try:
            # FONT 1: KHUSUS NILAI ANGKA PADA DATA
            font_angka_60 = ImageFont.truetype("spartan.ttf", 175)
            font_angka_40 = ImageFont.truetype("spartan.ttf", 120)
            
            # FONT 2: KHUSUS TEKS & WAKTU
            font_teks_bln_thn = ImageFont.truetype("rubik.ttf", 27)
            font_teks_jam = ImageFont.truetype("rubik.ttf", 35)
            font_teks_tanggal = ImageFont.truetype("rubik.ttf", 88)
            font_teks_angin = ImageFont.truetype("rubik.ttf", 47)
            font_teks_cuaca = ImageFont.truetype("rubik.ttf", 87)
            
        except Exception as e:
            st.warning(f"Font kustom gagal dimuat. Error: {e}")
            font_angka_60 = ImageFont.load_default()
            font_angka_40 = ImageFont.load_default()
            font_teks_bln_thn = ImageFont.load_default()
            font_teks_jam = ImageFont.load_default()
            font_teks_tanggal = ImageFont.load_default()
            font_teks_angin = ImageFont.load_default()
            font_teks_cuaca = ImageFont.load_default()


        # --- DRAWING TEXT & WAKTU (HEADER) ---
        draw.text((1150, 300), data['bulan_tahun'], font=font_teks_bln_thn, fill="#FFFFFF")
        
        draw.text(
            (1107, 357), 
            data['tanggal'], 
            font=font_teks_tanggal, 
            fill="#000000",
            stroke_width=2,         
            stroke_fill="#000000"   
        )
        
        # Memisahkan jam dan zona waktu
        jam_pecah = data['jam_lengkap'].split(" ") 
        angka_jam = jam_pecah[0]  
        zona_waktu = jam_pecah[1] 
        
        draw.text((1220, 365), angka_jam, font=font_teks_jam, fill="#000000")
        draw.text((1220, 410), zona_waktu, font=font_teks_jam, fill="#000000")
        
        
        # --- LOGIKA PERATAAN TENGAH DINAMIS UNTUK SUHU & CUACA ---
        titik_tengah_x = 740 
        
        # 1. Suhu Utama
        teks_suhu = f"{data['suhu']}°"
        lebar_suhu = draw.textlength(teks_suhu, font=font_angka_60)
        pos_x_suhu = int(titik_tengah_x - (lebar_suhu / 2))
        draw.text((pos_x_suhu, 957), teks_suhu, font=font_angka_60, fill="#FFFFFF")

        # 2. Cuaca Utama
        teks_cuaca = data['cuaca']
        lebar_cuaca = draw.textlength(teks_cuaca, font=font_teks_cuaca)
        pos_x_cuaca = int(titik_tengah_x - (lebar_cuaca / 2))
        
        draw.text(
            (pos_x_cuaca, 1115), 
            teks_cuaca, 
            font=font_teks_cuaca, 
            fill="#ffffff",
            stroke_width=2,         
            stroke_fill="#ffffff"   
        )
        

        # --- DRAWING NILAI ANGKA (KIRI & KANAN) ---
        # Kiri (Rata Kiri Default)
        draw.text((149, 1387), f"{data['titik_embun']}°", font=font_angka_60, fill="#FFFFFF")
        draw.text((128, 1745), str(data['tekanan']), font=font_angka_40, fill="#FFFFFF")

        # Kanan (Logika Rata Kanan Khusus)
        batas_kanan_kelembapan = 710 
        batas_kanan_jarak = 693
        
        # Kelembapan
        teks_kelembapan = str(data['kelembapan'])
        lebar_kelembapan = draw.textlength(teks_kelembapan, font=font_angka_60)
        pos_x_kelembapan = int(batas_kanan_kelembapan - lebar_kelembapan)
        draw.text((pos_x_kelembapan, 1387), teks_kelembapan, font=font_angka_60, fill="#FFFFFF")
        
        # Jarak Pandang
        teks_jarak = str(data['jarak_pandang'])
        lebar_jarak = draw.textlength(teks_jarak, font=font_angka_60)
        pos_x_jarak = int(batas_kanan_jarak - lebar_jarak)
        draw.text((pos_x_jarak, 1732), teks_jarak, font=font_angka_60, fill="#FFFFFF")
        

        # --- LOGIKA ANGIN & JARUM KOMPAS (PEMBARUAN) ---
        titik_tengah_angin_x = 1117 
        arah_teks = str(data['arah_teks']).strip()
        
        try:
            nilai_knot = float(data['kecepatan'] if data['kecepatan'] else 0)
        except ValueError:
            nilai_knot = 0
            
        # Pengecekan Kondisi Angin
        kondisi_calm = (nilai_knot == 0) or (arah_teks.upper() == "CALM")
        
        if kondisi_calm:
            # === JIKA CALM ===
            # Hanya cetak 1 baris teks "Calm" tepat di tengah area (Y: 1803)
            teks_angin = "Calm"
            lebar_angin = draw.textlength(teks_angin, font=font_teks_angin)
            pos_x_angin = int(titik_tengah_angin_x - (lebar_angin / 2))
            
            draw.text((pos_x_angin, 1803), teks_angin, font=font_teks_angin, fill="#FFFF00")
            
            # Note: Kita TIDAK mengeksekusi blok kode tempel jarum kompas di sini.
            
        else:
            # === JIKA TIDAK CALM (BERANGIN) ===
            # 1. Baris Atas: Arah Angin Teks (Y: 1776)
            teks_tampil_arah = f"dari {arah_teks}"
            lebar_arah = draw.textlength(teks_tampil_arah, font=font_teks_angin)
            pos_x_arah = int(titik_tengah_angin_x - (lebar_arah / 2))
            draw.text((pos_x_arah, 1776), teks_tampil_arah, font=font_teks_angin, fill="#FFFF00")
            
            # 2. Baris Bawah: Kecepatan Konversi km/jam (Y: 1830)
            nilai_kmj = round(nilai_knot * 1.852)
            teks_kecepatan = f"{nilai_kmj} km/jam"
            
            lebar_kecepatan = draw.textlength(teks_kecepatan, font=font_teks_angin)
            pos_x_kecepatan = int(titik_tengah_angin_x - (lebar_kecepatan / 2))
            draw.text((pos_x_kecepatan, 1830), teks_kecepatan, font=font_teks_angin, fill="#FFFF00")

            # 3. Proses Putaran & Penempelan Jarum Kompas
            try:
                jarum = Image.open("jarum_kompas.png").convert("RGBA")
                
                # Resize Jarum
                lebar_baru = 400
                tinggi_baru = 400
                jarum = jarum.resize((lebar_baru, tinggi_baru), Image.Resampling.LANCZOS)
                
                # Memutar Jarum (Counter-Clockwise untuk Pillow)
                jarum_diputar = jarum.rotate(-float(data['arah_derajat']), resample=Image.BICUBIC, expand=True) 
                
                # Hitung posisi paste agar jarum tepat di tengah kompas (Y: 1500)
                w_jarum, h_jarum = jarum_diputar.size
                titik_pusat_y = 1500  
                
                pos_x_jarum = int(titik_tengah_angin_x - (w_jarum / 2))
                pos_y_jarum = int(titik_pusat_y - (h_jarum / 2))
                
                # Paste jarum ke background
                bg.paste(jarum_diputar, (pos_x_jarum, pos_y_jarum), mask=jarum_diputar)
                
            except FileNotFoundError:
                pass


        # --- KONVERSI HASIL KE BYTES ---
        img_byte_arr = io.BytesIO()
        bg.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
        
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses gambar: {e}")
        return None

# ==========================================
# 3. FUNGSI UTAMA ANTARMUKA (UI)
# ==========================================
def tampilkan_ui_cuaca():
    engine = init_db_cuaca()

    st.markdown("### 🌤️ Generator Infografis Cuaca")
    st.caption("Masukkan data meteorologi terkini untuk membuat infografis.")

    # ------------------------------------------
    # PEMBAGIAN TAB UI
    # ------------------------------------------
    tab_input, tab_db = st.tabs(["📝 Buat & Simpan", "🗄️ Riwayat Database"])
    
    # === TAB 1: FORM INPUT ===
    with tab_input:
        now = datetime.now()
        
        bulan_indo = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
        
        kamus_arah_angin = {
            "Calm": 0, "Utara": 0, "Timur Laut": 45, "Timur": 90, "Tenggara": 135,
            "Selatan": 180, "Barat Daya": 225, "Barat": 270, "Barat Laut": 315,
            "Berubah-ubah (Variabel)": 0
        }
        
        # Logika Konversi Derajat QAM ke Arah Teks Default
        qam_arah = st.session_state.get("qam_arah_angin", "").strip()
        default_idx_arah = 0 
        
        if qam_arah:
            if qam_arah.upper() in ["0", "00", "000", "CALM"]:
                default_idx_arah = 0
            elif qam_arah.upper() in ["VRB", "VARIABEL", "9"]:
                default_idx_arah = 9 
            else:
                try:
                    d = int(qam_arah)
                    if 25 <= d <= 65: default_idx_arah = 2   
                    elif 70 <= d <= 110: default_idx_arah = 3 
                    elif 115 <= d <= 155: default_idx_arah = 4 
                    elif 160 <= d <= 200: default_idx_arah = 5 
                    elif 205 <= d <= 245: default_idx_arah = 6 
                    elif 250 <= d <= 295: default_idx_arah = 7 
                    elif 296 <= d <= 335: default_idx_arah = 8 
                    elif d >= 340 or d <= 20: default_idx_arah = 1 
                except ValueError:
                    pass
                    
        pilihan_jam_ops = [f"{str(h).zfill(2)}:00" for h in range(7, 18)]
        
        # Mengambil Data dari Session QAM (Jika Ada)
        qnh_qam = st.session_state.get("qam_qnh", "")
        if qnh_qam:
            try:
                qnh_qam = str(int(float(qnh_qam))) 
            except ValueError:
                pass
                
        # --- FORM BUILDER ---
        with st.form("form_infografis"):
            st.markdown("**Data Waktu & Cuaca**")
            
            sekarang = datetime.now()
            pilihan_tanggal = [str(i) for i in range(1, 32)]
            pilihan_bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
            pilihan_tahun = [str(i) for i in range(2024, 2035)]
            
            idx_tgl = sekarang.day - 1
            idx_bln = sekarang.month - 1
            try:
                idx_thn = pilihan_tahun.index(str(sekarang.year))
            except ValueError:
                idx_thn = 2 
                
            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
            
            tanggal = col_t1.selectbox("Tanggal", pilihan_tanggal, index=idx_tgl)
            bulan = col_t2.selectbox("Bulan", pilihan_bulan, index=idx_bln)
            tahun = col_t3.selectbox("Tahun", pilihan_tahun, index=idx_thn)
            jam_dipilih = col_t4.selectbox("Jam", pilihan_jam_ops)
            
            bulan_tahun = f"{bulan} {tahun}"
            
            daftar_cuaca = [
                "Cerah", "Cerah Berawan", "Berawan", "Berawan Tebal", 
                "Hujan Ringan", "Hujan Sedang", "Hujan Lebat", "Petir", 
                "Hujan Petir", "Udara Kabur", "Kabut", "Kabut Asap"
            ]
            cuaca = st.selectbox("Kondisi Cuaca Utama (Menentukan Ikon & Template)", daftar_cuaca)

            st.markdown("---")
            st.markdown("**Parameter Cuaca Utama**")
            col_c1, col_c2 = st.columns(2)
            suhu = col_c1.text_input("Suhu Utama (°C)", value=st.session_state.get("qam_suhu", ""))
            titik_embun = col_c2.text_input("Titik Embun (°C)", value=st.session_state.get("qam_titik_embun", ""))
            
            col_p1, col_p2, col_p3 = st.columns(3)
            kelembapan = col_p1.text_input("Kelembapan (%)") 
            tekanan = col_p2.text_input("Tekanan QNH (mb)", value=qnh_qam) 
            jarak_pandang = col_p3.text_input("Jarak Pandang (km)", value=st.session_state.get("qam_visibilitas", ""))
            
            st.markdown("**Data Angin**")
            col_a1, col_a2 = st.columns(2)
            arah_teks = col_a1.selectbox("Arah Angin (Dari)", list(kamus_arah_angin.keys()), index=default_idx_arah) 
            kecepatan = col_a2.text_input("Kecepatan (Knot)", value=st.session_state.get("qam_kec_angin", ""))
            
            submit_btn = st.form_submit_button("🎨 Buat Gambar & Simpan ke DB", type="primary", use_container_width=True)

        # --- AKSI KETIKA TOMBOL SUBMIT DITEKAN ---
        if submit_btn:
            jam_angka = int(jam_dipilih.split(":")[0])
            if 7 <= jam_angka < 11:
                waktu_template = "Pagi"
            elif 11 <= jam_angka < 15:
                waktu_template = "Siang"
            else: 
                waktu_template = "Sore"
                
            derajat_asal = kamus_arah_angin[arah_teks]
            derajat_kompas = (derajat_asal + 180) % 360
            
            jam_lengkap = f"{jam_dipilih} WITA"
            
            data_cuaca = {
                "waktu": waktu_template, 
                "cuaca": cuaca,
                "bulan_tahun": bulan_tahun, 
                "tanggal": tanggal, 
                "jam_lengkap": jam_lengkap,
                "suhu": suhu, 
                "titik_embun": titik_embun, 
                "kelembapan": kelembapan,
                "tekanan": tekanan, 
                "jarak_pandang": jarak_pandang,
                "arah_teks": arah_teks, 
                "arah_derajat": derajat_kompas, 
                "kecepatan": kecepatan
            }
            
            # Panggil fungsi generate
            gambar_hasil = generate_infografis(data_cuaca)
            
            if gambar_hasil:
                waktu_dibuat = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with engine.connect() as conn:
                    # Cek apakah data jam dan tanggal ini sudah ada di DB
                    query_cek = text("SELECT id FROM riwayat_cuaca WHERE tanggal_str=:tgl AND jam_str=:jam")
                    existing = conn.execute(query_cek, {"tgl": tanggal, "jam": jam_dipilih}).fetchone()
                    
                    if existing:
                        # Update/Timpa data lama
                        query_update = text('''
                            UPDATE riwayat_cuaca SET 
                            waktu_template=:wkt, cuaca=:cuaca, suhu=:suhu, arah_angin=:arah, 
                            kecepatan=:kec, gambar_blob=:img, waktu_dibuat=:buat
                            WHERE tanggal_str=:tgl AND jam_str=:jam
                        ''')
                        conn.execute(query_update, {
                            "wkt": waktu_template, "cuaca": cuaca, "suhu": suhu, "arah": arah_teks,
                            "kec": kecepatan, "img": gambar_hasil, "buat": waktu_dibuat,
                            "tgl": tanggal, "jam": jam_dipilih
                        })
                        st.toast("Data yang sama ditemukan, gambar berhasil diperbarui di Database!", icon="🔄")
                    else:
                        # Insert data baru
                        query_insert = text('''
                            INSERT INTO riwayat_cuaca 
                            (waktu_template, tanggal_str, jam_str, cuaca, suhu, arah_angin, kecepatan, gambar_blob, waktu_dibuat)
                            VALUES (:wkt, :tgl, :jam, :cuaca, :suhu, :arah, :kec, :img, :buat)
                        ''')
                        conn.execute(query_insert, {
                            "wkt": waktu_template, "tgl": tanggal, "jam": jam_dipilih,
                            "cuaca": cuaca, "suhu": suhu, "arah": arah_teks, "kec": kecepatan,
                            "img": gambar_hasil, "buat": waktu_dibuat
                        })
                        st.toast("Infografis baru berhasil disimpan ke Database!", icon="✅")
                    
                    conn.commit()

                # Tampilan Sukses di Antarmuka
                st.success(f"✅ Gambar siap! Silakan salin ke WhatsApp.")
                st.info("💡 **TIPS COPY KE WA:** Klik Kanan pada gambar di bawah, lalu pilih **'Copy image'** (Salin Gambar), kemudian buka WhatsApp dan tekan **Ctrl+V (Paste)**.")
                
                st.image(gambar_hasil, caption="Preview Hasil Infografis", use_container_width=True)
                
                st.download_button(
                    label="⬇️ Download Gambar (PNG)",
                    data=gambar_hasil,
                    file_name=f"Infografis_{waktu_template}_{cuaca}_{tanggal}.png",
                    mime="image/png",
                    use_container_width=True
                )

    # === TAB 2: DATABASE ===
    with tab_db:
        st.markdown("**🗄️ Data Infografis Historis**")
        
        # Menampilkan tabel data menggunakan pandas dan SQLAlchemy
        with engine.connect() as conn:
            df = pd.read_sql_query(text('''
                SELECT id, tanggal_str as Tanggal, jam_str as Jam, waktu_template as Waktu, 
                       cuaca as Cuaca, suhu as Suhu, arah_angin as Angin, waktu_dibuat as Dibuat_Pada
                FROM riwayat_cuaca ORDER BY id DESC
            '''), conn)
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("**Lihat Kembali Gambar Historis**")
        
        col_id, col_btn = st.columns([1, 3])
        id_lihat = col_id.number_input("Masukkan ID Gambar yang ingin dilihat:", min_value=0, step=1)
        
        if col_btn.button("Tampilkan Gambar dari Database"):
            with engine.connect() as conn:
                query_lihat = text("SELECT gambar_blob, tanggal_str, jam_str FROM riwayat_cuaca WHERE id=:id_gambar")
                hasil = conn.execute(query_lihat, {"id_gambar": id_lihat}).fetchone()
                
            if hasil and hasil[0]:
                st.info("💡 Klik kanan dan pilih 'Copy image' untuk mengirim ulang ke grup WhatsApp.")
                st.image(hasil[0], caption=f"Gambar dari Database - Tanggal {hasil[1]} Jam {hasil[2]} WITA", use_container_width=True)
            else:
                st.warning(f"Gambar dengan ID {id_lihat} tidak ditemukan di database.")