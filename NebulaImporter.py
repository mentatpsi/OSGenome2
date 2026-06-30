import argparse
import gzip
import json
import os
import re
import time

# Matches an alleles-are-single-nucleotide SNV; SNPedia genotype pages are
# overwhelmingly SNV-based, so we only emit SNVs and skip indels (their REF/ALT
# sequences don't map onto SNPedia's genotype notation reliably).
_NUCS = set("ACGT")


def vcf_genotype(ref: str, alt_field: str, gt_field: str):
    """
    Converts a VCF record's REF/ALT plus a sample GT into a '(A;B)' genotype.

    VCF alleles are reported on the forward strand of the reference. The array
    importers (23andMe/AncestryDNA) emit raw vendor alleles, which those vendors
    also report on the forward strand, so the two sources line up and app.py's
    orientation-flipping handles the SNPedia comparison from there.

    Returns the genotype string, or None to skip (no-call, indel, or malformed).
    """
    alleles = [ref.upper()] + [a.upper() for a in alt_field.split(',')]
    gt = gt_field.split(':')[0]
    indices = re.split(r'[/|]', gt)

    if not gt or '.' in indices:
        return None  # no-call

    try:
        called = [alleles[int(i)] for i in indices]
    except (ValueError, IndexError):
        return None

    if len(called) == 1:          # haploid call (chrX/Y/MT) -> homozygous
        called = [called[0], called[0]]
    if len(called) != 2:
        return None

    if not all(len(a) == 1 and a in _NUCS for a in called):
        return None               # indel / symbolic allele -> skip

    return f"({called[0]};{called[1]})"


def first_rsid(id_field: str):
    """Returns the first dbSNP rsID in a VCF ID field, or None."""
    for token in id_field.split(';'):
        token = token.strip().lower()
        if token.startswith('rs'):
            return token
    return None


def parse_vcf(filepath: str) -> dict:
    """
    Reads a (optionally bgzipped) single-sample VCF and returns {rsid: '(A;B)'}
    for every SNV the sample carries. Only the first sample column is used.
    """
    snp_dict = {}
    stats = {'records': 0, 'emitted': 0, 'no_rsid': 0, 'skipped_indel_or_nocall': 0}

    opener = gzip.open if filepath.endswith('.gz') else open
    print(f"Reading VCF: {filepath}...")
    start = time.time()

    with opener(filepath, 'rt') as f:
        for line in f:
            if line.startswith('#'):
                continue

            cols = line.rstrip('\n').split('\t')
            if len(cols) < 10:
                continue

            stats['records'] += 1
            rsid = first_rsid(cols[2])
            if rsid is None:
                stats['no_rsid'] += 1
                continue

            genotype = vcf_genotype(cols[3], cols[4], cols[9])
            if genotype is None:
                stats['skipped_indel_or_nocall'] += 1
                continue

            # Assumes one row per rsID; a multiallelic site split across rows
            # sharing an rsID would keep only the last row's genotype.
            snp_dict[rsid] = genotype
            stats['emitted'] += 1

            if stats['records'] % 1_000_000 == 0:
                print(f"  ...{stats['records']:,} records, {stats['emitted']:,} SNVs kept", flush=True)

    elapsed = round(time.time() - start, 1)
    print(f"Parsed {stats['records']:,} variant records in {elapsed}s.")
    print(f"  SNVs with an rsID kept : {stats['emitted']:,}")
    print(f"  skipped (indel/no-call): {stats['skipped_indel_or_nocall']:,}")
    print(f"  skipped (no rsID)      : {stats['no_rsid']:,}")
    return snp_dict


def export_to_json(data: dict, output_filepath: str):
    try:
        with open(output_filepath, "w") as jsonfile:
            json.dump(data, jsonfile, indent=4)
        print(f"Success! Wrote {len(data):,} SNPs to: {output_filepath}")
    except IOError as e:
        print(f"Error saving file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a Nebula Genomics (or any single-sample) VCF into a "
                    "snpDict.json for OSGenome2.",
        epilog="Note: a variant-only VCF lists only sites where you differ from "
               "the reference, so homozygous-reference SNPs are absent. Use "
               "--backfill with an array-derived snpDict.json to fill those in "
               "(the VCF call always wins where both have a site)."
    )
    parser.add_argument('-f', '--filepath', required=True,
                        help='Path to the VCF (.vcf or .vcf.gz).')
    parser.add_argument('-o', '--output', default='snpDict.json',
                        help='Output JSON file (default: snpDict.json).')
    parser.add_argument('--backfill', default=None,
                        help='An existing snpDict.json (e.g. from AncestryDNA via '
                             'GenomeImporter.py) used to fill in SNPs the VCF does '
                             'not report. VCF genotypes take precedence.')
    args = parser.parse_args()

    if not os.path.exists(args.filepath):
        print(f"Error: Could not find the input file at '{args.filepath}'")
        raise SystemExit(1)

    vcf_snps = parse_vcf(args.filepath)
    if not vcf_snps:
        print("Error: No usable SNVs found. Is this a single-sample VCF with rsIDs?")
        raise SystemExit(1)

    if args.backfill:
        if not os.path.exists(args.backfill):
            print(f"Error: --backfill file '{args.backfill}' not found.")
            raise SystemExit(1)
        with open(args.backfill) as bf:
            merged = json.load(bf)
        base = len(merged)
        added = sum(1 for k in vcf_snps if k not in merged)
        overridden = sum(1 for k in vcf_snps if k in merged and merged[k] != vcf_snps[k])
        merged.update(vcf_snps)  # VCF wins on overlap
        print(f"Backfill: started with {base:,} array SNPs; VCF added {added:,} new "
              f"and overrode {overridden:,} differing calls.")
        export_to_json(merged, args.output)
    else:
        export_to_json(vcf_snps, args.output)
