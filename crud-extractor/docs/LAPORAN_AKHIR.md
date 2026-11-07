# Laporan Akhir

## 1. Hasil evaluasi

```
Dievaluasi: audit.sql, campuran_error.sql, laporan_penjualan.sql, pemeliharaan.sql (27 triple)

Metode Precision Recall F1
parser 1.00 1.00 1.00
regex 0.65 0.81 0.72

[regex]
salah ditemukan (FP): ('audit.sql', 16, 'sesi', 'R')
salah ditemukan (FP): ('campuran_error.sql', 4, 'pesanan', 'R')
salah ditemukan (FP): ('campuran_error.sql', 8, 'keranjang', 'R')
salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'D')
salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pelanggan', 'R')
salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'pesanan', 'R')
salah ditemukan (FP): ('laporan_penjualan.sql', 2, 'rahasia', 'R')
salah ditemukan (FP): ('laporan_penjualan.sql', 15, 'pesanan', 'R')
salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.alamat', 'R')
salah ditemukan (FP): ('pemeliharaan.sql', 2, 'crm.pelanggan', 'R')
salah ditemukan (FP): ('pemeliharaan.sql', 2, 'pelanggan_lama', 'U')
salah ditemukan (FP): ('pemeliharaan.sql', 15, 'crm.alamat', 'R')
terlewat (FN): ('audit.sql', 2, 'pesanan', 'R')
terlewat (FN): ('laporan_penjualan.sql', 3, 'pelanggan', 'R')
terlewat (FN): ('laporan_penjualan.sql', 3, 'pesanan', 'R')
terlewat (FN): ('pemeliharaan.sql', 3, 'crm.alamat', 'R')
terlewat (FN): ('pemeliharaan.sql', 3, 'crm.pelanggan', 'R') 
```
## 2. Tiga kasus di mana regex salah


1. Komentar dan Literal String yang Memuat Kata Kunci SQL
   sql:
   -- DELETE FROM pelanggan
    SELECT p.nama, SUM(o.total) AS omzet
    FROM pelanggan p
    JOIN pesanan o ON o.pelanggan_id = p.id
    WHERE o.status = 'LUNAS' AND o.catatan <> 'FROM rahasia'
    GROUP BY p.nama;
   Kesalahan regex:
   regex menghasilkan 2 False Positive nyata di evaluate.py: ('laporan_penjualan.sql', 2, 'pelanggan', 'D') karena mencocokkan teks komentar -- DELETE FROM pelanggan, dan ('laporan_penjualan.sql', 2, 'rahasia', 'R') karena mencocokkan kata FROM rahasia di dalam literal string 'FROM rahasia'.
   Mengapa Parser Benar:
   Konsep Lexing (Bab 4): Lexer membuang komentar secara bersih (-- atau `/* ... */`) sehingga tidak menghasilkan token. Selain itu, teks 'SELECT _ FROM pesanan' dikenali sebagai satu token literal STRING, bukan rentetan kata kunci KEYWORD, sehingga parser tidak pernah menganggapnya sebagai klausul query.
2. Klausa `FROM` pada Statement `DELETE` Terbaca Ganda sebagai Operasi  `R` SQL (`audit.sql` baris 16):
   sql:
   DELETE FROM sesi s WHERE s.kedaluwarsa < :sekarang;
   Kesalahan regex:
   Di evaluate.py muncul False Positive ('audit.sql', 16, 'sesi', 'R'). Regex menjalankan semua pola di _PATTERNS secara terpisah pada teks statement yang sama, sehingga potongan FROM sesi cocok dengan dua pola sekaligus: pola DELETE\s+FROM (dicatat D) dan pola FROM biasa (sehingga ikut dicatat R).
   Mengapa Parser Benar:
  Konsep Parsing (Bab 6): Saat token pertama adalah keyword DELETE, parser langsung masuk ke aturan grammar _delete yang mengenali FROM sesi sebagai tabel target penghapusan pada node ast.Delete, bukan sebagai klausa FROM pada query SELECT.
3.Tabel Kedua pada Klausa `FROM` Dipisah Koma Terlewat (False Negative)
  SQL (`audit.sql` baris 2):
  SELECT p.id, p.nama
  FROM pelanggan p, pesanan o
  WHERE o.pelanggan_id = p.id ...
  Kesalahan regex:
  Di evaluate.py muncul False Negative terlewat (FN): ('audit.sql', 2, 'pesanan', 'R'). Pola regex FROM\s+([a-zA-Z_][\w.]*) hanya menangkap satu nama tabel tepat setelah kata kunci FROM (pelanggan), tetapi gagal mengenali tabel kedua (pesanan) yang dipisahkan tanda koma
  Mengapa Parser Benar:
  Konsep Parsing & Grammar (Bab 5 & 6): Sesuai aturan grammar from_clause -> "FROM" table_ref ( "," table_ref )*, fungsi _from_clause di parser memakai loop while self._match(T.COMMA): untuk membaca semua table_ref setelah koma dan menyimpannya ke dalam list sources pada node ast.Select.

## 3. Batas pendekatan kami

