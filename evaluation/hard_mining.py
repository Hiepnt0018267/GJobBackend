"""Deterministic lexical mining; no labels, matching engines, DB or AI imports."""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from evaluation.common import stable_rank
from evaluation.generate_pairs import JobRecord, ResumeRecord

# Transparent professional-role cue vocabulary, NOT a mapping of skill_abr codes.
FAMILIES = {
    'software': 'software developer development programmer programming python java javascript typescript react backend frontend devops database sql network cybersecurity linux cloud api web',
    'engineering': 'mechanical electrical electronics engineer engineering manufacturing automation industrial instrumentation circuits equipment cad autocad solidworks',
    'healthcare': 'nurse nursing clinical patient physician medical hospital healthcare pharmacy pharmacist surgical therapy therapist dental radiology',
    'education': 'teacher teaching classroom curriculum education educator school instructor student pedagogy',
    'finance': 'financial finance banking bank investment lending credit mortgage risk portfolio securities wealth insurance underwriting',
    'accounting': 'accountant accounting payroll bookkeeping ledger audit auditing reconciliation taxation tax accounts payable receivable',
    'sales': 'sales selling salesperson retail customer clients account business development revenue territory quota prospecting',
    'marketing': 'marketing advertising campaign media communications public relations branding seo content digital social journalism',
    'legal': 'legal lawyer attorney litigation counsel paralegal judicial court law contract',
    'hr': 'recruiter recruitment recruiting staffing human resources hr onboarding talent personnel benefits employee',
    'design': 'designer design graphic graphics visual illustration illustrator photoshop typography creative artwork ux ui',
    'hospitality': 'chef culinary kitchen cook cooking food restaurant catering hospitality hotel guest beverage pastry',
    'construction': 'construction carpenter carpentry masonry drywall concrete building plumbing electrician roofing excavation contractor',
    'aviation': 'aviation aircraft aerospace flight pilot airport aeronautical airline avionics',
    'agriculture': 'agriculture agricultural farm farming crop crops livestock agronomy horticulture soil irrigation',
    'science': 'scientist research laboratory biology chemistry biochemistry microbiology physics experiment scientific',
    'fitness': 'fitness sports athletic trainer exercise coaching wellness strength conditioning recreation',
    'apparel': 'apparel fashion garment garments textile merchandising wardrobe sewing clothing tailoring',
    'operations': 'logistics supply warehouse inventory procurement shipping distribution purchasing transportation dispatch operations',
    'support': 'support service call center customer technical helpdesk troubleshooting desktop',
}
SPECIALTIES = {
    'frontend': 'frontend front-end react angular vue css html ui ux',
    'backend': 'backend back-end python java api server django fastapi spring',
    'data': 'data analytics analyst sql etl warehouse tableau powerbi statistics',
    'mobile': 'mobile android ios native swift kotlin flutter',
    'infrastructure': 'network infrastructure devops linux cloud aws azure security cybersecurity',
    'investment': 'investment securities portfolio wealth trading asset',
    'credit': 'credit lending mortgage loans underwriting risk',
    'accounting': 'accounting payroll audit tax ledger reconciliation',
    'sales': 'sales quota selling prospecting territory revenue',
    'marketing': 'marketing seo campaign advertising branding',
    'clinical': 'clinical nurse patient physician medical hospital',
    'laboratory': 'laboratory scientist chemistry biology research',
    'teaching': 'teacher classroom teaching curriculum educator',
    'recruiting': 'recruiter recruiting staffing talent recruitment',
    'mechanical': 'mechanical machinery cad solidworks manufacturing',
    'electrical': 'electrical electronics circuits instrumentation power',
}
GENERIC = set('manager management director senior lead principal associate junior entry assistant specialist analyst engineer consultant coordinator officer executive general professional business company experience skills team ability work years responsibilities required preferred qualifications communication excellent strong successful provide support service development project related knowledge opportunity position role duties resume summary highlights city state university college bachelor degree education certification training employment history microsoft office word excel outlook powerpoint references phone email address including ensure effectively working perform maintain demonstrated processes company companies clients'.split())


def terms(text: str) -> frozenset[str]:
    text = re.sub(r'\S+@\S+|https?://\S+', ' ', text.casefold())
    tokens = re.findall(r'[a-z][a-z+#-]{2,}', text)
    return frozenset(t.rstrip('-') for t in tokens if t not in GENERIC)


def cues(text: str, vocabulary: dict[str, str]) -> Counter:
    found = terms(text)
    return Counter({name: len(found & set(words.split())) for name, words in vocabulary.items()})


def family(text: str, headline: str = '') -> str:
    counts = cues(text, FAMILIES)
    header = cues(headline, FAMILIES)
    scores = {key: counts[key] + 3 * header[key] for key in FAMILIES}
    best = max(sorted(scores), key=lambda key: scores[key])
    return best if scores[best] >= 2 else 'unknown'


def specialty(text: str) -> str:
    counts = cues(text, SPECIALTIES)
    best = max(sorted(counts), key=lambda key: counts[key])
    return best if counts[best] >= 2 else 'unknown'


def seniority(text: str) -> int | None:
    text = text.casefold()
    for level, pattern in [(3, r'\b(principal|director|executive|architect)\b'),
                           (2, r'\b(senior|lead|manager)\b'),
                           (0, r'\b(junior|entry.level|intern|internship)\b'),
                           (1, r'\b(associate|mid.level)\b')]:
        if re.search(pattern, text):
            return level
    return None


