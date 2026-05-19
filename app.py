from flask import Flask, render_template, jsonify, request, Response, stream_with_context
import json
import os
import threading
import time

try:
    import requests as _req
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_DB_FILE  = os.path.join(BASE_DIR, 'detailed_snps.json')
_CAT_FILE = os.path.join(BASE_DIR, 'category_snps.jsonl')

OLLAMA_BASE = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')


def format_user_allele(allele_string, orientation):
    """
    Flips the user's allele if the SNPedia orientation is 'minus'.
    Also sorts the alleles alphabetically to match SNPedia's standard formatting.
    """
    if not (allele_string.startswith('(') and allele_string.endswith(')')):
        return allele_string

    clean = allele_string.strip('()')
    alleles = [a.strip().upper() for a in clean.split(';')]

    if len(alleles) != 2:
        return allele_string

    if orientation.strip().lower() == 'minus':
        complement_map = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C', '-': '-'}
        alleles = [complement_map.get(a, a) for a in alleles]

    alleles.sort()
    return f"({alleles[0]};{alleles[1]})"


def _load_snp_db():
    """Builds a dict keyed by lowercase SNP ID from detailed_snps.json."""
    index = {}
    if not os.path.exists(_DB_FILE):
        return index
    with open(_DB_FILE, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            snp_info = json.loads(line)
            key = snp_info.get("SNP", "").strip().lower()
            if key:
                index[key] = snp_info
    print(f"Loaded {len(index):,} SNPs into database index.")
    return index


def _load_category_lookup():
    """Builds a dict keyed by lowercase rsid from category_snps.jsonl."""
    lookup = {}
    if not os.path.exists(_CAT_FILE):
        return lookup
    with open(_CAT_FILE, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            cat_data = json.loads(line)
            rsid = cat_data.get("rsid", "").strip().lower()
            lookup[rsid] = cat_data.get("categories", [])
    return lookup


# How long to wait between reloads while a file is actively being written to.
# The crawler appends ~1 SNP/second, so this prevents a full re-index on every request.
RELOAD_COOLDOWN = 15  # seconds

# Cache with mtime tracking — reloads automatically when files change on disk
SNP_DB: dict = {}
CATEGORY_LOOKUP: dict = {}
_db_mtime: float | None = None
_cat_mtime: float | None = None
_last_reload: float = 0.0
_cache_lock = threading.Lock()


def _mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _refresh_cache():
    """Reload whichever files changed, but at most once per RELOAD_COOLDOWN seconds."""
    global SNP_DB, CATEGORY_LOOKUP, _db_mtime, _cat_mtime, _last_reload

    current_db_mtime  = _mtime(_DB_FILE)
    current_cat_mtime = _mtime(_CAT_FILE)

    # Fast path: nothing changed at all
    if current_db_mtime == _db_mtime and current_cat_mtime == _cat_mtime:
        return

    # Something changed — but only act if the cooldown has elapsed
    if time.monotonic() - _last_reload < RELOAD_COOLDOWN:
        return

    with _cache_lock:
        # Re-check inside the lock so two simultaneous requests don't both reload
        if time.monotonic() - _last_reload < RELOAD_COOLDOWN:
            return

        if current_db_mtime != _db_mtime:
            SNP_DB = _load_snp_db()
            _db_mtime = current_db_mtime

        if current_cat_mtime != _cat_mtime:
            CATEGORY_LOOKUP = _load_category_lookup()
            _cat_mtime = current_cat_mtime

        _last_reload = time.monotonic()


# Initial load
_refresh_cache()


def cross_reference_snps(user_filepath):
    """Cross-references the SNP database index with the user's specific alleles."""
    if not os.path.exists(user_filepath) or not SNP_DB:
        return []

    with open(user_filepath, 'r') as f:
        raw_user_data = json.load(f)
    user_data = {key.strip().lower(): value.strip() for key, value in raw_user_data.items()}

    results = []

    # Iterate the (smaller) database index and look up against user dict in O(1)
    for snp_id_lower, snp_info in SNP_DB.items():
        if snp_id_lower not in user_data:
            continue

        raw_user_allele = user_data[snp_id_lower]
        orientation = snp_info.get("Orientation", "plus")
        processed_user_allele = format_user_allele(raw_user_allele, orientation)

        specific_summary = snp_info.get("Top_Summary", "No general summary available.")
        magnitude = "0"
        categories = CATEGORY_LOOKUP.get(snp_id_lower, [])

        for geno in snp_info.get("Genotypes", []):
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
            "Summary": specific_summary,
            "Categories": categories
        })

    # Use try/except to correctly handle negative magnitudes (e.g. -1.5 for beneficial variants)
    results.sort(key=lambda x: _safe_float(x['Magnitude']), reverse=True)
    return results


