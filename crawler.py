import urllib.request
import urllib.parse
import json
import os
import re
import time


def get_json_keys(filepath):
    """Reads a JSON file and returns a list of its top-level keys."""
    try:
        with open(filepath, 'r') as file:
            data = json.load(file)
            if isinstance(data, dict):
                return list(data.keys())
            else:
                print("Error: The top-level JSON structure is an array, not a dictionary.")
                return []
    except FileNotFoundError:
        print(f"Error: The file '{filepath}' was not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: The file '{filepath}' does not contain valid JSON.")
        return []


def convert_jsonl_to_json(input_file, output_file):
    print("Reading JSON Lines file...")
    data = []
    with open(input_file, 'r') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    print("Converting to standard JSON array...")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Done! Saved standard JSON to {output_file}")


def get_genotype_data(snp_title):
    """Fetches all genotype sub-pages for a given SNP in a single API call using the bots URL."""
    prefix = urllib.parse.quote(f"{snp_title}(")
    url = f"https://bots.snpedia.com/api.php?action=query&generator=allpages&gapprefix={prefix}&prop=revisions&rvprop=content&rvslots=main&format=json"

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Python native scraper)'})

    genotypes = []
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
            break
        except Exception as e:
            if attempt < 4:
                print(f"  -> Genotype fetch failed for {snp_title} ({e}), retrying in 10s...")
                time.sleep(10)
            else:
                print(f"  -> Giving up on genotypes for {snp_title} after 5 attempts: {e}")
                return genotypes

    pages = data.get('query', {}).get('pages', {})

    for page_id, page_info in pages.items():
        title = page_info.get('title', '')

        allele_match = re.search(r'(\([A-Z,-]+;[A-Z,-]+\))', title, re.IGNORECASE)
        alleles = allele_match.group(1) if allele_match else title

        if 'revisions' in page_info:
            content = page_info['revisions'][0]['slots']['main']['*']

            summary = re.search(r'\|\s*Summary\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
            magnitude = re.search(r'\|\s*Magnitude\s*=\s*([^|\n}]+)', content, re.IGNORECASE)

            genotypes.append({
                "Alleles": alleles,
                "Magnitude": magnitude.group(1).strip() if magnitude else "",
                "Summary": summary.group(1).strip() if summary else ""
            })

    return genotypes


def get_snp_data(snp_name):
    """Fetches the main SNP page and its genotype sub-pages using the bots URL."""
    safe_title = urllib.parse.quote(snp_name)
    url = f"https://bots.snpedia.com/api.php?action=query&prop=revisions&rvprop=content&rvslots=main&titles={safe_title}&redirects=1&format=json"

    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Python native scraper)'})

    data = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
            break
        except Exception as e:
            if attempt < 4:
                print(f"  -> Fetch failed for {snp_name} ({e}), retrying in 10s...")
                time.sleep(10)
            else:
                print(f"  -> Giving up on {snp_name} after 5 attempts: {e}")
                return None

    pages = data.get('query', {}).get('pages', {})

    for page_id, page_info in pages.items():
        if page_id == '-1' or 'missing' in page_info:
            print(f"  -> {snp_name} not found in SNPedia. Skipping.")
            return None

        content = page_info['revisions'][0]['slots']['main']['*']
        actual_title = page_info.get('title', snp_name)

        top_summary = re.search(r'\|\s*Summary\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
        chromosome = re.search(r'\|\s*Chromosome\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
        gene = re.search(r'\|\s*Gene\s*=\s*([^|\n}]+)', content, re.IGNORECASE)
        orientation = re.search(r'\|\s*Orientation\s*=\s*([^|\n}]+)', content, re.IGNORECASE)

        genotypes_list = get_genotype_data(actual_title)

        return {
            "SNP": actual_title,
            "Top_Summary": top_summary.group(1).strip() if top_summary else "",
            "Orientation": orientation.group(1).strip() if orientation else "",
            "Gene": gene.group(1).strip() if gene else "",
            "Chromosome": chromosome.group(1).strip() if chromosome else "",
            "Genotypes": genotypes_list
        }

    return None


def fetch_snpedia_snp_list(cache_file='snpedia_snps.json'):
    """
    Returns a set of lowercase rsIDs that SNPedia has pages for, using
    the Category:Is_a_snp member list. Result is cached to disk so
    subsequent runs skip the fetch. Delete the cache file to force a refresh.
    """
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            snps = set(json.load(f))
        print(f"Loaded {len(snps):,} SNPedia SNPs from cache ({cache_file}).")
        return snps

    print("Fetching SNPedia SNP list (Category:Is_a_snp) — this runs once and is cached...")
    snps = set()
    cmcontinue = None
    page = 0

    max_retries = 5
    retry_delay = 10  # seconds

    while True:
        base = "https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json"
        url = base + (f"&cmcontinue={urllib.parse.quote(cmcontinue)}" if cmcontinue else "")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Python native scraper)'})

        data = None
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode('utf-8'))
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"\n  Page {page + 1} failed ({e}), retrying in {retry_delay}s... "
                          f"(attempt {attempt + 2}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    print(f"\nFailed after {max_retries} attempts on page {page + 1}: {e}")
                    raise

        for item in data.get('query', {}).get('categorymembers', []):
            snps.add(item['title'].lower())

        page += 1
        print(f"  Page {page} — {len(snps):,} SNPs collected...", end='\r')

        cmcontinue = data.get('continue', {}).get('cmcontinue')
        if not cmcontinue:
            break

        time.sleep(0.5)

    print(f"\nFetched {len(snps):,} SNPs from SNPedia.")

    with open(cache_file, 'w') as f:
        json.dump(sorted(snps), f)
    print(f"Cached to {cache_file}.")

    return snps


