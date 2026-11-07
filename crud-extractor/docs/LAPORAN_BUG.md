# Laporan Bug

Salin blok di bawah untuk setiap bug. Bagian **Akar masalah** wajib ditulis dengan kata-kata
sendiri dan memakai konsep dari _Crafting Interpreters_ (sebutkan bab). Bagian ini diuji lisan.

> Daftar bug: 9 entri (6 oleh A di lexer dan parser, 3 oleh B di resolver dan analyzer).
> Tiga TODO (T1, T2, T3) bukan bug; penyelesaiannya dicatat singkat di lampiran di bagian akhir.
> Bagian bertanda `TODO-ISI` harus diisi sendiri sebelum dikumpulkan. Hapus catatan ini setelah semuanya terisi.

---

## Bug 1: Keyword huruf kecil dibaca sebagai IDENT (lexer)

**Ditemukan oleh:** Luis Danang Pambudi · **Diperbaiki oleh:** Luis Danang Pambudi

**Gejala.** Input `select id from t`. Didapat: token pertama `IDENT 'select'`. Diharapkan (SPESIFIKASI.md bagian 2.2): keyword tidak peka huruf besar/kecil, token `KEYWORD` bernilai `SELECT`.

**Reproduksi minimal.**

```sql
select a from t
```

**Akar masalah.** engacu pada konsep Bab 4 (Scanning - Reserved Words and Identifiers), lexer membedakan identifier biasa dan reserved word dengan mencocokkan teks string lexeme terhadap tabel/himpunan kata kunci (lookup table). Pada implementasi awal, lexer memeriksa string masukan secara persis (case-sensitive) ke dalam himpunan KEYWORDS yang didefinisikan dalam huruf kapital. Akibatnya, masukan berkasus huruf kecil seperti select tidak cocok dengan entri "SELECT", sehingga salah diklasifikasikan sebagai token IDENT biasa.

**Perbaikan.** Pada crud/lexer.py, di fungsi \_word, teks hasil pemindaian diubah menjadi huruf besar terlebih dahulu menggunakan text.upper() sebelum diperiksa keanggotaannya di KEYWORDS. Jika cocok, token dibuat dengan tipe TokenType.KEYWORD dan nilainya dinormalisasi ke text.upper().

**Test regresi.** `test_regresi_lexer_keyword_tidak_peka_huruf_besar_kecil`

**Peran AI.** digunakan untuk brainstorming memeriksa pola penanganan reserved word di Bab 4 buku Crafting Interpreters. Logika normalisasi text.upper() diimplementasikan dan diverifikasi secara manual menggunakan suite uji pytest test_regresi_lexer_keyword_tidak_peka_huruf_besar_kecil.

---

## Bug 2: Operator `<>` terpecah jadi dua token (lexer)

**Ditemukan oleh:** Luis Danang Pambudi · **Diperbaiki oleh:** Luis Danang Pambudi

**Gejala.** `a<>b` menghasilkan token `<` lalu `>`. Parser lalu melihat `>` berdiri sendiri dan gagal: `laporan_penjualan.sql` berhenti dengan error "Baris 6, kolom 41: diharapkan ekspresi, ditemukan '>'". Menurut bagian 2.5, `<>` harus satu token.

**Reproduksi minimal.**

```sql
SELECT a FROM t WHERE a <> 1
```

**Akar masalah.** Sesuai prinsip Bab 4 (Scanning - Operators & Maximal Munch), ketika scanner membaca karakter operator yang berpotensi memiliki dua karakter, scanner wajib melakukan lookahead (mengintip karakter berikutnya) guna memilih token terpanjang yang valid (maximal munch). Pada kode awal fungsi \_scan_token, percabangan karakter < hanya mengecek apakah karakter berikutnya adalah = (untuk membentuk <=), namun tidak memeriksa kemungkinan karakter >. Akibatnya, <> diperlakukan sebagai dua token terpisah: < diikuti oleh >, yang menyebabkan parser gagal saat mengharapkan ekspresi operand setelah operator biner <.

**Perbaikan.** Pada crud/lexer.py di fungsi \_scan_token, percabangan penanganan ch == "<" diperluas dengan menambahkan kondisi pengecekan elif self.\_match(">"): op = "<>" sebelum jatuh ke nilai default < .

**Test regresi.** `test_regresi_lexer_operator_tidak_sama_satu_token`

**Peran AI.** menjelaskan materi yang belum di pahami pada diagram percabangan lalu mengidentifikasi bug nya dari penjelasan tersebut

---

## Bug 3: Dua kutip di dalam string menutup string

**Ditemukan oleh:** Luis Danang Pambudi · **Diperbaiki oleh:** Luis Danang Pambudi