def _safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


@app.route('/')
def index():
    _refresh_cache()
    user_file = os.path.join(BASE_DIR, 'snpDict.json')
    report_data = cross_reference_snps(user_file)

    genome_summary = [
        {
            'SNP': r['SNP'], 'Gene': r['Gene'],
            'Allele': r['Processed_Allele'], 'Magnitude': r['Magnitude'],
            'Summary': r['Summary'], 'Categories': r['Categories']
        }
        for r in report_data[:25]
        if r.get('Summary') and r['Summary'] != 'No general summary available.'
    ]

    return render_template('index.html', report_data=report_data, genome_summary=genome_summary)


@app.route('/api/ollama-status')
def ollama_status():
    if not _REQUESTS_OK:
        return jsonify({'available': False, 'models': [], 'error': 'requests library not installed'})
    try:
        resp = _req.get(f'{OLLAMA_BASE}/api/tags', timeout=3)
        models = [m['name'] for m in resp.json().get('models', [])]
        return jsonify({'available': True, 'models': models})
    except Exception:
        return jsonify({'available': False, 'models': []})


@app.route('/api/analyze-snp', methods=['POST'])
def analyze_snp():
    if not _REQUESTS_OK:
        return jsonify({'error': 'requests library not installed — run: pip install requests'}), 500
    data = request.json
    snp  = data.get('snp', {})
    model = data.get('model', '')

    prompt = (
        "Analyze this genetic variant from a 23andMe report:\n\n"
        f"SNP ID: {snp.get('SNP', 'Unknown')}\n"
        f"Gene: {snp.get('Gene', 'Unknown')}\n"
        f"Chromosome: {snp.get('Chromosome', 'Unknown')}\n"
        f"Your allele: {snp.get('Processed_Allele', 'Unknown')}\n"
        f"SNPedia magnitude: {snp.get('Magnitude', '0')} (0=benign, 1=interesting, 2=moderate, 3+=significant)\n"
        f"Trait summary: {snp.get('Summary', 'None')}\n"
        f"Disease categories: {', '.join(snp.get('Categories', [])) or 'Unclassified'}\n\n"
        "Please explain in plain language:\n"
        "1. What this gene does in the body\n"
        "2. What this specific allele means for this individual\n"
        "3. Any relevant lifestyle or health considerations\n"
        "4. Important caveats about interpreting genetic testing\n\n"
        "Be factual, accessible, and non-alarmist. Always recommend consulting a healthcare provider for medical decisions."
    )

    def generate():
        try:
            resp = _req.post(f'{OLLAMA_BASE}/api/generate',
                             json={'model': model, 'prompt': prompt, 'stream': True},
                             stream=True, timeout=120)
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get('response', '')
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get('done'):
                        yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/chat', methods=['POST'])
def ollama_chat():
    if not _REQUESTS_OK:
        return jsonify({'error': 'requests library not installed — run: pip install requests'}), 500
    data     = request.json
    messages = data.get('messages', [])
    model    = data.get('model', '')
    summary  = data.get('genome_summary', [])

    context = '\n'.join(
        f"- {s['SNP']} ({s['Gene']}): allele {s['Allele']}, magnitude {s['Magnitude']}, "
        f"categories: {', '.join(s.get('Categories', []))}, trait: {s['Summary']}"
        for s in summary
    ) or 'No significant variants loaded yet.'

    system_msg = {
        'role': 'system',
        'content': (
            "You are a genomics assistant helping a user understand their personal 23andMe DNA data.\n\n"
            f"Their top genetic variants by significance:\n{context}\n\n"
            "Guidelines:\n"
            "- Explain genetics in plain, non-alarmist language\n"
            "- Always recommend a healthcare provider for medical decisions\n"
            "- Acknowledge DTC testing limitations (false positives, incomplete coverage)\n"
            "- Reference the user's specific SNPs when relevant\n"
            "- Be concise but thorough"
        )
    }

    def generate():
        try:
            resp = _req.post(f'{OLLAMA_BASE}/api/chat',
                             json={'model': model, 'messages': [system_msg] + messages, 'stream': True},
                             stream=True, timeout=120)
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get('message', {}).get('content', '')
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get('done'):
                        yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    app.run(debug=True)
