import os
import io
import zipfile
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

# Password admin (lebih baik di-set via ENV: ADMIN_PASSWORD)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# =========================
# DB UTILS
# =========================
def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Tabel submissions
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

    # Tabel master kelas
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT UNIQUE,
            is_active INTEGER DEFAULT 1
        )
        """
    )

    conn.commit()
    conn.close()


def add_submission(class_name, group_name, notes, file_path, file_name, file_size):
    conn = get_conn()
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
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM submissions ORDER BY timestamp DESC", conn)
    conn.close()
    return df


# ---------- MASTER KELAS ----------
def get_active_classes():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT class_name FROM classes WHERE is_active = 1 ORDER BY class_name ASC"
    )
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_all_classes_df():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT id, class_name, is_active FROM classes ORDER BY class_name ASC", conn
    )
    conn.close()
    return df


def add_class_name(class_name: str) -> bool:
    class_name = class_name.strip()
    if not class_name:
        return False

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO classes (class_name, is_active) VALUES (?, 1)",
            (class_name,),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


def set_class_active(class_id: int, active: bool):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE classes SET is_active = ? WHERE id = ?",
        (1 if active else 0, class_id),
    )
    conn.commit()
    conn.close()


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


def create_zip_from_df(df_filtered: pd.DataFrame) -> io.BytesIO:
    """
    Buat ZIP dari daftar file pada df_filtered.
    Struktur di dalam ZIP: Kelas/Kelompok/NamaFileAsli
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, row in df_filtered.iterrows():
            file_path = row["file_path"]
            if file_path and os.path.exists(file_path):
                class_name = sanitize_name(row["class_name"])
                group_name = sanitize_name(row["group_name"])
                file_name = row["file_name"] or os.path.basename(file_path)
                arcname = os.path.join(class_name, group_name, file_name)
                zf.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer


