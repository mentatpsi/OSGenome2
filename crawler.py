import urllib.request
import urllib.parse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED


class FetchError(Exception):
    """Raised when an HTTP/network fetch fails after all retries. Transient and
    retryable, as opposed to a genuine 'page does not exist' result."""


def _fetch_json(url, label, retries=5, delay=10):
    """GET a URL and return the parsed JSON, retrying transient failures.
    Raises FetchError if every attempt fails."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Python native scraper)'})
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                print(f"  -> {label} fetch failed ({e}), retrying in {delay}s... "
                      f"(attempt {attempt + 2}/{retries})")
                time.sleep(delay)
    raise FetchError(f"{label} fetch failed after {retries} attempts: {last_error}")


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


def get_genotype_data(snp_title):
    """Fetches all genotype sub-pages for a given SNP in a single API call using the bots URL."""
    prefix = urllib.parse.quote(f"{snp_title}(")
    url = f"https://bots.snpedia.com/api.php?action=query&generator=allpages&gapprefix={prefix}&prop=revisions&rvprop=content&rvslots=main&format=json"

    genotypes = []
    data = _fetch_json(url, f"genotypes for {snp_title}")
    pages = data.get('query', {}).get('pages', {})

    for page_info in pages.values():
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

    data = _fetch_json(url, snp_name)
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

    while True:
        base = "https://bots.snpedia.com/api.php?action=query&list=categorymembers&cmtitle=Category:Is_a_snp&cmlimit=500&format=json"
        url = base + (f"&cmcontinue={urllib.parse.quote(cmcontinue)}" if cmcontinue else "")

        data = _fetch_json(url, f"SNP list page {page + 1}")

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
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=3,
        help='Number of SNPs to fetch concurrently (default 3). Use 1 for the '
             'original sequential behaviour. Keep this modest to be respectful '
             'to SNPedia.'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Seconds each worker pauses after finishing a SNP (default 0.5). '
             'Throttles the request rate; lower is faster but less polite.'
    )
    args = parser.parse_args()

    if args.workers < 1:
        print("--workers must be at least 1. Exiting.")
        raise SystemExit(1)

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

    # 'error' entries are transient fetch failures — always retry them.
    # Build the skip set: exclude 'skipped' entries when --crawl-skipped is active.
    if args.crawl_skipped:
        already_scanned = {rsid for rsid, status in progress.items()
                           if status not in ('skipped', 'error')}
        skipped_count = sum(1 for s in progress.values() if s == 'skipped')
        if skipped_count:
            print(f"--crawl-skipped: will re-crawl {skipped_count:,} previously skipped SNPs.")
    else:
        already_scanned = {rsid for rsid, status in progress.items() if status != 'error'}

    error_count = sum(1 for s in progress.values() if s == 'error')
    if error_count:
        print(f"Found {error_count:,} SNPs that previously failed with a transient error — will retry them.")

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

    # Load SNPs already written to the output file. Anything already in the
    # output is, by definition, already fetched — skip it so we never re-download
    # data we hold (e.g. the shipped starter dataset has no progress entries).
    already_written = _load_written(output_filename)
    if already_written:
        new_from_output = already_written - already_scanned
        already_scanned |= already_written
        print(f"Found {len(already_written):,} SNPs already in output file "
              f"({len(new_from_output):,} not in progress log — skipping those too).")

    total = len(target_snps)
    remaining_count = sum(1 for s in target_snps if s.lower() not in already_scanned)
    print(f"Scanning {remaining_count:,} SNPs (of {total:,} total)...\n")

    # The remaining work, in order. Each worker thread only does network I/O;
    # all file writes happen on the main thread below, so no locking is needed.
    remaining = [s for s in target_snps if s.lower() not in already_scanned]

    def fetch_one(snp):
        """Runs in a worker thread. Never raises — returns (snp, status, data)."""
        try:
            data = get_snp_data(snp)
            status = 'success' if data else 'not_found'
        except FetchError as e:
            print(f"  -> {e}")
            data, status = None, 'error'
        if args.delay > 0:
            time.sleep(args.delay)
        return snp, status, data

    # Abort the run if the server keeps failing — entries are marked 'error'
    # (retryable), so a later run resumes them once the server recovers.
    max_consecutive_errors = 10
    consecutive_errors = 0
    completed = 0
    stop = False

    with open(output_filename, 'a') as out_f, open(progress_file, 'a') as prog_f, \
            ThreadPoolExecutor(max_workers=args.workers) as executor:
        work = iter(remaining)

        def submit_next():
            snp = next(work, None)
            return executor.submit(fetch_one, snp) if snp is not None else None

        # Prime the pool with up to `workers` in-flight fetches.
        inflight = set()
        for _ in range(args.workers):
            fut = submit_next()
            if fut is None:
                break
            inflight.add(fut)

        while inflight:
            done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                snp, status, data = fut.result()
                completed += 1

                prog_f.write(json.dumps({'snp': snp.lower(), 'status': status}) + '\n')
                prog_f.flush()
                already_scanned.add(snp.lower())

                if data and snp.lower() not in already_written:
                    out_f.write(json.dumps(data) + '\n')
                    out_f.flush()
                    already_written.add(snp.lower())

                print(f"[{completed}/{len(remaining)}] {snp} -> {status}")

                if status == 'error':
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors and not stop:
                        stop = True
                        print(f"\nAborting: {consecutive_errors} consecutive fetch "
                              f"failures — SNPedia looks down. Progress is saved; "
                              f"re-run later to resume.")
                else:
                    consecutive_errors = 0

                # Keep the pool topped up until we stop or run out of work.
                if not stop:
                    fut = submit_next()
                    if fut is not None:
                        inflight.add(fut)

    print(f"\nFinished! Data saved to {output_filename}")
