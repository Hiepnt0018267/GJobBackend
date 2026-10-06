"""Development-only fitted-state adapter; unchanged lexical scorer/tokenizer."""
import hashlib
import math
from collections import Counter

from evaluation.baseline_lexical import LexicalBaseline, tokens

STATE_VERSION = 'baseline-v1-development-state-v1'
TRANSFORM_VERSION = 'fixed-development-vocabulary-transform-v1'


def token_key(token):
    return hashlib.sha256(token.encode()).hexdigest()


def development_state(documents):
    # The only fit is on caller-supplied development documents, never fresh text.
    engine = LexicalBaseline(documents)
    state = {'version': STATE_VERSION, 'transform_version': TRANSFORM_VERSION,
             'development_document_count': len(documents),
             'idf_by_token_sha256': {token_key(term): value for term, value in sorted(engine.idf.items())},
             'vocabulary_size': len(engine.idf), 'oov_policy': 'ignore OOV in TF-IDF vectors; literal title coverage unchanged'}
    return engine, state


def transform_only(state, documents):
    """Allocate scorer inputs without fitting IDF or adding vocabulary terms."""
    # Bypass fitting constructor; score() itself is reused unchanged.
    engine = object.__new__(LexicalBaseline)
    engine.idf = dict(state['idf_by_token_sha256'])
    engine.counts = {key: Counter(tokens(text)) for key, text in sorted(documents.items())}
    engine.vectors = {key: {term: (1 + math.log(count)) * state['idf_by_token_sha256'][token_key(term)]
                           for term, count in sorted(counts.items()) if token_key(term) in state['idf_by_token_sha256']}
                      for key, counts in engine.counts.items()}
    engine.norms = {key: math.sqrt(math.fsum(v * v for v in vector.values())) for key, vector in engine.vectors.items()}
    return engine
