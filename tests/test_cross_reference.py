"""Tests for cross_reference.py — pure regex logic, no DB required."""

from lex_retriever.cross_reference import extract_references


def test_extract_single_bgb():
    refs = extract_references("Haftung nach § 280 Abs. 1 BGB")
    assert len(refs) == 1
    assert refs[0]["paragraph"] == "§ 280"
    assert refs[0]["law"] == "BGB"


def test_extract_two_refs():
    refs = extract_references("§ 280 Abs. 1 BGB und § 823 BGB")
    assert len(refs) == 2
    assert all(r["law"] == "BGB" for r in refs)


def test_extract_art_dsgvo():
    refs = extract_references("gemäß Art. 6 DSGVO")
    assert len(refs) == 1
    assert refs[0]["paragraph"] == "Art. 6"
    assert refs[0]["law"] == "DSGVO"


def test_default_law_fallback():
    refs = extract_references("§ 241 Abs. 2", default_law="BGB")
    assert len(refs) == 1
    assert refs[0]["law"] == "BGB"


def test_double_paragraph_sign():
    refs = extract_references("§§ 280, 281 BGB")
    assert len(refs) >= 1
    assert refs[0]["law"] == "BGB"


def test_no_law_without_default():
    refs = extract_references("gemäß § 123")
    assert len(refs) == 1
    assert refs[0]["law"] is None


def test_raw_field_preserved():
    refs = extract_references("Haftung nach § 280 Abs. 1 BGB")
    assert "280" in refs[0]["raw"]


def test_unknown_abbreviation_not_used_as_law():
    refs = extract_references("§ 280 Foobar")
    assert refs[0]["law"] is None


def test_absatz_variant():
    refs = extract_references("§ 242 Absatz 1 BGB")
    assert len(refs) == 1
    assert refs[0]["law"] == "BGB"
