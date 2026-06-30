import argparse
import os
import json
import time

def _genotype_from_columns(columns: list) -> str:
    """
    Builds a '(A;B)' genotype string from a raw data row, handling both formats:
      - 23andMe:    rsid, chromosome, position, genotype   (alleles joined: 'AG')
      - AncestryDNA: rsid, chromosome, position, allele1, allele2  (split: 'A','G')
    No-calls ('0' for AncestryDNA, '-' for 23andMe) yield '(-;-)'. A single-allele
    23andMe call (haploid X/Y/mtDNA) becomes homozygous, e.g. 'A' -> '(A;A)'.
    """
    no_call = ('0', '-', '')

    if len(columns) >= 5:
        # AncestryDNA: two separate allele columns. Treat the row as a no-call
        # unless both alleles are real bases, so a half-called site never gets
        # turned into a spurious homozygote.
        a1, a2 = columns[3].strip().upper(), columns[4].strip().upper()
        if a1 in no_call or a2 in no_call:
            return "(-;-)"
        return f"({a1};{a2})"

    # 23andMe: a single combined-genotype column ('AG'); '--' is a no-call.
    alleles = columns[3].strip().upper().replace('-', '')
    if len(alleles) == 2:
        return f"({alleles[0]};{alleles[1]})"
    if len(alleles) == 1:
        return f"({alleles[0]};{alleles[0]})"
    return "(-;-)"


def parse_genome_file(filepath: str) -> dict:
    """
    Reads a raw 23andMe or AncestryDNA DNA text file line-by-line and extracts
    SNPs and genotypes. The column layout is auto-detected per row, so both
    formats (and their indel/single-allele calls) are handled correctly.
    """
    snp_dict = {}

    print(f"Reading raw DNA file: {filepath}...")
    start_time = time.time()

    with open(filepath, 'r') as file:
        for line in file:
            # Skip comment blocks and the column header line
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or stripped.lower().startswith('rsid'):
                continue

            columns = stripped.split("\t")

            # Both formats start: rsid, chromosome, position, allele(s)...
            if len(columns) < 4:
                continue

            rsid = columns[0].strip().lower()
            snp_dict[rsid] = _genotype_from_columns(columns)

    elapsed_time = round(time.time() - start_time, 2)
    print(f"Processed {len(snp_dict):,} SNPs in {elapsed_time} seconds.")

    return snp_dict


def export_to_json(data: dict, output_filepath: str):
    """Saves the dictionary to a JSON file."""
    try:
        with open(output_filepath, "w") as jsonfile:
            json.dump(data, jsonfile, indent=4)
        print(f"Success! Data exported to: {output_filepath}")
    except IOError as e:
        print(f"Error saving file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a raw 23andMe or AncestryDNA text file into a JSON dictionary.")
    parser.add_argument('-f', '--filepath', help='Path to the raw 23andMe or AncestryDNA text file', required=True)
    parser.add_argument('-o', '--output', help='Name of the output JSON file', default='snpDict.json')

    args = parser.parse_args()

    if not os.path.exists(args.filepath):
        print(f"Error: Could not find the input file at '{args.filepath}'")
    else:
        extracted_snps = parse_genome_file(args.filepath)

        if extracted_snps:
            export_to_json(extracted_snps, args.output)
        else:
            print("Error: No valid SNPs found. Ensure this is a valid 23andMe or AncestryDNA raw data file.")