# =========================
# MAIN APP
# =========================
def main():
    init_db()

    # state untuk admin login
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False

    st.title("📥 Pengumpulan Tugas Kelompok")
    # Credit di bawah title
    st.caption('Built by [Brilly Andro](https://brillyandro.com)')

    # Credit juga di sidebar
    st.sidebar.markdown("#### 👨‍💻 Info")
    st.sidebar.markdown("by [Brilly Andro](https://brillyandro.com)")

    tab_submit, tab_admin = st.tabs(["🧑‍🎓 Pengumpulan Tugas", "🧑‍💼 Admin Panel"])

    # -------------------------
    # TAB: STUDENT SUBMISSION
    # -------------------------
    with tab_submit:
        st.subheader("Form Pengumpulan Tugas")

        # Ambil daftar kelas aktif
        active_classes = get_active_classes()

        col1, col2 = st.columns(2)

        with col1:
            if active_classes:
                class_name = st.selectbox(
                    "Nama Kelas",
                    active_classes,
                    placeholder="Pilih kelas...",
                )
            else:
                class_name = ""
                st.error(
                    "Belum ada master kelas yang aktif. "
                    "Silakan hubungi dosen/admin untuk menambahkan kelas terlebih dahulu."
                )

        with col2:
            group_name = st.text_input("Nama Lengkap", placeholder="misal: Kentaro Nareswara Putra Aji")

        uploaded_files = st.file_uploader(
            "Upload File Tugas (boleh lebih dari satu)",
            type=None,
            accept_multiple_files=True,
        )
        notes = st.text_area("Catatan (opsional)", placeholder="Tulis catatan untuk dosen...")

        submit_button = st.button("Kumpulkan Tugas", type="primary")

        if submit_button:
            if not active_classes:
                st.error(
                    "Tidak bisa submit karena belum ada kelas aktif. "
                    "Silakan hubungi admin."
                )
            elif not class_name:
                st.error("Silakan pilih nama kelas.")
            elif not group_name.strip():
                st.error("Nama kelompok tidak boleh kosong.")
            elif not uploaded_files:
                st.error("Silakan upload minimal satu file tugas terlebih dahulu.")
            else:
                saved_files_info = []
                for uf in uploaded_files:
                    file_path, original_name, file_size = save_uploaded_file(
                        uf, class_name, group_name
                    )
                    add_submission(
                        class_name.strip(),
                        group_name.strip(),
                        notes.strip(),
                        file_path,
                        original_name,
                        file_size,
                    )
                    saved_files_info.append(original_name)

                st.success(f"✅ {len(saved_files_info)} file tugas berhasil dikumpulkan!")
                st.info(
                    f"Kelas: **{class_name}** | Kelompok: **{group_name}**\n\n"
                    "File yang dikumpulkan:\n"
                    + "\n".join([f"- **{name}**" for name in saved_files_info])
                )

    # -------------------------
    # TAB: ADMIN PANEL (dengan login)
    # -------------------------
    with tab_admin:
        st.subheader("Admin Panel - Rekap & Master Data")

        # Jika belum login, tampilkan form login dulu
        if not st.session_state["is_admin"]:
            st.warning("Area ini hanya untuk admin. Silakan login terlebih dahulu.")
            password_input = st.text_input("Password Admin", type="password")
            login_button = st.button("Login Admin")

            if login_button:
                if password_input == ADMIN_PASSWORD:
                    st.session_state["is_admin"] = True
                    st.success("Login berhasil. Selamat datang, Admin!")
                else:
                    st.error("Password salah.")

            # stop di sini kalau belum login
            if not st.session_state["is_admin"]:
                return

        # Tombol logout
        st.sidebar.markdown("---")
        if st.sidebar.button("🔒 Logout Admin"):
            st.session_state["is_admin"] = False
            st.sidebar.success("Anda sudah logout sebagai admin.")

        # ---------- MASTER KELAS ----------
        st.markdown("### ⚙️ Kelola Master Kelas")

        with st.expander("Tambah & Kelola Kelas", expanded=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                new_class_name = st.text_input(
                    "Tambah Kelas Baru",
                    placeholder="misal: IF-2025-01",
                    key="add_class_name",
                )
            with col_b:
                if st.button("➕ Tambah Kelas"):
                    if not new_class_name.strip():
                        st.error("Nama kelas tidak boleh kosong.")
                    else:
                        ok = add_class_name(new_class_name)
                        if ok:
                            st.success(f'Kelas "{new_class_name}" berhasil ditambahkan / diaktifkan.')
                        else:
                            st.error("Gagal menambahkan kelas (mungkin sudah ada).")

            # Daftar semua kelas
            classes_df = get_all_classes_df()
            if classes_df.empty:
                st.info("Belum ada kelas di master data.")
            else:
                for _, row in classes_df.iterrows():
                    c1, c2, c3 = st.columns([4, 2, 2])
                    status_text = "Aktif ✅" if row["is_active"] == 1 else "Non-aktif ⚪"
                    with c1:
                        st.write(f"**{row['class_name']}**")
                    with c2:
                        st.write(status_text)
                    with c3:
                        if row["is_active"] == 1:
                            if st.button(
                                "Non-aktifkan",
                                key=f"deact_{row['id']}",
                            ):
                                set_class_active(row["id"], False)
                                st.rerun()
                        else:
                            if st.button(
                                "Aktifkan",
                                key=f"act_{row['id']}",
                            ):
                                set_class_active(row["id"], True)
                                st.rerun()

        st.markdown("---")

        # ---------- DATA SUBMISSION ----------
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

        # -------------------------
        # BULK DOWNLOAD (ZIP)
        # -------------------------
        st.markdown("#### ⬇️ Bulk Download (ZIP)")

        if df_filtered.empty:
            st.info("Tidak ada data sesuai filter untuk di-download.")
        else:
            zip_buffer = create_zip_from_df(df_filtered)
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            if selected_class != "(Semua Kelas)":
                base_name = f"tugas_{sanitize_name(selected_class)}"
                if selected_group != "(Semua Kelompok)":
                    base_name += f"_{sanitize_name(selected_group)}"
            else:
                base_name = "tugas_semua_kelas"

            zip_file_name = f"{base_name}_{timestamp_str}.zip"

            st.download_button(
                label="📦 Download semua tugas sebagai ZIP (sesuai filter)",
                data=zip_buffer,
                file_name=zip_file_name,
                mime="application/zip",
            )

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