**Gejala.** `'O''Brien'` menghasilkan dua token STRING (`O` dan `Brien`). Menurut bagian 2.4, dua kutip berturut-turut berarti satu karakter kutip, jadi harusnya satu token `O'Brien`.

**Reproduksi minimal.**

```sql
SELECT a FROM t WHERE nama = 'O''Brien'
```

**Akar masalah.** Sesuai Bab 4 (Scanning - String Literals & Escape Sequences), scanner harus mengenali konvensi penulisan karakter pembatas di dalam literal (escape mechanism). Dalam SQL, tanda petik tunggal di-escape dengan menuliskan dua tanda petik berurutan (''). Pada implementasi awal \_string, saat lexer menemukan karakter ', ia langsung mengasumsikannya sebagai akhir literal tanpa melakukan lookahead pada karakter berikutnya. Akibatnya, 'O''Brien' terbaca sebagai string 'O', disusul string tak lengkap 'Brien'.

**Perbaikan.** Pada crud/lexer.py di fungsi \_string, ketika karakter petik tunggal ' ditemukan, fungsi melakukan pemeriksaan if self.\_peek() == "'":. Jika ya, karakter petik kedua langsung dikonsumsi menggunakan self.\_advance(), karakter tunggal ' ditambahkan ke buffer string hasil, dan loop pemindaian string terus berlanjut tanpa keluar dari fungsi.

**Test regresi.** `test_regresi_lexer_dua_kutip_dalam_string_jadi_satu_kutip`

**Peran AI.** AI digunakan untuk membandingkan mekanisme escape sequence Lox (\n, dsb.) dengan konvensi petik ganda SQL. Logika diterapkan dan divalidasi langsung melalui test test_regresi_lexer_dua_kutip_dalam_string_jadi_satu_kutip.

---

## Bug 4: AND dan OR berada di satu tingkat presedensi

**Ditemukan oleh:** Luis Danang Pambudi · **Diperbaiki oleh:** Luis Danang Pambudi

**Gejala.** `a = 1 OR b = 2 AND c = 3` dibaca dengan `AND` di akar pohon. Menurut bagian 3.1, `AND` lebih kuat dari `OR`, jadi akarnya harus `OR` dan `AND` ada di cabang kanan. Terlihat di `--ast` pada `audit.sql` baris 2.

**Reproduksi minimal.**

```sql
SELECT a FROM t WHERE a = 1 OR b = 2 AND c = 3
```

**Akar masalah.** Mengacu pada konsep Bab 6 (Parsing Expressions - Ambiguity, Precedence, and Stratified Grammars), teknik recursive descent mewajibkan setiap tingkatan presedensi operator memiliki fungsi aturan tata bahasa (grammar rule) terpisah secara bertingkat. Operator dengan presedensi lebih rendah harus memanggil aturan operator dengan presedensi lebih tinggi agar operator yang lebih kuat mengikat lebih ketat (bind tighter). Pada kode awal, parser menyatukan penanganan AND dan OR ke dalam satu fungsi \_logical, sehingga keduanya dianggap memiliki presedensi setara dan dievaluasi murni secara asosiatif kiri dari kiri ke kanan.

**Perbaikan.** Pada crud/parser.py, fungsi \_logical dihapus dan dipecah secara bertingkat menjadi \_or (tingkat presedensi terendah) dan \_and (tingkat presedensi lebih tinggi). Fungsi \_expr kini memanggil \_or(), di mana \_or memanggil \_and() sebagai operand-nya, dan \_and memanggil \_not().

**Test regresi.** `test_regresi_parser_and_lebih_kuat_dari_or`

**Peran AI.** Tidak ada; pengelompokkan gramar langsung diadaptasi dari struktur equality -> comparison -> term -> factor pada Bab 6 buku acuan dan diverifikasi dengan pytest test_regresi_parser_and_lebih_kuat_dari_or.

---

## Bug 5: Error recovery membuang semua token sampai akhir file

**Ditemukan oleh:** Luis Danang pambudi · **Diperbaiki oleh:** Luis Danang Pambudi

**Gejala.** Input SELECT id nama, FROM x; UPDATE p SET a = 1; DELETE FROM k. Didapat: 1 error dan 0 statement. Diharapkan (bagian 6): satu error untuk statement rusak, dan UPDATE serta DELETE sesudahnya tetap diproses. Terlihat di campuran_error.sql: produk U dan keranjang D hilang dari matrix.

**Reproduksi minimal.**

```sql
SELECT id nama, FROM x; UPDATE p SET a = 1; DELETE FROM k
```

Hasil lama: 1 error dan 0 statement. Seharusnya: 1 error, lalu `Update` dan `Delete` tetap terbaca.

