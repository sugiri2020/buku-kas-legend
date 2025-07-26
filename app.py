from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
import mysql.connector
import hashlib
from openpyxl import Workbook
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
import os
from werkzeug.utils import secure_filename

# Konfigurasi Flask
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Fungsi koneksi database (Railway menggunakan DATABASE_URL)
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise Exception("DATABASE_URL tidak ditemukan di environment variables.")
    
    result = urlparse(db_url)
    return mysql.connector.connect(
        host=result.hostname,
        user=result.username,
        password=result.password,
        database=result.path.lstrip('/'),
        port=result.port
    )

# Konfigurasi upload
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ------------------------- LOGIN -------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = hashlib.md5(request.form['password'].encode()).hexdigest()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['logged_in'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            error = 'Username atau password salah'
    return render_template('login.html', error=error)

# --------------------- AUTH DECORATOR ---------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ------------------------ DASHBOARD ------------------------
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT kas.*, members.nama AS nama_member
    FROM kas
    LEFT JOIN members ON kas.member_id = members.id
    ORDER BY kas.tanggal DESC
    """)
    kas = cursor.fetchall()

    cursor.execute("SELECT SUM(jumlah) FROM kas WHERE jenis = 'masuk'")
    total_masuk = cursor.fetchone()['SUM(jumlah)'] or 0

    cursor.execute("SELECT SUM(jumlah) FROM kas WHERE jenis = 'keluar'")
    total_keluar = cursor.fetchone()['SUM(jumlah)'] or 0

    saldo = total_masuk - total_keluar

    cursor.close()
    conn.close()
    return render_template('index.html', kas=kas, saldo=saldo)

# ---------------------- TAMBAH TRANSAKSI ----------------------
@app.route('/tambah', methods=['GET', 'POST'])
@login_required
def tambah():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        keterangan = request.form['keterangan']
        jenis = request.form['jenis']
        jumlah = request.form['jumlah']
        member_id = request.form.get('member_id')

        bukti_file = request.files.get('bukti_file')
        filename = None
        if bukti_file and allowed_file(bukti_file.filename):
            filename = secure_filename(bukti_file.filename)
            bukti_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        sql = """
            INSERT INTO kas (tanggal, keterangan, jenis, jumlah, bukti_file, member_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (tanggal, keterangan, jenis, jumlah, filename, member_id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/')
    else:
        cursor.execute("SELECT * FROM members")
        members = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("tambah.html", members=members)

# ---------------------- EKSPOR EXCEL ----------------------
@app.route('/export_excel')
@login_required
def export_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, keterangan, jenis, jumlah FROM kas ORDER BY tanggal ASC")
    data = cursor.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Tanggal", "Keterangan", "Jenis", "Jumlah (Rp)"])
    for row in data:
        ws.append(row)

    if not os.path.exists('laporan'):
        os.makedirs('laporan')
    filename = f"laporan/Laporan_Buku_Kas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)

    cursor.close()
    conn.close()
    return send_file(filename, as_attachment=True)

# ---------------------- EDIT TRANSAKSI ----------------------
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        tanggal = request.form['tanggal']
        keterangan = request.form['keterangan']
        jenis = request.form['jenis']
        jumlah = request.form['jumlah']
        cursor.execute("UPDATE kas SET tanggal=%s, keterangan=%s, jenis=%s, jumlah=%s WHERE id=%s",
                       (tanggal, keterangan, jenis, jumlah, id))
        conn.commit()
        flash('Kas berhasil diperbarui.', 'success')
        return redirect(url_for('index'))
    cursor.execute("SELECT * FROM kas WHERE id = %s", (id,))
    kas = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit.html', kas=kas)

# ---------------------- HAPUS TRANSAKSI ----------------------
@app.route('/hapus/<int:id>')
@login_required
def hapus(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kas WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Kas berhasil dihapus.', 'danger')
    return redirect(url_for('index'))

# ---------------------- MEMBER ROUTES ----------------------
@app.route('/members')
@login_required
def members():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM members ORDER BY id DESC")
    members = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('member/member.html', members=members)

@app.route('/add_member', methods=['POST'])
@login_required
def add_member():
    nama = request.form['nama']
    kontak = request.form['kontak']
    alamat = request.form['alamat']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO members (nama, kontak, alamat) VALUES (%s, %s, %s)", (nama, kontak, alamat))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/members')

@app.route('/edit_member/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        nama = request.form['nama']
        kontak = request.form['kontak']
        alamat = request.form['alamat']
        cursor.execute("UPDATE members SET nama=%s, kontak=%s, alamat=%s WHERE id=%s", (nama, kontak, alamat, id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/members')
    else:
        cursor.execute("SELECT * FROM members WHERE id = %s", (id,))
        member = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template('member/edit_member.html', member=member)

@app.route('/delete_member/<int:id>')
@login_required
def delete_member(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM members WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/members')

# ---------------------- LOGOUT ----------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------------------- RUN ----------------------
if __name__ == '__main__':
    app.run(debug=True)