Minimal tiga hal yang **tidak bisa** ditangani dengan benar oleh tool ini meskipun semua bug
sudah diperbaiki. Untuk tiap batas: contoh SQL atau situasinya, akibatnya pada CRUD matrix,
dan informasi apa yang dibutuhkan untuk mengatasinya.

1. **Tidak adanya skema database untuk kolom tanpa qualifier di multi-tabel**

  **Contoh SQL:**
  ```sql
  SELECT nama, total
  FROM pelanggan, pesanan
  WHERE pelanggan.id = pesanan.pelanggan_id;
  ```

  **Akibat pada CRUD Matrix:**
  Tool tidak tahu apakah kolom `nama` dan `total` milik tabel `pelanggan` atau `pesanan`.
  Akibatnya, tool menghasilkan peringatan kolom ambigu dengan `resolved = None`.
  Jika tool membutuhkan pemetaan kolom ke tabel secara granular (`--kolom`), relasinya
  hilang atau tidak terpetakan.

  **Informasi yang dibutuhkan:**
  Katalog skema database (definisi tabel dan kolom/DDL) untuk mengetahui tabel mana
  yang memiliki kolom `nama` dan `total`.

2. **Ketiadaan dukungan Common Table Expressions (CTE/`WITH`)**

  **Contoh SQL:**
  ```sql
  WITH ringkasan AS (
     SELECT pelanggan_id, SUM(total) AS belanja
     FROM pesanan
     GROUP BY pelanggan_id
  )
  SELECT p.nama, r.belanja
  FROM pelanggan p
  JOIN ringkasan r ON p.id = r.pelanggan_id;
  ```

  **Akibat pada CRUD Matrix:**
  Karena grammar proyek tidak mendukung klausa `WITH` (di luar lingkup SPESIFIKASI
  bagian 9), parser akan melempar `ParseError` dan mengabaikan statement tersebut.
  Akibatnya, operasi `R` pada `pesanan` dan `pelanggan` sama sekali tidak tercatat
  dalam matrix.

  **Informasi yang dibutuhkan:**
  Perluasan aturan grammar pada parser untuk mengenali klausa `WITH [alias] AS (...)`,
  serta penanganan CTE pada resolver sebagai virtual table/temporary scope.

3. **Resolusi wildcard (`*`) tanpa qualifier**

  **Contoh SQL:**
  ```sql
  SELECT *
  FROM pelanggan p
  JOIN pesanan o ON p.id = o.pelanggan_id;
  ```

  **Akibat pada CRUD Matrix:**
  Meskipun tool berhasil menandai operasi `R` pada `pelanggan` dan `pesanan` pada
  level tabel, dalam mode audit detail kolom (`--kolom`) tool tidak dapat mengetahui
  kolom apa saja yang sebenarnya dibaca oleh aplikasi. AST hanya mencatat node
  `ast.Star()` tanpa daftar nama kolom.

  **Informasi yang dibutuhkan:**
  Metadata skema database untuk melakukan ekspansi wildcard `*` menjadi daftar kolom
  nyata (`p.id`, `p.nama`, ..., `o.id`, `o.total`).

## 4. Pembagian kerja

### Pengerjaan Kode

Pair programming dilakukan dengan pergantian peran sebagai berikut:

- **Luis Danang Pambudi (Anggota A)**
  - **Driver awal:** jam ke-1 (Orientasi & CLI), jam ke-3 (Parser), dan jam ke-5 (lexer).
  - **Navigator awal:** jam ke-2 (analyxer) dan jam ke-4 (Resolver).
- **Muhammad Rafi Al Rabbani (Anggota B)**
  - **Driver awal:** jam ke-2 (analyzer) dan jam ke-4 (Resolver).
  - **Navigator awal:** jam ke-1 (Orientasi & CLI), jam ke-3 (Parser), dan jam ke-5 (lexer).

**Peran di lapangan:**

- **Driver** mengetik kode implementasi dan tes regresi.
- **Navigator** meninjau kepatuhan grammar terhadap `SPESIFIKASI.md`, memastikan solusi menyentuh akar masalah (bukan sekadar gejala), dan memvalidasi commit Git untuk setiap bug.

### Tanggung Jawab Dokumen

Penulis draf dan penelaah dokumen dibagi sebagai berikut:

- **`LAPORAN_BUG.md`**
  - Bug 1–6 (Lexer & Parser): penulis draf Luis Danang Pambudi (A), penelaah Muhammad Rafi Al Rabbani (B).
  - Bug 7–9 (Resolver & Analyzer): penulis draf Muhammad Rafi Al Rabbani (B), penelaah Luis Danang Pambudi (A).
- **`KARTU_DESAIN.md`** (5 Keputusan Desain)
  - Keputusan 1, 3, dan 5 ditulis oleh Luis Danang Pambudi (A).
  - Keputusan 2 dan 4 ditulis oleh Muhammad Rafi Al Rabbani (B).
- **`LAPORAN_AKHIR.md`** (Evaluasi, Analisis Regex, Batas Pendekatan)
  - Penulis draf Muhammad Rafi Al Rabbani (B), ditelaah dan diverifikasi oleh Luis Danang Pambudi (A).
- **`LOG_AI.md`**
  - Masing-masing anggota mencatat interaksi dan konfirmasi konsep saat memakai AI, lalu saling memeriksa catatan pada akhir pengerjaan.