**Akar masalah.** Sesuai konsep Bab 6 (Parsing Expressions - Panic Mode Error Recovery & Synchronize), saat menemukan kesalahan sintaksis, parser harus memasuki mode panik dan membuang token (discard tokens) hingga menemukan titik batas sinkronisasi yang aman (dalam SQL berupa tanda titik koma ; sebagai pemisah statement) agar parser dapat pulih dan melanjutkan pemrosesan statement berikutnya. Pada implementasi awal \_synchronize, perulangan pembuangan token tidak berhenti saat menemukan token ; melainkan terus maju hingga mencapai TokenType.EOF. Akibatnya, seluruh statement sah setelah statement yang rusak ikut terbuang.

**Perbaikan.** Pada crud/parser.py, logika \_synchronize diperbaiki sehingga perulangan membaca token akan segera berhenti (return) persis setelah mengonsumsi token TokenType.SEMICOLON:
while not self.\_at_end():
if self.\_advance().type == T.SEMICOLON:
return

**Test regresi.** `test_regresi_parser_recovery_lanjut_setelah_titik_koma`

**Peran AI.** AI digunakan untuk menganalisis perbandingan implementasi sinkronisasi statement pada Crafting Interpreters Bab 6 dengan penanganan titik koma SQL. Solusi diverifikasi dengan menjalankan pengujian test_regresi_parser_recovery_lanjut_setelah_titik_koma.

---

## Bug 6: LEFT OUTER JOIN ditolak

**Ditemukan oleh:** Luis Danang Pambudi · **Diperbaiki oleh:** Luis Danang Pambudi

**Gejala.** `LEFT OUTER JOIN` menghasilkan error "diharapkan JOIN, ditemukan 'OUTER'". Menurut grammar, `OUTER` setelah `LEFT` boleh ada.

**Reproduksi minimal.**

```sql
SELECT a FROM t LEFT OUTER JOIN u ON t.id = u.id
```

**Akar masalah.** Berdasarkan Bab 6 (Parsing Expressions - Recursive Descent Parser & Matching Grammar Rules), setiap percabangan kode parser harus memetakan aturan tata bahasa (grammar rules) secara presisi, termasuk elemen opsional (? atau [...]). Grammar untuk klausa join mendefinisikan bentuk "LEFT" [ "OUTER" ] JOIN. Namun fungsi \_join awalnya hanya mencocokkan kata kunci LEFT lalu langsung mewajibkan kata kunci JOIN berikutnya melalui \_expect_kw("JOIN"). Ketika kata kunci opsional OUTER muncul di antara LEFT dan JOIN, parser menganggapnya sebagai pelanggaran sintaksis.

**Perbaikan.** `crud/parser.py`, fungsi `_join`: setelah `LEFT`, tambahkan `_match_kw("OUTER")`. Alternatif: menjadikan `LEFT OUTER` satu token di lexer. Tidak dipilih karena itu mengubah daftar token yang sudah ditetapkan spek.

**Test regresi.** `test_regresi_parser_left_outer_join`

**Peran AI.** digunakan untuk menjelaskan aturan gramar dan memverifikasi/menganalisis dengan bug yang ada di program

---

## Bug 7: Alias di subquery dicari dari scope terluar

**Ditemukan oleh:** (isi) · **Diperbaiki oleh:** Muhammad Rafi Al Rabbani

**Gejala.** Di `audit.sql` baris 12, alias `x` dipakai di query luar (`pelanggan`) dan di subquery (`pesanan`). Di subquery, `x.pelanggan_id` di-resolve ke `pelanggan`, padahal seharusnya `pesanan` (SPESIFIKASI 4.3: alias di subquery menutupi alias luar).

**Reproduksi minimal.**

```sql
SELECT x.id FROM pelanggan x
WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x);
```

**Akar masalah.** (tulis ulang dengan kata sendiri) Resolver mencari alias dari scope paling luar dulu. Seharusnya dari scope paling dalam, karena scope itu tumpukan (stack): yang terakhir dibuka dicek pertama. Di kode, daftar scope dikumpulkan dari dalam ke luar lalu dibalik dengan `reversed()`, sehingga urutannya jadi luar ke dalam. Konsep: Crafting Interpreters Bab 11 (variabel dicari dari scope terdalam ke luar).

**Perbaikan.** `crud/resolver.py`, fungsi `_lookup`: langsung berjalan dari scope sekarang ke induknya dan berhenti di yang pertama ketemu. Alternatif: tetap memakai list dan menghapus `reversed()`. Tidak dipilih karena list tidak diperlukan, loop langsung lebih sederhana.

**Test regresi.** `test_regresi_shadowing_alias_subquery_pakai_scope_terdalam`

