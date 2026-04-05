# OSGenome2

An Open Source Web Application for Genetic Data (SNPs) using 23AndMe and Data Crawling Technologies

## Overview

OSGenome2 is a Flask-based web application that cross-references your personal SNP data with a comprehensive SNPedia database to provide personalized genomic insights and trait analysis.

## Project Structure

```
OSGenome2/
├── app.py                 # Flask application & SNP cross-referencing logic
├── crawler.py             # SNPedia web crawler
├── GenomeImporter.py      # 23AndMe Genome Importer
├── snpDict.json          # Your 23AndMe SNP data (Genome Importer Generated)
├── detailed_snps.json    # Crawler output (JSONL format)
├── final_snps_array.json # Converted JSON array format
├── templates/
│   └── index.html        # Dashboard UI
├── README.md
└── LICENSE
```

## Setup & Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Install Dependencies

```bash
pip install flask
```

## How to Use the Crawler

### Step 1: Import Your 23AndMe Raw Data

Use `GenomeImporter.py` to convert your raw 23AndMe DNA text file into the required SNP dictionary format.

```bash
python GenomeImporter.py -f <path_to_23andme_file.txt> -o snpDict.json
```

**What happens:**
1. Reads your raw 23AndMe text file line-by-line
2. Extracts SNP IDs (rsids) and genotypes
3. Formats genotypes to SNPedia standard: `(A;G)` syntax
4. Exports the processed data to `snpDict.json`

**Expected output format:**
```json
{
  "rs53576": "(A;G)",
  "rs1815739": "(C;T)",
  "rs6152": "(A;G)"
}
```

### Step 2: Run the Crawler

The crawler fetches detailed SNP information from SNPedia for each SNP in your `snpDict.json` file.

```bash
python crawler.py
```

**What happens:**
1. Reads all SNP IDs from `snpDict.json`
2. For each SNP, queries the SNPedia API (`bots.snpedia.com`)
3. Extracts SNP metadata: gene, chromosome, orientation, summary
4. Retrieves all genotype-specific data (magnitude & traits)
5. Writes results line-by-line to `detailed_snps.json` (JSONL format)
6. Converts JSONL to standard JSON array format in `final_snps_array.json`

**Output files:**
- `detailed_snps.json` - Raw JSONL data (one JSON object per line)
- `final_snps_array.json` - Formatted JSON array (optional, for manual inspection)

### Step 3: Run the Web Application

At any time during the crawl, start the Flask app:

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Crawler Functions Reference

### `get_json_keys(filepath)`
Extracts all SNP IDs (top-level keys) from your `snpDict.json` file.

### `get_snp_data(snp_name)`
Fetches main SNP page data from SNPedia including:
- Summary
- Chromosome location
- Gene name
- Strand orientation (+ or -)

### `get_genotype_data(snp_title)`
Retrieves all genotype variations for a specific SNP with their:
- Allele pairs (e.g., A;A, A;G, G;G)
- Magnitude (effect size)
- Associated traits/summaries

### `convert_jsonl_to_json(input_file, output_file)`
Converts line-delimited JSON to a standard JSON array format.

## Dashboard Features

- **SNP Explorer**: Browse all matched SNPs with detailed genotype information
- **Filtering**: Hide "Common in ClinVar" variants and empty traits
- **Sorting**: Sort by magnitude (effect size) to identify high-impact variants
- **Search**: Quick search across genes, SNP IDs, and traits
- **Responsive Design**: Mobile-friendly Bootstrap interface

## Notes

- The crawler includes a 1-second delay between API requests to be respectful to SNPedia
- User alleles are automatically flipped if the SNP uses the minus strand orientation
- Magnitude values > 2.0 are highlighted as high-impact variants
- All data is processed locally; no personal data is sent to external servers.

## License

GNU General Public License v3.0 - See [LICENSE](LICENSE) for details