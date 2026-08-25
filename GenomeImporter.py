import argparse
import os
import json
import time

# Valid single-base alleles plus indel/no-call markers used by DTC providers.
VALID_ALLELES = {"A", "T", "C", "G", "-", "I", "D"}


def detect_delimiter(sample_lines: list) -> str:
    """
    Sniffs the column delimiter from the first non-comment data lines.

    Ancestry and 23andMe use tabs; MyHeritage / FamilyTreeDNA use commas.
    Falls back to tab (the most common raw-data format) when ambiguous.
    """
    for line in sample_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if '\t' in stripped:
            return '\t'
        if ',' in stripped:
            return ','
    return '\t'


def normalize_genotype(allele1: str, allele2: str) -> str:
    """
    Builds a SNPedia-style ``(A;G)`` genotype from one or two allele columns,
    validating each allele and collapsing anything unrecognized to a no-call.

    Handles:
    - Two-allele layouts (Ancestry / MyHeritage): allele1='A', allele2='G'
    - Single-allele calls (X/Y/mtDNA): allele2 empty -> mirror allele1
    - No-calls: '-', '0', '', or unrecognized tokens -> '(-;-)'
    """
    a1 = (allele1 or '').strip().upper()
    a2 = (allele2 or '').strip().upper()

    # Ancestry encodes no-calls as '0'; treat it like a dash.
    a1 = '-' if a1 in ('', '0') else a1
    a2 = '-' if a2 in ('', '0') else a2

    # Single-allele call: mirror the first allele (e.g. male X 'A' -> (A;A)).
    if a2 == '-' and a1 != '-':
        a2 = a1

    if a1 not in VALID_ALLELES:
        a1 = '-'
    if a2 not in VALID_ALLELES:
        a2 = '-'

    return f"({a1};{a2})"


def _split_combined_genotype(raw_genotype: str) -> tuple:
    """
    Splits a 23andMe combined genotype field ('AG', 'A', '--') into two alleles.
    """
    raw = (raw_genotype or '').strip()
    if len(raw) >= 2:
        return raw[0], raw[1]
    if len(raw) == 1:
        return raw, raw
    return '-', '-'


def parse_genome_file(filepath: str) -> dict:
    """
    Reads a raw DNA text file and extracts SNPs and genotypes, auto-detecting
    the provider format.

    Supported layouts (after the provider's ``#`` comment block):
    - 23andMe:   rsid, chromosome, position, genotype        (tab, 4 columns, combined genotype)
    - Ancestry:  rsid, chromosome, position, allele1, allele2 (tab, 5 columns, split alleles)
    - MyHeritage / FamilyTreeDNA: same columns, comma-separated

    Properly handles indels (D/I), single-allele calls on X/Y/mtDNA, and no-calls.
    """
    snp_dict = {}

    print(f"Reading genome file: {filepath}...")
    start_time = time.time()

    with open(filepath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    delimiter = detect_delimiter(lines[:50])
    delim_name = 'tab' if delimiter == '\t' else 'comma'
    layout = None  # '23andme' (combined genotype) or 'split' (two allele columns)

    for line in lines:
        stripped = line.strip()

        # Skip provider comment block and blank lines.
        if not stripped or stripped.startswith('#'):
            continue

        columns = [c.strip() for c in stripped.split(delimiter)]

        # Skip header rows (e.g. MyHeritage quotes/labels its header).
        if columns[0].lower().strip('"') in ('rsid', 'rs id'):
            continue

        if len(columns) < 4:
            continue

        rsid = columns[0].strip().strip('"').lower()
        if not rsid:
            continue

        # Decide the layout once, from the first real data row.
        if layout is None:
            layout = 'split' if len(columns) >= 5 else '23andme'
            print(f"Detected format: {delim_name}-separated, "
                  f"{'Ancestry-style split alleles' if layout == 'split' else '23andMe combined genotype'}.")

        if layout == 'split':
            allele1 = columns[3].strip().strip('"')
            allele2 = columns[4].strip().strip('"') if len(columns) > 4 else ''
            genotype = normalize_genotype(allele1, allele2)
        else:
            a1, a2 = _split_combined_genotype(columns[3].strip().strip('"'))
            genotype = normalize_genotype(a1, a2)

        snp_dict[rsid] = genotype

    elapsed_time = round(time.time() - start_time, 2)
    print(f"Processed {len(snp_dict):,} SNPs in {elapsed_time} seconds.")

    return snp_dict


# Backwards-compatible alias: the original function name.
def parse_23andme_file(filepath: str) -> dict:
    """Deprecated alias for :func:`parse_genome_file` (now multi-format)."""
    return parse_genome_file(filepath)


def export_to_json(data: dict, output_filepath: str):
    """Saves the dictionary to a JSON file."""
    try:
        with open(output_filepath, "w", encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=4)
        print(f"Success! Data exported to: {output_filepath}")
    except IOError as e:
        print(f"Error saving file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert raw DNA text files (23andMe, Ancestry, MyHeritage) into a JSON dictionary."
    )
    parser.add_argument('-f', '--filepath', help='Path to the raw DNA text file', required=True)
    parser.add_argument('-o', '--output', help='Name of the output JSON file', default='snpDict.json')

    args = parser.parse_args()

    if not os.path.exists(args.filepath):
        print(f"Error: Could not find the input file at '{args.filepath}'")
    else:
        extracted_snps = parse_genome_file(args.filepath)

        if extracted_snps:
            export_to_json(extracted_snps, args.output)
        else:
            print("Error: No valid SNPs found. Ensure this is a valid 23andMe/Ancestry raw data file.")