def _load_progress(progress_file):
    """Returns a dict of {lowercase rsID: status} using the last entry per rsid."""
    progress = {}
    try:
        with open(progress_file) as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        rsid = entry.get('snp', '').lower()
                        if rsid:
                            progress[rsid] = entry.get('status', '')
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return progress


def _load_written(output_file):
    """Returns a set of lowercase rsIDs already present in the output file."""
    written = set()
    try:
        with open(output_file) as f:
            for line in f:
                if line.strip():
                    try:
                        rsid = json.loads(line).get('SNP', '').lower()
                        if rsid:
                            written.add(rsid)
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass
    return written


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Crawl SNPedia for SNP data.')
    parser.add_argument(
        '-s', '--start',
        default=None,
        help='Skip all SNPs before this point and mark them as scanned. '
             'Accepts an rsID (e.g. rs53576) or a numeric index (e.g. 10000). '
             'Has no effect if those SNPs are already in the progress file.'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Clear the progress file and start the crawl from scratch.'
    )
    parser.add_argument(
        '--crawl-skipped',
        action='store_true',
        dest='crawl_skipped',
        help='Re-crawl SNPs previously marked as skipped via --start, '
             'while still skipping already-crawled (success/not_found) entries.'
    )
    parser.add_argument(
        '--refresh-snplist',
        action='store_true',
        dest='refresh_snplist',
        help='Re-fetch the SNPedia SNP list even if a local cache exists.'
    )
    args = parser.parse_args()

    filename        = 'snpDict.json'
    output_filename = 'detailed_snps.json'
    progress_file   = 'crawl_progress.jsonl'
    snplist_cache   = 'snpedia_snps.json'

    target_snps = get_json_keys(filename)
    if not target_snps:
        print("No SNPs found. Exiting.")
        raise SystemExit(1)

    if args.refresh_snplist and os.path.exists(snplist_cache):
        os.remove(snplist_cache)

    snpedia_snps = fetch_snpedia_snp_list(snplist_cache)
    before = len(target_snps)
    target_snps = [s for s in target_snps if s.lower() in snpedia_snps]
    print(f"Pre-filtered to {len(target_snps):,} SNPs (of {before:,}) that exist in SNPedia.\n")

    if args.reset:
        if os.path.exists(progress_file):
            os.remove(progress_file)
            print("Progress file cleared. Starting from scratch.")

    # Load every SNP that was ever attempted (success, not_found, skipped)
    progress = _load_progress(progress_file)

    # Build the skip set: exclude 'skipped' entries when --crawl-skipped is active
    if args.crawl_skipped:
        already_scanned = {rsid for rsid, status in progress.items() if status != 'skipped'}
        skipped_count = sum(1 for s in progress.values() if s == 'skipped')
        if skipped_count:
            print(f"--crawl-skipped: will re-crawl {skipped_count:,} previously skipped SNPs.")
    else:
        already_scanned = set(progress.keys())

    if already_scanned:
        print(f"Found {len(already_scanned):,} already-scanned SNPs in progress file — will skip them.")

    # --start: pre-populate the progress file with all SNPs before the start point
    if args.start is not None:
        if args.start.lstrip('-').isdigit():
            start_index = int(args.start)
            if start_index < 0 or start_index >= len(target_snps):
                print(f"Index {start_index} is out of range (0–{len(target_snps) - 1}). Exiting.")
                raise SystemExit(1)
        else:
            needle = args.start.lower()
            start_index = next((i for i, s in enumerate(target_snps) if s.lower() == needle), None)
            if start_index is None:
                print(f"SNP '{args.start}' not found in {filename}. Exiting.")
                raise SystemExit(1)

        to_skip = [s for s in target_snps[:start_index] if s.lower() not in already_scanned]
        if to_skip:
            print(f"Marking {len(to_skip):,} SNPs before index {start_index} as skipped...")
            with open(progress_file, 'a') as pf:
                for s in to_skip:
                    pf.write(json.dumps({'snp': s.lower(), 'status': 'skipped'}) + '\n')
                    already_scanned.add(s.lower())
        print(f"Starting from '{target_snps[start_index]}' (index {start_index}).")

    # Load SNPs already written to the output file (guards against duplicate entries)
    already_written = _load_written(output_filename)
    if already_written:
        print(f"Found {len(already_written):,} SNPs already in output file.")

    total = len(target_snps)
    remaining_count = sum(1 for s in target_snps if s.lower() not in already_scanned)
    print(f"Scanning {remaining_count:,} SNPs (of {total:,} total)...\n")

    with open(output_filename, 'a') as out_f, open(progress_file, 'a') as prog_f:
        for idx, snp in enumerate(target_snps, 1):
            if snp.lower() in already_scanned:
                continue

            print(f"[{idx}/{total}] Checking {snp}...")

            data = get_snp_data(snp)

            # Record every attempt in the progress file, regardless of outcome
            status = 'success' if data else 'not_found'
            prog_f.write(json.dumps({'snp': snp.lower(), 'status': status}) + '\n')
            prog_f.flush()
            already_scanned.add(snp.lower())

            if data and snp.lower() not in already_written:
                out_f.write(json.dumps(data) + '\n')
                out_f.flush()
                already_written.add(snp.lower())

            time.sleep(1)

    print(f"\nFinished! Data saved to {output_filename}")
