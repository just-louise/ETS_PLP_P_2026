"""Test tambahan bagian B (resolver dan analyzer): regresi per bug dan kasus tepi."""
import pytest
from crud import ast_nodes as ast
from crud.analyzer import analyze_statement
from crud.parser import parse_sql
from crud.pipeline import analyze_source
from crud.resolver import Resolver
from crud.lexer import LexError, TokenType as T, tokenize


def resolve(sql):
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    resolver = Resolver()
    diagnostics = resolver.resolve_script(script)
    return script, diagnostics, resolver


def columns(node):
    return [n for n in ast.iter_nodes(node) if isinstance(n, ast.ColumnRef)]


def crud(sql):
    script = parse_sql(sql)
    assert script.errors == [], script.errors
    return analyze_statement(script.statements[0])


# ======================================================================
# TEST REGRESI (satu per bug / TODO)
# ======================================================================

def test_regresi_shadowing_alias_subquery_pakai_scope_terdalam():
    # Bug resolver: _lookup mencari dari scope terluar, bukan terdalam (spek 4.3).
    script, diags, _ = resolve(
        "SELECT x.id FROM pelanggan x "
        "WHERE x.id IN (SELECT x.pelanggan_id FROM pesanan x)")
    hasil = {c.name: c.resolved for c in columns(script)}
    assert hasil["pelanggan_id"] == "pesanan"   # alias x di dalam = pesanan
    assert hasil["id"] == "pelanggan"           # alias x di luar = pelanggan
    assert diags == []


def test_regresi_scope_tidak_bocor_ke_statement_berikutnya():
    # Bug resolver: _delete membuat scope tapi tidak pernah pop (spek 4.5).
    script, diags, resolver = resolve(
        "DELETE FROM sesi s WHERE s.kedaluwarsa < :sekarang; "
        "SELECT s.id FROM pengguna u WHERE u.aktif = 1;")
    assert resolver.scope is None
    assert [d.level for d in diags] == ["error"]
    assert "'s'" in diags[0].message


def test_regresi_kolom_tanpa_qualifier_ambigu_jadi_warning():
    # T2: dua tabel di scope terdalam -> warning, resolved tetap None (spek 4.3).
    script, diags, _ = resolve("SELECT nama FROM pelanggan, pesanan")
    assert [c.resolved for c in columns(script)] == [None]
    assert [d.level for d in diags] == ["warning"]
    assert "ambigu" in diags[0].message


def test_regresi_kolom_tanpa_qualifier_di_update():
    # T2: kolom di SET dan WHERE UPDATE ikut ter-resolve ke tabel targetnya.
    script, diags, _ = resolve("UPDATE produk SET stok = stok - 1 WHERE id = 3")
    assert {c.resolved for c in columns(script)} == {"produk"}
    assert diags == []


def test_regresi_subquery_di_where_update_selalu_R():
    # Bug analyzer: tabel di subquery WHERE pada UPDATE dicatat U (spek 5: harus R).
    sql = ("UPDATE pesanan SET status = 'BATAL' "
           "WHERE pelanggan_id IN (SELECT id FROM pelanggan WHERE diblokir = 1)")
    assert crud(sql) == {"pesanan": {"U"}, "pelanggan": {"R"}}


def test_regresi_subquery_di_set_update_selalu_R():
    # Bug analyzer yang sama, versi subquery di bagian SET.
    assert crud("UPDATE a SET x = (SELECT y FROM b)") == {"a": {"U"}, "b": {"R"}}


# ======================================================================
# KASUS TEPI (pilih 3 untuk bagian B, sisanya cadangan)
# ======================================================================

def test_kasus_tepi_correlated_subquery_melihat_alias_luar():
    # Berisiko: kalau pencarian scope tidak naik ke induk, alias luar jadi "tidak terdefinisi".
    script, diags, _ = resolve(
        "SELECT p.id FROM pelanggan p "
        "WHERE EXISTS (SELECT 1 FROM pembayaran b WHERE b.pelanggan_id = p.id)")
    ref = {(c.qualifier, c.name): c.resolved for c in columns(script)}
    assert ref[("p", "id")] == "pelanggan"
    assert ref[("b", "pelanggan_id")] == "pembayaran"
    assert diags == []


def test_kasus_tepi_subquery_di_from_tidak_melihat_tabel_saudara():
    # Berisiko: spek 4.4, subquery di FROM di-resolve sebelum scope pembungkusnya dibuat.
    script, diags, _ = resolve(
        "SELECT d.id FROM pelanggan p, (SELECT p.id FROM pesanan o) d")
    assert [x.level for x in diags] == ["error"]
    assert "'p'" in diags[0].message
    luar = [c for c in columns(script) if c.qualifier == "d"][0]
    assert luar.resolved == "<subquery d>"


def test_kasus_tepi_matrix_urut_CRUD_gabungan_statement():
    # Berisiko: gabungan operasi antar statement harus berurutan C, R, U, D (spek 5).
    res = analyze_source(
        "UPDATE a SET x = 1 WHERE id IN (SELECT id FROM b);\nSELECT * FROM a;")
    assert res.matrix() == {"a": "RU", "b": "R"}


