"""Test tambahan bagian B (resolver dan analyzer): regresi per bug dan kasus tepi."""

from crud import ast_nodes as ast
from crud.analyzer import analyze_statement
from crud.parser import parse_sql
from crud.pipeline import analyze_source
from crud.resolver import Resolver


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