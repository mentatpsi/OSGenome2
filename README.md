# OSGenome2

An Open Source Web Application for Genetic Data (SNPs) using 23AndMe and Data Crawling Technologies

## Example
![Example of App](https://github.com/mentatpsi/OSGenome2/blob/main/screenshots/OSGenome05-07.png)


## Overview

OSGenome2 is a Flask-based web application that cross-references your personal SNP data with a comprehensive SNPedia database to provide personalized genomic insights and trait analysis.

## What are SNPs?
From Bioinformatics - A Practical Approach by Shui Qing Ye, M.D., Ph.D. (pg 108):

>SNP, pronounced “snip,” stands for single-nucleotide polymorphism, which represents a substitution of one base for another, e.g., C to T or A to G. SNP is the most common variation in the human genome and occurs approximately once every 100 to 300 bases. SNP is terminologically distinguished from mutation based on an arbitrary population frequency cutoff value: 1%, with SNP [greater than] 1% and mutation [less than] 1%. A key aspect of research in genetics is associating sequence variations with heritable phenotypes. Because SNPs are expected to facilitate large-scale association genetics studies, there has been an increasing interest in SNP discovery and detection.

23andMe gathers hundreds of thousands of SNPs that give you everything from your genetic ancestry (haplogroups) to whether you are more likely to think Cilantro tastes like soap, or how quickly you likely digest coffee. Unfortunately, and fortunately, there is a lot of information out there on each specific SNP and what associations they might have. Much like Phrenology of the late 18th and early 19th century, where personality was attempted to be associated to facial features, there can be a lot of attempts to draw conclusions in noise. Enter OS Genome v2, where you can discover links and research at your own pace with the information you gather. It will link what specific Genotype is yours, and what that means in the context of discovery. From there you can google the relevant SNP id at your own intrigue or use the link on the RSId to discover more about that SNP on SNPedia.


## Project Structure

```
OSGenome2/
├── app.py                 # Flask application & SNP cross-referencing logic
├── crawler.py             # SNPedia web crawler
├── GenomeImporter.py      # 23AndMe Genome Importer
├── snpDict.json          # Your 23AndMe SNP data (Genome Importer Generated)
├── category_snps.jsonl   # Claude-curated category tags (JSONL format)
├── detailed_snps.json    # SNPedia data — starter dataset included (see below)
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

## SNP Database Options

`detailed_snps.json` ships with a **curated starter dataset** of **3,975 SNPs** sourced from SNPedia. You can use it immediately without running the crawler, or replace it with a full personalized crawl.

### Option A — Use the Starter Dataset (default, no setup required)

The included dataset contains every SNP where at least one genotype has a **SNPedia magnitude ≥ 1**. SNPedia's magnitude scale is roughly:

| Magnitude | Meaning |
|-----------|---------|
| 0 | No known significance / benign |
| 1 | Interesting, worth knowing |
| 2 | Moderate clinical relevance |
| 3+ | High significance (e.g. hereditary cancer, cardiomyopathy) |

Filtering at ≥ 1 removes ~21,500 low-signal entries (variants with no documented effect) while keeping every SNP with a meaningful annotation. This covers the vast majority of clinically relevant results for most users.

**Just import your genome (Step 1 below) and run the app — the starter data is already there.**

### Option B — Full Personalized Crawl

For complete coverage of every SNP in your specific genome:

1. Delete `detailed_snps.json`
2. Run `python crawler.py`

The crawler queries SNPedia for each rsID in your `snpDict.json` at one request per second (to be respectful to SNPedia's servers). A full 23andMe genome contains ~600,000 SNPs, though SNPedia only has meaningful data for a fraction of them. **Expect the crawl to run for several hours.** The app can be used at any point during the crawl, it reloads new results automatically as the file grows.

---

## How to Use

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

### Step 2 (Optional): Run the Crawler for Full Coverage

> Skip this step if you want to use the included starter dataset.

Delete `detailed_snps.json` first, then run:

```bash
python crawler.py
```

**What happens:**
1. Reads all SNP IDs from `snpDict.json`
2. For each SNP, queries the SNPedia API (`bots.snpedia.com`)
3. Extracts SNP metadata: gene, chromosome, orientation, summary
4. Retrieves all genotype-specific data (magnitude & traits)
5. Writes results line-by-line to `detailed_snps.json` (JSONL format)

### Step 3: Run the Web Application

Start the Flask app (can be run at any point — with or without running the crawler):

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

- The starter `detailed_snps.json` contains 3,975 SNPs with SNPedia magnitude ≥ 1 — all entries with a documented clinical effect
- The app reloads `detailed_snps.json` automatically as the crawler adds new data (at most once every 15 seconds)
- The crawler includes a 1-second delay between API requests to be respectful to SNPedia
- User alleles are automatically flipped when the SNP uses the minus strand orientation
- Magnitude values > 2.0 are highlighted as high-impact variants in the dashboard
- All data is processed locally — no personal genetic data is sent to external servers
- Categories were generated by Claude (Anthropic) using a curated gene→disease mapping; always confirm significant findings with a clinician

## Disclaimer
Raw Data coming from Genetic tests done by Direct To Consumer companies such as 23andMe and Ancestry.com were found to have a false positive rate of 40% for genes with clinical significance in a March 2018 study [*False-positive results released by direct-to-consumer genetic tests highlight the importance of clinical confirmation testing for appropriate patient care*](https://www.nature.com/articles/gim201838). For this reason, it's important to confirm any at risk clinical SNPs with your doctor who can provide genetic tests and send them to a clinical laboratory.

## Acknowledgements

- **Dr. Sergey Kornilov** ([Biostochastics](https://github.com/biostochastics)) for brief audit of bioinformatics correctness

## License

GNU General Public License v3.0 - See [LICENSE](LICENSE) for details
