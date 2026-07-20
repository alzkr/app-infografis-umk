import streamlit as st

# Import modul yang sudah kita buat
import modul_qam 
import modul_cuaca

# 1. Konfigurasi Halaman (WAJIB diletakkan paling atas)
st.set_page_config(
    page_title="OpsMeteo Dashboard",
    page_icon="☁️",
    layout="wide" # Menggunakan layout penuh (wide)
)

# 2. Header Utama Dashboard
st.title("☁️ OpsMeteo Dashboard")
st.markdown("**Pantauan Operasional Laporan (QAM) dan Infografis Cuaca Terpadu**")
st.markdown("---")

# 3. Membuat Layout 2 Kolom (Kiri dan Kanan)
# Rasio [1.2, 1] memberikan sedikit ruang ekstra (lebih lebar) untuk QAM karena banyak input form
kolom_kiri, kolom_kanan = st.columns([1.2, 1], gap="large")

# ==========================================
# SECTION KIRI: LAPORAN QAM
# ==========================================
with kolom_kiri:
    # Menggunakan container bergaris agar terlihat rapi seperti kotak dashboard
    with st.container(border=True):
        # Memanggil seluruh antarmuka QAM dari file modul_qam.py
        modul_qam.tampilkan_ui_qam()

# ==========================================
# SECTION KANAN: INFOGRAFIS CUACA (Placeholder)
# ==========================================
with kolom_kanan:
    with st.container(border=True):
        # Memanggil fungsi dari modul cuaca
        modul_cuaca.tampilkan_ui_cuaca()