**Peran AI.** AI membantu menunjukkan lokasi bug dan menyiapkan perbaikannya. Diverifikasi dengan: test gagal sebelum perbaikan dan lulus sesudahnya, lalu `--ast` pada `audit.sql` dicek ulang (`x.pelanggan_id` jadi `-> pesanan`).

---

## Bug 8: Scope DELETE bocor ke statement berikutnya

**Ditemukan oleh:** (isi) · **Diperbaiki oleh:** Muhammad Rafi Al Rabbani

**Gejala.** Di `audit.sql` baris 18, `SELECT s.id FROM pengguna u ...` di-resolve `s.id -> sesi` tanpa diagnostik. Alias `s` berasal dari `DELETE ... sesi s` di baris 16. Seharusnya error "alias 's' tidak terdefinisi" (SPESIFIKASI 4.5: setiap statement berdiri sendiri).

**Reproduksi minimal.**

```sql
DELETE FROM sesi s WHERE s.kedaluwarsa < :sekarang;
SELECT s.id FROM pengguna u WHERE u.aktif = 1;
```

**Akar masalah.** (tulis ulang dengan kata sendiri) Fungsi `_delete` membuat scope baru (`_push`) tetapi tidak pernah menutupnya (`_pop`). Scope DELETE tersisa dan jadi induk dari scope statement berikutnya, jadi alias `s` masih ditemukan. Membuka scope harus selalu dipasangkan dengan menutupnya. Konsep: Crafting Interpreters Bab 11 (beginScope dan endScope harus seimbang).

**Perbaikan.** `crud/resolver.py`, fungsi `_delete`: tambah `self._pop()` di akhir. Alternatif: mereset `self.scope = None` di tiap statement pada `resolve_script`. Tidak dipilih karena itu hanya menutupi gejala, penyebabnya (push dan pop tidak seimbang) tetap ada.

**Test regresi.** `test_regresi_scope_tidak_bocor_ke_statement_berikutnya`

**Peran AI.** AI membantu membandingkan `_update` dan `_delete` dan menemukan `_pop` yang hilang. Diverifikasi dengan: test gagal sebelum perbaikan dan lulus sesudahnya, plus cek `resolver.scope is None` di akhir.

---

## Bug 9: Subquery di UPDATE dicatat sebagai U

**Ditemukan oleh:** (isi) · **Diperbaiki oleh:** Muhammad Rafi Al Rabbani

**Gejala.** Pada `UPDATE pesanan ... WHERE pelanggan_id IN (SELECT id FROM pelanggan ...)`, tabel `pelanggan` dicatat `U`. Seharusnya `R` (SPESIFIKASI bagian 5: membaca tabel lewat subquery selalu R, apa pun statement luarnya).

**Reproduksi minimal.**

```sql
UPDATE pesanan SET status = 'BATAL'
WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1);
```

**Akar masalah.** (tulis ulang dengan kata sendiri) Analyzer memakai huruf `U` untuk semua tabel yang ditemukan di dalam statement UPDATE, termasuk tabel di subquery. Padahal `U` hanya untuk tabel target. Tabel yang hanya dibaca lewat subquery harus `R`. Jadi huruf operasi target tercampur dengan huruf operasi tabel yang dibaca. Konsep: Crafting Interpreters Bab 5 (penelusuran AST, tiap bagian pohon diberi operasi sesuai perannya).

**Perbaikan.** `crud/analyzer.py`, cabang `Update` di `analyze_statement`: dua panggilan `_collect` (nilai SET dan WHERE) diganti dari `"U"` ke `"R"`. Alternatif: fungsi khusus untuk UPDATE. Tidak dipilih karena berlebihan, cukup mengganti hurufnya.

**Test regresi.** `test_regresi_subquery_di_where_update_selalu_R` dan `test_regresi_subquery_di_set_update_selalu_R`

**Peran AI.** AI membantu membaca analyzer terhadap tabel di SPESIFIKASI bagian 5. Diverifikasi dengan: test gagal sebelum perbaikan dan lulus sesudahnya.

---

## TODO

| Kode | Isi                                        | Diselesaikan oleh Test   |
| ---- | ------------------------------------------ | ------------------------ | -------------------------------------------------------------------------------------------------------- |
| T1   | `INSERT ... SELECT` di parser              | Luis Danang Pambudi      | `test_regresi_parser_insert_select`                                                                      |
| T2   | Resolusi kolom tanpa qualifier di resolver | Muhammad Rafi Al Rabbani | `test_regresi_kolom_tanpa_qualifier_ambigu_jadi_warning`, `test_regresi_kolom_tanpa_qualifier_di_update` |
| T3   | Komentar blok `/* ... */` di lexer         | Luis Danang Pambudi      | `test_regresi_lexer_komentar_blok_lintas_baris_berisi_bintang`                                           |
