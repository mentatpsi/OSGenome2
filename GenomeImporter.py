import argparse
import os
import json
import time

def parse_23andme_file(filepath: str) -> dict:
    """
    Reads a raw 23andMe DNA text file line-by-line and extracts SNPs and Genotypes.
    Properly handles Indels (D/I) and single-allele calls on X/Y/mtDNA.
    """
    snp_dict = {}
    
    print(f"Reading 23andMe file: {filepath}...")
    start_time = time.time()
    
    with open(filepath, 'r') as file:
        for line in file:
            # Skip 23andMe's comment block at the top
            if not line.strip() or line.startswith('#'):
                continue
                
            columns = line.strip().split("\t")
            
            # 23andMe files have exactly 4 columns: rsid, chromosome, position, genotype
            if len(columns) < 4:
                continue
                
            rsid = columns[0].strip().lower()
            raw_genotype = columns[3].strip()
            
            # The bulletproof genotype parsing logic
            if len(raw_genotype) == 2 and raw_genotype != "--":
                formatted_genotype = f"({raw_genotype[0]};{raw_genotype[1]})"
            elif len(raw_genotype) == 1 and raw_genotype != '-':
                # Handle single-allele calls (often seen on Male X/Y or mtDNA in 23andMe)
                # This will turn 'A' into '(A;A)' and 'D' into '(D;D)'
                formatted_genotype = f"({raw_genotype[0]};{raw_genotype[0]})"
            else:
                # Handle actual no-calls ('--' or '-')
                formatted_genotype = "(-;-)"
                
            snp_dict[rsid] = formatted_genotype

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
    parser = argparse.ArgumentParser(description="Convert raw 23andMe text files into a JSON dictionary.")
    parser.add_argument('-f', '--filepath', help='Path to the 23andMe text file', required=True)
    parser.add_argument('-o', '--output', help='Name of the output JSON file', default='snpDict.json')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.filepath):
        print(f"Error: Could not find the input file at '{args.filepath}'")
    else:
        extracted_snps = parse_23andme_file(args.filepath)
        
        if extracted_snps:
            export_to_json(extracted_snps, args.output)
        else:
            print("Error: No valid SNPs found. Ensure this is a valid 23andMe raw data file.")