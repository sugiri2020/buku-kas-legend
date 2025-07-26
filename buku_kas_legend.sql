-- 1. Tabel users
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'user') NOT NULL DEFAULT 'user'
);

-- 2. Tambah user admin default
INSERT INTO users (username, password, role)
VALUES ('admin', MD5('admin123'), 'admin')
ON DUPLICATE KEY UPDATE username=username;

-- 3. Tabel members
CREATE TABLE IF NOT EXISTS members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nama VARCHAR(100) NOT NULL,
    kontak VARCHAR(100),
    alamat TEXT
);

-- 4. Tabel kas (dengan member_id, bukti_file, dan foreign key)
CREATE TABLE IF NOT EXISTS kas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tanggal DATE NOT NULL,
    keterangan VARCHAR(255) NOT NULL,
    jenis ENUM('masuk', 'keluar') NOT NULL,
    jumlah DECIMAL(15,2) NOT NULL,
    bukti_file VARCHAR(255),
    member_id INT,
    CONSTRAINT fk_kas_member FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE SET NULL
);
