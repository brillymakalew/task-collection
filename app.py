import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Pengumpulan Tugas Kelompok",
    layout="wide",
)

DB_PATH = "submissions.db"
UPLOAD_DIR = "uploads"

# =========================
# DB UTILS
# =========================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            class_name TEXT,
            group_name TEXT,
            notes TEXT,
            file_path TEXT,
            file_name TEXT,
            file_size INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def add_submission(class_name, group_name, notes, file_path, file_name, file_size):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO submissions (
            timestamp, class_name, group_name, notes, file_path, file_name, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            class_name,
            group_name,
            notes,
            file_path,
            file_name,
            file_size,
        ),
    )
    conn.commit()
    conn.close()


def get_all_submissions():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM submissions ORDER BY timestamp DESC", conn)
    conn.close()
    return df


# =========================
# FILE UTILS
# =========================
def sanitize_name(name: str) -> str:
    """Sederhanakan nama folder/file."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip())


def save_uploaded_file(uploaded_file, class_name, group_name):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    safe_class = sanitize_name(class_name)
    safe_group = sanitize_name(group_name)

    target_dir = os.path.join(UPLOAD_DIR, safe_class, safe_group)
    os.makedirs(target_dir, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{timestamp_str}_{sanitize_name(uploaded_file.name)}"
    file_path = os.path.join(target_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    file_size = len(uploaded_file.getbuffer())

    return file_path, uploaded_file.name, file_size


# =========================
# MAIN APP
# =========================
def main():
    init_db()

    st.title("📥 Pengumpulan Tugas Kelompok")

    tab_submit, tab_admin = st.tabs(["🧑‍🎓 Pengumpulan Tugas", "🧑‍💼 Admin Panel"])

    # -------------------------
    # TAB: STUDENT SUBMISSION
    # -------------------------
    with tab_submit:
        st.subheader("Form Pengumpulan Tugas")

        col1, col2 = st.columns(2)

        with col1:
            class_name = st.text_input("Nama Kelas", placeholder="misal: IF-2025-01")
        with col2:
            group_name = st.text_input("Nama Kelompok", placeholder="misal: Kelompok 3")

        uploaded_file = st.file_uploader("Upload File Tugas", type=None)
        notes = st.text_area("Catatan (opsional)", placeholder="Tulis catatan untuk dosen...")

        submit_button = st.button("Kumpulkan Tugas", type="primary")

        if submit_button:
            if not class_name.strip():
                st.error("Nama kelas tidak boleh kosong.")
            elif not group_name.strip():
                st.error("Nama kelompok tidak boleh kosong.")
            elif uploaded_file is None:
                st.error("Silakan upload file tugas terlebih dahulu.")
            else:
                # Simpan file
                file_path, original_name, file_size = save_uploaded_file(
                    uploaded_file, class_name, group_name
                )
                # Simpan ke database
                add_submission(
                    class_name.strip(),
                    group_name.strip(),
                    notes.strip(),
                    file_path,
                    original_name,
                    file_size,
                )
                st.success("✅ Tugas berhasil dikumpulkan!")
                st.info(
                    f"Kelas: **{class_name}** | Kelompok: **{group_name}**\n\n"
                    f"File: **{original_name}**"
                )

    # -------------------------
    # TAB: ADMIN PANEL
    # -------------------------
    with tab_admin:
        st.subheader("Admin Panel - Rekap Pengumpulan Tugas")

        df = get_all_submissions()
        if df.empty:
            st.warning("Belum ada tugas yang dikumpulkan.")
            return

        # Filter
        col1, col2 = st.columns(2)

        with col1:
            class_options = ["(Semua Kelas)"] + sorted(df["class_name"].unique().tolist())
            selected_class = st.selectbox("Filter berdasarkan kelas", class_options)

        if selected_class != "(Semua Kelas)":
            df_filtered = df[df["class_name"] == selected_class].copy()
        else:
            df_filtered = df.copy()

        with col2:
            if not df_filtered.empty:
                group_options = ["(Semua Kelompok)"] + sorted(
                    df_filtered["group_name"].unique().tolist()
                )
            else:
                group_options = ["(Semua Kelompok)"]

            selected_group = st.selectbox("Filter berdasarkan kelompok", group_options)

        if selected_group != "(Semua Kelompok)":
            df_filtered = df_filtered[df_filtered["group_name"] == selected_group]

        # Ringkasan kelas & kelompok yang sudah kumpul
        st.markdown("### ✅ Ringkasan Kelas & Kelompok yang Sudah Mengumpulkan")
        summary = (
            df.groupby(["class_name", "group_name"])
            .size()
            .reset_index(name="jumlah_tugas")
        )
        st.dataframe(summary, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📂 Daftar Tugas Terkumpul")

        # Tabel detail
        show_cols = ["timestamp", "class_name", "group_name", "file_name", "notes"]
        df_show = df_filtered[show_cols].rename(
            columns={
                "timestamp": "Waktu Submit",
                "class_name": "Kelas",
                "group_name": "Kelompok",
                "file_name": "Nama File",
                "notes": "Catatan",
            }
        )

        st.dataframe(df_show, use_container_width=True)

        st.markdown("#### Download Tugas per Baris")
        if df_filtered.empty:
            st.info("Tidak ada data sesuai filter.")
        else:
            # Download per baris
            for idx, row in df_filtered.iterrows():
                col_a, col_b, col_c, col_d = st.columns([3, 3, 3, 2])
                with col_a:
                    st.write(f"🕒 {row['timestamp']}")
                with col_b:
                    st.write(f"**Kelas:** {row['class_name']}")
                with col_c:
                    st.write(f"**Kelompok:** {row['group_name']}")
                with col_d:
                    file_path = row["file_path"]
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download",
                                data=f,
                                file_name=row["file_name"],
                                key=f"download_{row['id']}",
                            )
                    else:
                        st.error("File tidak ditemukan di server.")


if __name__ == "__main__":
    main()
