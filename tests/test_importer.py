"""
Tests for genome import parsing and allele orientation handling.

Covers the correctness-critical paths that everything downstream depends on:
- multi-format genome import (23andMe combined genotype, Ancestry/MyHeritage split alleles)
- delimiter and column-layout auto-detection
- indel / single-allele / no-call normalization
- minus-strand allele flipping at display time
"""
import os
import tempfile

import pytest

from GenomeImporter import (
    detect_delimiter,
    normalize_genotype,
    parse_genome_file,
)


# ── normalize_genotype ───────────────────────────────────────────────────────

@pytest.mark.parametrize("a1, a2, expected", [
    ("A", "G", "(A;G)"),          # standard heterozygous
    ("C", "C", "(C;C)"),          # homozygous
    ("a", "g", "(A;G)"),          # lowercase normalized to upper
    ("A", "", "(A;A)"),           # single-allele call -> mirrored
    ("A", "-", "(A;A)"),          # dash second allele -> mirrored
    ("-", "-", "(-;-)"),          # explicit no-call
    ("0", "0", "(-;-)"),          # Ancestry '0' no-call -> dash
    ("", "", "(-;-)"),            # empty -> no-call
    ("D", "I", "(D;I)"),          # indel markers preserved
    ("X", "G", "(-;G)"),          # unrecognized allele -> dash
])
def test_normalize_genotype(a1, a2, expected):
    assert normalize_genotype(a1, a2) == expected


# ── detect_delimiter ─────────────────────────────────────────────────────────

def test_detect_delimiter_tab():
    lines = ["# comment", "rs1\t1\t100\tAG"]
    assert detect_delimiter(lines) == "\t"


def test_detect_delimiter_comma():
    lines = ["# comment", "rs1,1,100,A,G"]
    assert detect_delimiter(lines) == ","


def test_detect_delimiter_defaults_to_tab():
    assert detect_delimiter(["# only comments", ""]) == "\t"


# ── parse_genome_file (full-file, format autodetection) ──────────────────────

def _write_tmp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_parse_23andme_combined_genotype():
    """23andMe: tab-separated, 4 columns, combined genotype field."""
    content = (
        "# rsid\tchromosome\tposition\tgenotype\n"
        "rs53576\t3\t8804371\tAG\n"
        "rs1815739\t11\t66560624\tCC\n"
        "rs6152\tX\t66765627\tA\n"     # single-allele X call
        "rs9999999\t1\t12345\t--\n"    # no-call
    )
    path = _write_tmp(content)
    try:
        result = parse_genome_file(path)
    finally:
        os.remove(path)

    assert result["rs53576"] == "(A;G)"
    assert result["rs1815739"] == "(C;C)"
    assert result["rs6152"] == "(A;A)"      # mirrored single allele
    assert result["rs9999999"] == "(-;-)"   # no-call


def test_parse_ancestry_split_alleles():
    """AncestryDNA: tab-separated, 5 columns, two allele columns."""
    content = (
        "# AncestryDNA raw data\n"
        "rsid\tchromosome\tposition\tallele1\tallele2\n"
        "rs53576\t3\t8804371\tA\tG\n"
        "rs1815739\t11\t66560624\tC\tC\n"
        "rs6152\tX\t66765627\tA\t0\n"   # Ancestry '0' -> mirrored single allele
    )
    path = _write_tmp(content)
    try:
        result = parse_genome_file(path)
    finally:
        os.remove(path)

    assert result["rs53576"] == "(A;G)"
    assert result["rs1815739"] == "(C;C)"
    assert result["rs6152"] == "(A;A)"   # '0' collapses to dash, then mirrored


def test_parse_myheritage_comma_separated():
    """MyHeritage / FamilyTreeDNA: comma-separated, quoted, split alleles."""
    content = (
        "# MyHeritage raw data\n"
        '"RSID","CHROMOSOME","POSITION","RESULT1","RESULT2"\n'
        '"rs53576","3","8804371","A","G"\n'
        '"rs1815739","11","66560624","C","T"\n'
    )
    path = _write_tmp(content)
    try:
        result = parse_genome_file(path)
    finally:
        os.remove(path)

    assert result["rs53576"] == "(A;G)"
    assert result["rs1815739"] == "(C;T)"


# ── format_user_allele (minus-strand flipping, from app.py) ──────────────────

def test_format_user_allele_minus_strand_flip():
    from app import format_user_allele

    # plus strand: unchanged (but sorted)
    assert format_user_allele("(A;G)", "plus") == "(A;G)"
    # minus strand: complement each allele, then sort -> A;G -> T;C -> sorted (C;T)
    assert format_user_allele("(A;G)", "minus") == "(C;T)"
    # non-genotype strings pass through untouched
    assert format_user_allele("Unknown", "minus") == "Unknown"