def test_kasus_tepi_nama_tabel_berskema_tanpa_alias():
    # Berisiko: tanpa alias, nama di scope = bagian terakhir nama tabel (spek 4.2),
    # tapi hasil resolve tetap nama lengkap dengan skema.
    script, diags, _ = resolve("SELECT pelanggan.id FROM crm.pelanggan")
    assert {c.resolved for c in columns(script)} == {"crm.pelanggan"}
    assert diags == []

# ======================================================================
# BAGIAN A (lexer dan parser): regresi per bug dan kasus tepi
# ======================================================================
def ekspresi_where(sql_kondisi):
    script = parse_sql("SELECT a FROM t WHERE " + sql_kondisi)
    assert script.errors == [], script.errors
    return script.statements[0].where
 
 
def test_regresi_lexer_keyword_tidak_peka_huruf_besar_kecil():
    # Bug lexer: keyword dicocokkan persis huruf besar (spek 2.2).
    toks = tokenize("select Select SELECT selection")
    assert [(t.type, t.value) for t in toks[:3]] == [(T.KEYWORD, "SELECT")] * 3
    assert toks[3].type == T.IDENT      # hanya diawali keyword -> tetap IDENT
 
 
def test_regresi_lexer_operator_tidak_sama_satu_token():
    # Bug lexer: '<' tidak melihat '>' sesudahnya, jadi '<>' terpecah (maximal munch, spek 2.5).
    toks = tokenize("a<>b a<=b a!=b")
    assert [t.value for t in toks if t.type == T.OP] == ["<>", "<=", "!="]
 
 
def test_regresi_lexer_dua_kutip_dalam_string_jadi_satu_kutip():
    # Bug lexer: '' menutup string, jadi 'O''Brien' terpecah jadi dua STRING (spek 2.4).
    toks = tokenize("'O''Brien'")
    assert [(t.type, t.value) for t in toks] == [(T.STRING, "O'Brien"), (T.EOF, "")]
 
 
def test_regresi_lexer_komentar_blok_lintas_baris_berisi_bintang():
    # T3: komentar blok belum didukung (spek 2.3).
    toks = tokenize("/* a * b\n c */ SELECT")
    assert (toks[0].type, toks[0].value, toks[0].line) == (T.KEYWORD, "SELECT", 2)
    with pytest.raises(LexError):
        tokenize("/* tidak ditutup")
 
 
def test_regresi_parser_and_lebih_kuat_dari_or():
    # Bug parser: AND dan OR berada di satu level, jadi urutan penulisan menentukan pohon (spek 3.1).
    node = ekspresi_where("a = 1 OR b = 2 AND c = 3")
    assert node.op == "OR"
    assert node.right.op == "AND"
 
 
def test_regresi_parser_recovery_lanjut_setelah_titik_koma():
    # Bug parser: _synchronize membuang token sampai akhir input (spek 6, panic mode).
    script = parse_sql("SELECT id nama, FROM x; UPDATE p SET a = 1; DELETE FROM k")
    assert len(script.errors) == 1
    assert [type(s).__name__ for s in script.statements] == ["Update", "Delete"]
 
 
def test_regresi_parser_insert_select():
    # T1: INSERT ... SELECT belum didukung (spek 3 dan 5).
    script = parse_sql("INSERT INTO crm.arsip (id) SELECT id FROM pesanan")
    assert script.errors == []
    ins = script.statements[0]
    assert ins.table.name == "crm.arsip" and ins.values == []
    assert ins.query.sources[0].name == "pesanan"
 
 
def test_regresi_parser_left_outer_join():
    # Bug parser: OUTER tidak dikenali setelah LEFT (grammar join: "LEFT" [ "OUTER" ]).
    script = parse_sql("SELECT a FROM t LEFT OUTER JOIN u ON t.id = u.id")
    assert script.errors == []
    assert script.statements[0].joins[0].kind == "LEFT"
 
 
def test_kasus_tepi_lexer_komentar_blok_hanya_slash_bintang_slash():
    # Berisiko: '/*/' bukan komentar utuh, karena '*' pembuka tidak boleh dipakai ulang sebagai penutup.
    with pytest.raises(LexError):
        tokenize("/*/ SELECT")
 
 
def test_kasus_tepi_parser_between_and_milik_between():
    # Berisiko: AND setelah BETWEEN harus dikonsumsi BETWEEN, bukan dianggap operator logika (spek 3.2).
    node = ekspresi_where("x BETWEEN 1 AND 5 AND y = 2")
    assert node.op == "AND"
    assert type(node.left).__name__ == "Between"
 
 
def test_kasus_tepi_parser_perbandingan_tidak_berantai():
    # Berisiko: 'a = 1 = 2' tidak boleh dibaca sebagai rantai; hanya statement itu yang error,
    # statement sesudahnya tetap diproses (spek 3.1 dan 6).
    script = parse_sql("SELECT a FROM t WHERE a = 1 = 2; SELECT b FROM u")
    assert len(script.errors) == 1
    assert len(script.statements) == 1