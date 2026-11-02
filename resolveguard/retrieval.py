"""Version-filtered local keyword RAG. No embeddings, credentials or network."""
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / 'resolveguard_synthetic_v04' / 'fixtures'
STOP = frozenset('a an the is are was my me i you your this that to for of and or in on it do does can what how please'.split())


def words(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP]


def chunk_document(doc, target=400, overlap=50):
    """Whitespace-token approximation, not the hosted model's billing tokenizer.

    Short fixture documents stay intact. Heading blocks, lists, and tables stay
    together; long ordinary prose splits at sentence boundaries with overlap.
    Rule/exception blocks stay whole even when over target, and are flagged.
    """
    if target < 20 or overlap < 0 or overlap >= target:
        raise ValueError('Require target >= 20 and 0 <= overlap < target')
    paragraphs = re.split(r'\n\s*\n', doc['text'].strip())
    units = []
    for paragraph in paragraphs:
        protected = ('|' in paragraph or re.search(r'(?im)^\s*(?:[-*]|\d+[.)])\s', paragraph)
                     or re.search(r'\b(?:except|unless|however)\b', paragraph, re.I))
        if protected or len(paragraph.split()) <= target:
            units.append((paragraph, bool(protected)))
        else:
            sentences = re.split(r'(?<=[.!?])\s+', paragraph)
            current = []
            for sentence in sentences:
                if current and len((' '.join(current)+' '+sentence).split()) > target:
                    units.append((' '.join(current), False))
                    current = []
                current.append(sentence)
            if current:
                units.append((' '.join(current), False))
    chunks = []
    previous = ''
    for index, (body, protected) in enumerate(units):
        prefix = ' '.join(previous.split()[-overlap:]) if overlap and index and not protected else ''
        text = (prefix+' '+body).strip()
        chunks.append({**{k: doc.get(k) for k in ('doc_id', 'title', 'version', 'product', 'jurisdiction',
                                                'effective_date', 'expires_at', 'approval_status')},
                       'chunk_id': f"{doc['doc_id']}:{doc['version']}:{index+1}",
                       'section': doc['title'], 'text': text,
                       'token_count_approx': len(text.split()),
                       'oversize_preserved': len(text.split()) > target})
        previous = body
    return chunks


class PolicyIndex:
    def __init__(self, documents=None):
        if documents is None:
            groups = json.loads((FIXTURES/'knowledge_bases.json').read_text())
            documents = [d for group in groups for d in group['docs']]
            extra = FIXTURES.parents[1]/'data/supplemental_fixtures.json'
            documents.extend(json.loads(extra.read_text())['policies'])
        self.chunks = [c for doc in documents for c in chunk_document(doc)]

    def retrieve(self, query, product='DEBIT_CHECKING', jurisdiction='US', as_of='2026-10-30', k=4):
        today = date.fromisoformat(as_of)
        eligible = [c for c in self.chunks
                    if c['approval_status'] == 'APPROVED_FOR_SYNTHETIC_TEST'
                    and c['product'] in ('ALL', product) and c['jurisdiction'] == jurisdiction
                    and c['effective_date'] and date.fromisoformat(c['effective_date']) <= today
                    and (not c['expires_at'] or today < date.fromisoformat(c['expires_at']))]
        # Conflicting active versions are not silently blended into an answer.
        versions = {}
        for c in eligible:
            versions.setdefault(c['doc_id'], set()).add(c['version'])
        conflicts = {key for key, value in versions.items() if len(value) > 1}
        tokens = set(words(query))
        privacy_query = bool(re.search(r'\b(card numbers?|passwords?|pins?|cvvs?|one.time codes?|credentials|private data)\b', query, re.I))
        scored = []
        for chunk in eligible:
            frequencies = Counter(words(chunk['title']+' '+chunk['text']))
            overlap = tokens.intersection(frequencies)
            if not overlap:
                continue
            if chunk['doc_id'] in conflicts:
                return {'status': 'CONFLICT', 'chunks': [], 'reason_code': 'ACTIVE_POLICY_VERSIONS_CONFLICT'}
            score = sum(1+math.log(frequencies[t]) for t in overlap) / math.sqrt(max(1, sum(frequencies.values())))
            if privacy_query and chunk['doc_id'].startswith('POL-PRIV-'):
                score += 5
            scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1]['chunk_id']))
        selected = [dict(c, score=round(score, 6)) for score, c in scored[:max(0, min(k, 5))]]
        return {'status': 'OK' if selected else 'NOT_FOUND', 'chunks': selected}

    def save(self, path):
        Path(path).write_text(json.dumps({'retrieval': 'local_keyword',
                                         'tokenizer': 'whitespace_approximation',
                                         'chunks': self.chunks}, indent=2)+'\n', encoding='utf-8')
