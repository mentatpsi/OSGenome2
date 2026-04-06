from flask import Flask, render_template
import json
import os

app = Flask(__name__)

def format_user_allele(allele_string, orientation):
    """
    Flips the user's allele if the SNPedia orientation is 'minus'.
    Also sorts the alleles alphabetically to match SNPedia's standard formatting.
    """
    # If it's not a standard (X;Y) format, return it as-is
    if not (allele_string.startswith('(') and allele_string.endswith(')')):
        return allele_string
        
    clean = allele_string.strip('()')
    # Split by semicolon and ensure uppercase
    alleles = [a.strip().upper() for a in clean.split(';')]
    
    if len(alleles) != 2:
        return allele_string

    # Flip the bases if the orientation is minus
    if orientation.strip().lower() == 'minus':
        complement_map = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C', '-': '-'}
        alleles = [complement_map.get(a, a) for a in alleles]
        
    # Alphabetize the alleles (e.g., T,C becomes C,T)
    alleles.sort()
    
    return f"({alleles[0]};{alleles[1]})"

def cross_reference_snps(db_filepath, user_filepath):
    """Cross-references the massive SNP database with the user's specific alleles."""
    
    if not os.path.exists(user_filepath):
        return []
        
    with open(user_filepath, 'r') as f:
        raw_user_data = json.load(f)
        user_data = {key.strip().lower(): value.strip() for key, value in raw_user_data.items()}

    results = []
    
    if not os.path.exists(db_filepath):
        return []

    with open(db_filepath, 'r') as f:
        for line in f:
            if not line.strip():
                continue
                
            snp_info = json.loads(line)
            snp_id_lower = snp_info.get("SNP", "").strip().lower()

            if snp_id_lower in user_data:
                raw_user_allele = user_data[snp_id_lower]
                orientation = snp_info.get("Orientation", "plus")
                
                # Format, sort, and potentially flip the allele based on orientation
                processed_user_allele = format_user_allele(raw_user_allele, orientation)
                
                specific_summary = snp_info.get("Top_Summary", "No general summary available.")
                magnitude = "0"
                
                # Check for the exact processed allele
                for geno in snp_info.get("Genotypes", []):
                    # We also strip and upper the database allele just to be safe
                    db_allele = geno.get("Alleles", "").strip().upper()
                    if db_allele == processed_user_allele.upper():
                        specific_summary = geno.get("Summary") or specific_summary
                        magnitude = geno.get("Magnitude", "0")
                        break 

                results.append({
                    "SNP": snp_info.get("SNP"),
                    "Gene": snp_info.get("Gene", "Unknown"),
                    "Chromosome": snp_info.get("Chromosome", "Unknown"),
                    "Original_Allele": raw_user_allele,
                    "Processed_Allele": processed_user_allele,
                    "Orientation": orientation,
                    "Magnitude": magnitude,
                    "Summary": specific_summary
                })

    # Sort results by magnitude (highest first)
    results.sort(key=lambda x: float(x['Magnitude']) if x['Magnitude'].replace('.','',1).isdigit() else 0, reverse=True)
    return results

@app.route('/')
def index():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_file = os.path.join(base_dir, 'detailed_snps.json') 
    user_file = os.path.join(base_dir, 'snpDict.json')

    report_data = cross_reference_snps(db_file, user_file)
    
    return render_template('index.html', report_data=report_data)

if __name__ == '__main__':
    app.run(debug=True)