@dataclass(frozen=True)
class Evidence:
    lexical_overlap: float
    title_overlap: float
    domain_overlap: int
    cv_family: str
    job_family: str
    cv_specialty: str
    job_specialty: str
    mismatch_cues: tuple[str, ...]
    shared_terms: tuple[str, ...]
    sampling_score: float


class HardMiner:
    def __init__(self, resumes: list[ResumeRecord], jobs: list[JobRecord], seed: int = 42, pool_limit: int = 180):
        self.seed, self.pool_limit = seed, pool_limit
        self.cvs = {r.cv_id: r for r in resumes}
        self.jobs = {j.job_id: j for j in jobs}
        self.cv_terms = {r.cv_id: terms(r.text) for r in resumes}
        self.job_terms = {j.job_id: terms(j.semantic_text) for j in jobs}
        self.title_terms = {j.job_id: terms(j.title) for j in jobs}
        self.cv_family = {r.cv_id: family(r.text, r.text[:500]) for r in resumes}
        self.job_family = {j.job_id: family(j.description[:1200], j.title) for j in jobs}
        self.cv_specialty = {r.cv_id: specialty(r.text[:3000]) for r in resumes}
        self.job_specialty = {j.job_id: specialty(j.title + ' ' + j.description[:1500]) for j in jobs}
        self.index: dict[str, set[str]] = defaultdict(set)
        self.family_index: dict[str, set[str]] = defaultdict(set)
        df = Counter()
        for jid, token_set in self.job_terms.items():
            df.update(token_set)
            self.family_index[self.job_family[jid]].add(jid)
            for term in token_set:
                self.index[term].add(jid)
        self.idf = {t: math.log(1 + len(jobs) / (1 + count)) for t, count in df.items()}
        self.cv_norm = {cid: math.sqrt(sum(self.idf.get(t, 0)**2 for t in ts)) for cid, ts in self.cv_terms.items()}
        self.job_norm = {jid: math.sqrt(sum(self.idf[t]**2 for t in ts)) for jid, ts in self.job_terms.items()}

    def evidence(self, cid: str, jid: str) -> Evidence:
        cv, job = self.cvs[cid], self.jobs[jid]
        shared = self.cv_terms[cid] & self.job_terms[jid]
        lexical = sum(self.idf[t]**2 for t in shared) / max(1e-9, self.cv_norm[cid] * self.job_norm[jid])
        title = self.title_terms[jid]
        overlap = sum(self.idf.get(t, 0) for t in title & self.cv_terms[cid]) / max(1e-9, sum(self.idf.get(t, 0) for t in title))
        same = int(self.cv_family[cid] != 'unknown' and self.cv_family[cid] == self.job_family[jid])
        cs, js = self.cv_specialty[cid], self.job_specialty[jid]
        mismatch = []
        if cs != 'unknown' and js != 'unknown' and cs != js:
            mismatch.append('specialization_difference')
        csen, jsen = seniority(cv.text[:700]), seniority(job.title + ' ' + job.experience_level)
        if csen is not None and jsen is not None and jsen - csen >= 2:
            mismatch.append('seniority_gap')
        # Stack cues are literal terms, never skill_abr interpretations.
        stack = {'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue', 'swift', 'kotlin', 'sql', 'linux', 'aws', 'azure'}
        required = terms(job.title) & stack
        if required and required - self.cv_terms[cid]:
            mismatch.append('title_stack_not_evidenced')
        score = .55 * lexical + .25 * overlap + .20 * same
        return Evidence(round(lexical, 6), round(overlap, 6), same, self.cv_family[cid], self.job_family[jid],
                        cs, js, tuple(mismatch), tuple(sorted(shared, key=lambda t: (-self.idf[t], t))[:15]), round(score, 6))

    def classify(self, e: Evidence) -> str:
        professional = set().union(*(set(words.split()) for words in FAMILIES.values())) - GENERIC
        shared_professional = len(set(e.shared_terms) & professional)
        if e.domain_overlap and e.lexical_overlap >= .07 and e.mismatch_cues and (e.title_overlap >= .25 or shared_professional >= 4):
            return 'INFORMATIVE_HARD_NEGATIVE_CANDIDATE'
        if e.domain_overlap and e.lexical_overlap >= .10 and e.title_overlap >= .40 and not e.mismatch_cues:
            return 'INFORMATIVE_POSITIVE_CANDIDATE'
        if not e.domain_overlap and e.lexical_overlap <= .04 and e.title_overlap <= .15:
            return 'EASY_SANITY_CANDIDATE'
        return 'TOO_TRIVIAL'

    def retrieve(self, cid: str) -> list[str]:
        # Inverted index retrieval, not a full CV x JD scoring pass.
        counts = Counter()
        for term in sorted(self.cv_terms[cid]):
            posting = self.index.get(term, ())
            if len(posting) > max(50, len(self.jobs) * .25):
                continue
            for jid in sorted(posting):
                counts[jid] += self.idf[term]
        related = self.family_index.get(self.cv_family[cid], set())
        ranked = sorted(counts, key=lambda jid: (jid not in related, -counts[jid], stable_rank(self.seed, cid, jid)))
        pool = ranked[:self.pool_limit]
        # Small deterministic cross-family pool reserved for sanity checks.
        other = sorted((jid for jid in self.jobs if jid not in related), key=lambda jid: stable_rank(self.seed, 'easy', cid, jid))[:24]
        return list(dict.fromkeys(pool + other))
