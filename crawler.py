import urllib.request
import urllib.parse
import json
import re
import time

def get_json_keys(filepath):
    """Reads a JSON file and returns a list of its top-level keys."""
    try:
        with open(filepath, 'r') as file:
            # Load the JSON data into a Python variable
            data = json.load(file)
            
            # Ensure the loaded data is actually a dictionary (JSON object)
            if isinstance(data, dict):
                # Extract the keys and convert them into a standard list/array
                keys_array = list(data.keys())
                return keys_array
            else:
                print("Error: The top-level JSON structure is an array, not a dictionary.")
                return []
                
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: The file '{filepath}' does not contain valid JSON.")
        return []

# --- Example Usage ---
if __name__ == "__main__":
    filename = 'snpDict.json'
    
    # Get the keys
    snp_keys = get_json_keys(filename)
    
    # Print the results
    if snp_keys:
        print(f"Successfully extracted {len(snp_keys)} keys:")
        print(snp_keys)


def convert_jsonl_to_json(input_file, output_file):
    print("Reading JSON Lines file...")
    data = []
    
    # Read the line-by-line file
    with open(input_file, 'r') as f:
        for line in f:
            if line.strip(): # Skip empty lines
                data.append(json.loads(line))
                
    print("Converting to standard JSON array...")
    # Write it out as a standard formatted JSON array
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"Done! Saved standard JSON to {output_file}")

def get_genotype_data(snp_title):
    """Fetches all genotype sub-pages for a given SNP in a single API call using the bots URL."""
    prefix = urllib.parse.quote(f"{snp_title}(")
    # UPDATED: Using bots.snpedia.com
    url = f"https://bots.snpedia.com/api.php?action=query&generator=allpages&gapprefix={prefix}&prop=revisions&rvprop=content&rvslots=main&format=json"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Python native scraper)'})
    
    genotypes = []
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        pages = data.get('query', {}).get('pages', {})
        
        for page_id, page_info in pages.items():
            title = page_info.get('title', '')
            
            # Extract the allele pair from the title (e.g., "Rs53576(A;A)" -> "(A;A)")
            allele_match = re.search(r'(\([A-Z,-]+;[A-Z,-]+\))', title, re.IGNORECASE)
            alleles = allele_match.group(1) if allele_match else title
            
            # Extract the wikitext content
            if 'revisions' in page_info:
                content = page_info['revisions'][0]['slots']['main']['*']
                
                # Grab the Summary and Magnitude from the Genotype template
                summary = re.search(r'\|\s*Summary\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
                magnitude = re.search(r'\|\s*Magnitude\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
                
                genotypes.append({
                    "Alleles": alleles,
                    "Magnitude": magnitude.group(1).strip() if magnitude else "",
                    "Summary": summary.group(1).strip() if summary else ""
                })
                
    except Exception as e:
        print(f"  -> Error fetching genotypes for {snp_title}: {e}")
        
    return genotypes

def get_snp_data(snp_name):
    """Fetches the main SNP page and its genotype sub-pages using the bots URL."""
    safe_title = urllib.parse.quote(snp_name)
    # UPDATED: Using bots.snpedia.com
    url = f"https://bots.snpedia.com/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&titles={safe_title}&redirects=1&format=json"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Python native scraper)'})
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        pages = data.get('query', {}).get('pages', {})
        
        for page_id, page_info in pages.items():
            if page_id == '-1' or 'missing' in page_info:
                print(f"  -> {snp_name} not found in SNPedia. Skipping.")
                return None
                
            content = page_info['revisions'][0]['slots']['main']['*']
            actual_title = page_info.get('title', snp_name)
            
            # Regex for main page variables
            top_summary = re.search(r'\|\s*Summary\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
            chromosome = re.search(r'\|\s*Chromosome\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
            gene = re.search(r'\|\s*Gene\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
            orientation = re.search(r'\|\s*Orientation\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
            
            # Fetch the nested genotype sub-pages
            genotypes_list = get_genotype_data(actual_title)
            
            return {
                "SNP": actual_title,
                "Top_Summary": top_summary.group(1).strip() if top_summary else "",
                "Orientation": orientation.group(1).strip() if orientation else "",
                "Gene": gene.group(1).strip() if gene else "",
                "Chromosome": chromosome.group(1).strip() if chromosome else "",
                "Genotypes": genotypes_list
            }
    except Exception as e:
        print(f"Error fetching {snp_name}: {e}")
        
    return None

if __name__ == "__main__":
    # Your array of SNPs to investigate

    filename = 'snpDict.json'
    
    # Get the keys
    target_snps = get_json_keys(filename)

    output_filename = 'detailed_snps.json'
    
    results = []
    
    print(f"Investigating {len(target_snps)} SNPs...\n")
    
    with open(output_filename, 'a') as f:
        for index, snp in enumerate(target_snps):
            print(f"[{index + 1}/{len(target_snps)}] Checking {snp}...")
            
            data = get_snp_data(snp)
            
            if data:
                # Instantly write the single SNP to the file and add a newline
                f.write(json.dumps(data) + '\n')
                # Force the computer to actually write to the hard drive immediately
                f.flush() 
                
            time.sleep(1) 
            
    print(f"\nFinished! Data successfully saved to {output_filename}")
        
    print(f"\nData successfully saved to {output_filename}")

    input_filename = 'detailed_snps.json' 
    output_filename = 'final_snps_array.json'
    
    convert_jsonl_to_json(input_filename, output_filename)
