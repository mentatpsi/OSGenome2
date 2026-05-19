# OSGenome2

An Open Source Web Application for Genetic Data (SNPs) using 23AndMe and Data Crawling Technologies

## Example
![Example of App](https://github.com/mentatpsi/OSGenome2/blob/main/screenshots/OSGenome05-07.png)
![Example of App AI](https://github.com/mentatpsi/OSGenome2/blob/main/screenshots/OSGenome-AI.png)



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
├── snpedia_snps.json     # Cached list of all SNPedia rsIDs — included
├── crawl_progress.jsonl  # Crawler progress tracking — created on first crawl run
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
pip install flask requests
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

The crawler queries SNPedia for each rsID in your `snpDict.json` at one request per second (to be respectful to SNPedia's servers). A full 23andMe genome contains ~600,000 SNPs, though SNPedia only has meaningful data for a fraction of them. **Expect the crawl to run for several hours.** The app can be used at any point during the crawl — it reloads new results automatically as the file grows.

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

#### Resuming an Interrupted Crawl

The crawler tracks every attempted SNP in `crawl_progress.jsonl` — including failures and gateway errors — so re-running the command will always pick up exactly where it left off without re-scanning anything.

```bash
python crawler.py          # resumes automatically from crawl_progress.jsonl
```

#### Crawler Flags

| Flag | Description |
|------|-------------|
| `-s` / `--start <rsID\|index>` | Skip all SNPs before this point and mark them as `skipped` in the progress file. Accepts an rsID (e.g. `rs53576`) or a zero-based numeric index. |
| `--crawl-skipped` | Re-crawl SNPs previously marked as `skipped` via `--start`, while still skipping anything already successfully crawled or confirmed missing. |
| `--reset` | Clear the progress file entirely and start the crawl from scratch. |
| `--refresh-snplist` | Re-fetch the SNPedia SNP list even if a local cache (`snpedia_snps.json`) exists. |

#### SNPedia Pre-filter (`snpedia_snps.json`)

`snpedia_snps.json` is a cached list of every rsID that SNPedia has a page for, fetched from `Category:Is_a_snp`. **This file is included in the repository** — generating it from scratch takes ~30 minutes of paginated API calls, so the cached copy lets you start crawling immediately.

Before each crawl, your genome's SNPs are pre-filtered against this list so SNPs with no SNPedia page are never queried. A typical 23andMe genome has ~600,000 SNPs; SNPedia covers roughly 25,000 of them, so this eliminates the majority of wasted requests.

**To refresh the cache** (e.g. to pick up SNPs newly added to SNPedia):

```bash
python crawler.py --refresh-snplist
```

Or delete the file manually and re-run — the crawler will regenerate it automatically.

**Example workflow — start mid-list, then backfill:**

```bash
# Start crawling from rs53576 (skips everything before it)
python crawler.py --start rs53576

# Later: go back and fill in the entries that were skipped above
python crawler.py --crawl-skipped
```

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

### Progress Tracking (`crawl_progress.jsonl`)
The crawler maintains a JSONL progress file alongside `detailed_snps.json`. Each line records one attempted SNP:

```json
{"snp": "rs53576", "status": "success"}
{"snp": "rs1815739", "status": "not_found"}
{"snp": "rs6152", "status": "skipped"}
```

| Status | Meaning |
|--------|---------|
| `success` | SNPedia returned data; written to `detailed_snps.json` |
| `not_found` | SNP has no SNPedia page |
| `skipped` | Skipped via `--start`; can be re-crawled with `--crawl-skipped` |

Re-running the crawler always skips `success` and `not_found` entries. Only `skipped` entries can be selectively resumed.

## AI Analysis (Ollama)

OSGenome2 integrates with [Ollama](https://ollama.com) to provide local, private AI-powered explanations of your genetic data. No data leaves your machine.

### Setup

1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model (e.g. `llama3` is a good starting point):
   ```bash
   ollama pull llama3
   ```
3. Make sure Ollama is running before you start the app. The app detects it automatically on page load.

### Features

**Per-SNP Analysis** — Each row in the table has a <kbd>🤖</kbd> button on the right. Clicking it opens a modal that streams a plain-language explanation of:
- What the gene does in the body
- What your specific allele means
- Relevant lifestyle or health considerations
- Caveats about interpreting DTC genetic testing

**Genome Chat** — A floating chat button in the bottom-right corner opens a conversational interface. Your top 25 SNPs (by magnitude) are automatically included as context, so you can ask questions like:
- *"Which of my variants are most clinically significant?"*
- *"What does my APOE status mean?"*
- *"Are any of my variants related to cardiovascular risk?"*

Both features support multiple Ollama models. Use the model selector in each panel to switch between installed models.

> **Privacy note:** All AI processing runs locally through Ollama. Your genetic data is never sent to any external server.

> **Medical disclaimer:** AI-generated explanations are for educational purposes only. Always confirm significant findings with a licensed clinician.

---

## Dashboard Features

- **SNP Explorer**: Browse all matched SNPs with detailed genotype information
- **Category Filter**: Clickable color-coded pills to filter by disease area
- **AI Analysis**: Per-SNP explanations and genome-wide chat powered by local Ollama models
- **Filtering**: Hide "Common in ClinVar" variants and empty traits
- **Sorting**: Sort by magnitude (effect size) to identify high-impact variants
- **Search**: Quick search across genes, SNP IDs, and traits
- **Responsive Design**: Mobile-friendly Bootstrap interface

## Category Color Guide

Category badges are color-coded by disease area — both in the filter panel and in the table — so you can spot related variants at a glance.

| Color | Disease Area | Example Categories |
|-------|-------------|-------------------|
| 🔴 Red | Hereditary Cancer & Autoimmune | Hereditary Cancer, Lynch Syndrome, Breast/Ovarian Cancer, Rheumatoid Arthritis |
| 🟠 Orange | Cardiovascular | Cardiovascular Disease, Cardiomyopathy, Hypertrophic Cardiomyopathy, Familial Hypercholesterolemia, Aortic Aneurysm |
| 🟣 Purple | Neurological | Neurological Disease, Alzheimer's Disease, Parkinson's Disease, Epilepsy, Tuberous Sclerosis |
| 🟤 Dark Orange | Metabolic | Metabolic Disease, Phenylketonuria, Gaucher Disease, MCAD Deficiency, Hemochromatosis |
| 🟢 Teal | Drug Metabolism | Drug Metabolism, Pharmacogenomics, Warfarin Sensitivity, Alcohol Metabolism |
| 🔴 Dark Red | Blood Disorders | Blood Disorders, Thrombophilia, Sickle Cell Disease, Hemophilia |
| 🔵 Blue | Eye & Blood Type | Eye Disease, Retinitis Pigmentosa, Age-Related Macular Degeneration, Blood Type |
| 🔵 Cyan | Respiratory & Hearing | Respiratory Disease, Cystic Fibrosis, Hearing Loss |
| 🟢 Green | Connective Tissue & Kidney | Connective Tissue Disease, Marfan Syndrome, Ehlers-Danlos Syndrome, Kidney Disease |
| 🟤 Brown | Bone | Bone Disease, Hypophosphatasia |
| 🟠 Burnt Orange | Skin | Skin Disease, Epidermolysis Bullosa |
| 🟣 Deep Purple | Neuromuscular & Psychiatric | Neuromuscular Disease, Psychiatric Traits, Bipolar Disorder Risk, Dopamine Metabolism |
| 🟢 Olive | Nutrition & Physical Traits | Nutrition & Vitamins, Vitamin D, Physical Traits, Height |
| ⚫ Grey | Unclassified | Clinical Variant (SNPs not matched to a known disease category) |

## Notes

- The starter `detailed_snps.json` contains 3,975 SNPs with SNPedia magnitude ≥ 1 — all entries with a documented clinical effect
- The app reloads `detailed_snps.json` automatically as the crawler adds new data (at most once every 15 seconds)
- The crawler includes a 1-second delay between API requests to be respectful to SNPedia
- User alleles are automatically flipped when the SNP uses the minus strand orientation
- Magnitude values > 2.0 are highlighted as high-impact variants in the dashboard
- All data is processed locally — no personal genetic data is sent to external servers
- AI analysis requires Ollama running on `localhost:11434`; the app works normally without it (the chat button turns grey)
- Categories were generated by Claude (Anthropic) using a curated gene→disease mapping; always confirm significant findings with a clinician

## Disclaimer
Raw Data coming from Genetic tests done by Direct To Consumer companies such as 23andMe and Ancestry.com were found to have a false positive rate of 40% for genes with clinical significance in a March 2018 study [*False-positive results released by direct-to-consumer genetic tests highlight the importance of clinical confirmation testing for appropriate patient care*](https://www.nature.com/articles/gim201838). For this reason, it's important to confirm any at risk clinical SNPs with your doctor who can provide genetic tests and send them to a clinical laboratory.

## Acknowledgements

- **Dr. Sergey Kornilov** ([Biostochastics](https://github.com/biostochastics)) for brief audit of bioinformatics correctness

## License

GNU General Public License v3.0 - See [LICENSE](LICENSE) for details
