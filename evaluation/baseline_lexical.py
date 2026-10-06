"""Frozen offline lexical reference, distinct from production structured-skill baseline."""
import hashlib
import math
import re
import unicodedata
from collections import Counter

VERSION = 'baseline-v1-offline-lexical'
PREPROCESSING_VERSION = 'nfkc-casefold-static-stopwords-v1'
TEXT_WEIGHT = .7
TITLE_WEIGHT = .3
DEFAULT_THRESHOLD = .5
# Local generic English function words/boilerplate, not skills, roles or skill_abr mappings.
STOPWORDS = frozenset('a an and are as at be been being but by can could did do does each for from had has have how if in into is it its may more most must no not of on or our out own per please should so some such than that the their them these they this those through to too under up upon us use used using was we were what when where which while who will with within would you your years year job jobs position role company companies candidate candidates resume summary responsibilities qualifications requirements description title skills experience work working opportunity opportunities'.split())


def tokens(text):
    normalized = unicodedata.normalize('NFKC', text).casefold()
    normalized = re.sub(r'\S+@\S+|https?://\S+', ' ', normalized)
    return tuple(token for raw in re.findall(r'(?u)\b[^\W\d_][\w+#.-]*', normalized)
                 if (token := raw.strip('.-')) not in STOPWORDS and len(token) >= 2)


def definition():
    return dict(version=VERSION, preprocessing=PREPROCESSING_VERSION,
        weights={'tfidf_lexical_cosine': TEXT_WEIGHT, 'title_token_coverage': TITLE_WEIGHT},
        default_threshold=DEFAULT_THRESHOLD, score_range=[0, 1],
        term_frequency='1 + ln(count)', inverse_document_frequency='ln((1+N)/(1+df)) + 1',
        title_formula='|unique JD title tokens intersect CV tokens| / |unique JD title tokens|; empty=0',
        stopwords_sha256=hashlib.sha256('\n'.join(sorted(STOPWORDS)).encode()).hexdigest(),
        skill_vocabulary=None, seniority_signal=None,
        formula='0.7 * TF-IDF lexical cosine + 0.3 * title-token coverage',
        production_baseline='Unchanged structured-skill coverage engine; not this raw-text reference.')


class LexicalBaseline:
    def __init__(self, documents):
        """Fit IDF on unique referenced entities, never on labels or predictions."""
        self.counts = {key: Counter(tokens(text)) for key, text in sorted(documents.items())}
        df = Counter(term for counts in self.counts.values() for term in sorted(counts))
        self.idf = {term: math.log((1 + len(documents)) / (1 + count)) + 1 for term, count in sorted(df.items())}
        self.vectors = {key: {term: (1 + math.log(count)) * self.idf[term] for term, count in sorted(counts.items())}
                        for key, counts in self.counts.items()}
        self.norms = {key: math.sqrt(math.fsum(value * value for value in vector.values())) for key, vector in self.vectors.items()}

    def score(self, cv_key, job_key, title):
        left, right = self.vectors[cv_key], self.vectors[job_key]
        denominator = self.norms[cv_key] * self.norms[job_key]
        lexical = math.fsum(left[t] * right[t] for t in sorted(left.keys() & right.keys())) / denominator if denominator else 0.
        title_terms = set(tokens(title))
        coverage = len(title_terms & self.counts[cv_key].keys()) / len(title_terms) if title_terms else 0.
        return min(1., max(0., TEXT_WEIGHT * lexical + TITLE_WEIGHT * coverage))
