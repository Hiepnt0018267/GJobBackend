"""Deterministic contact minimization for matching text, not raw records.

Conservative, English/Vietnamese contact labels; not a general PII/NER detector.
Unlabeled phones require a + country prefix or a recognizable VN 0-prefix shape.
Unlabeled URLs are limited to explicit social/profile/messaging/contact paths.
Technical URLs, dates, compensation and arbitrary numeric IDs remain unchanged.
"""
import re

MATCHING_CANONICAL_VERSION = 'matching-canonical-v3-explicit-identity-contract'
CONTACT_PLACEHOLDER = '[CONTACT]'

_EMAIL = re.compile(r'(?<![\w.+-])(?:mailto:)?[\w.+-]+@[\w-]+(?:\.[\w-]+)+', re.I)
_PHONE_BODY = (r'(?:\(\d{2,4}\)[ .-]?\d{3,4}[ .-]?\d{4}'
               r'|\d{3}[ .-]\d{3}[ .-]\d{3,4}'
               r'|\d{2}[ .-]\d{4}[ .-]\d{4}|\d{7,15})')
_PHONE_CANDIDATE = r'(?:\+\d{1,3}[ .-]?)?' + _PHONE_BODY
_LABELED_PHONE = re.compile(
    r'\b(?:phone|tel(?:ephone)?|mobile|hotline|điện thoại|sđt)\s*:\s*('
    + _PHONE_CANDIDATE + r')(?!\w)', re.I)
_UNLABELED_PHONE = re.compile(
    r'(?<![\w\d.+-])(?:\+\d{1,3}[ .-]?' + _PHONE_BODY
    + r'|0[35789]\d[ .-]\d{3}[ .-]\d{4}'
      r'|0\d{3}[ .-]\d{3}[ .-]\d{3}'
      r'|\(0\d{2,3}\)[ .-]?\d{4}[ .-]?\d{4}'
      r'|0[235789]\d{8,9})(?![\w\d])')
_URL = re.compile(r'(?:https?://|www\.)(?:[^\s<>\[\]"\x27]+)', re.I)
_BARE_SOCIAL = re.compile(
    r'(?<![\w/])(?:linkedin\.com/in/|(?:www\.)?(?:facebook\.com|instagram\.com|'
    r't\.me|wa\.me|zalo\.me)/)[^\s<>\[\]"\x27]+', re.I)
_CONTACT_URL_LABEL = re.compile(
    r'\b(?:linkedin|portfolio|personal website|contact(?: page)?|website cá nhân|'
    r'hồ sơ cá nhân)\s*:\s*$', re.I)
_LABEL_WITH_TOKEN = re.compile(
    r'\b(?:email|e-mail|phone|tel(?:ephone)?|mobile|hotline|contact|linkedin|portfolio|'
    r'personal website|điện thoại|sđt|liên hệ)\s*:\s*\[CONTACT\]', re.I)
_NUMERIC_METADATA_LABEL = re.compile(
    r'\b(?:certification(?:\s+id)?|certificate(?:\s+id)?|license(?:\s+id)?|'
    r'serial|invoice|order|salary|quantity|model|version|id)\s*[:#]?\s*$', re.I)


def _phone_replacement(match):
    candidate = match.group(0)
    if _NUMERIC_METADATA_LABEL.search(match.string[:match.start()].rsplit('\n', 1)[-1]):
        return candidate
    digits = re.sub(r'\D', '', candidate)
    # Four-digit year/date chunks and decimal-only chains are not phone evidence.
    if not 9 <= len(digits) <= 15 or re.search(r'\b(?:19|20)\d{2}[-/]\d', candidate):
        return candidate
    if '.' in candidate and not any(c in candidate for c in ('+', '(', ' ', '-')):
        return candidate
    return CONTACT_PLACEHOLDER


def _contact_url(url, prefix):
    from urllib.parse import urlsplit

    stripped = url.rstrip('.,;:!?)')
    parsed = urlsplit(stripped if '://' in stripped else 'https://' + stripped)
    host = (parsed.hostname or '').lower().removeprefix('www.')
    path = parsed.path.lower()
    return bool(
        _CONTACT_URL_LABEL.search(prefix)
        or (host == 'linkedin.com' and path.startswith('/in/'))
        or host in {'facebook.com', 'instagram.com', 't.me', 'wa.me', 'zalo.me'}
        or path.rstrip('/') in {'/contact', '/contact-me', '/about-me'}
    )


def _sanitize_phones(text):
    # Technical URL numeric paths/query parameters are not phone evidence.
    parts = []
    cursor = 0
    for match in _URL.finditer(text):
        chunk = text[cursor:match.start()]
        parts.append(_UNLABELED_PHONE.sub(_phone_replacement,
                     _LABELED_PHONE.sub(_phone_replacement, chunk)))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(_UNLABELED_PHONE.sub(_phone_replacement,
                 _LABELED_PHONE.sub(_phone_replacement, text[cursor:])))
    return ''.join(parts)


def sanitize_matching_text(text: str | None) -> str:
    """Replace supported contacts only; preserve non-contact text byte-for-byte."""
    if not text:
        return ''
    result = _EMAIL.sub(CONTACT_PLACEHOLDER, text)

    def replace_url(match):
        if not _contact_url(match.group(0), result[:match.start()].rsplit('\n', 1)[-1]):
            return match.group(0)
        suffix = match.group(0)[len(match.group(0).rstrip('.,;:!?)')):]
        return CONTACT_PLACEHOLDER + suffix

    result = _URL.sub(replace_url, result)
    result = _BARE_SOCIAL.sub(CONTACT_PLACEHOLDER, result)
    result = _sanitize_phones(result)
    return _LABEL_WITH_TOKEN.sub(CONTACT_PLACEHOLDER, result)


def find_matching_text_privacy_issues(text: str | None) -> tuple[str, ...]:
    """Safe aggregate audit only: never return identifier values or text spans."""
    if not text:
        return ()
    issues = []
    if _EMAIL.search(text):
        issues.append('email')
    if _sanitize_phones(text) != text:
        issues.append('phone')
    if _BARE_SOCIAL.search(text) or any(
        _contact_url(m.group(0), text[:m.start()].rsplit('\n', 1)[-1]) for m in _URL.finditer(text)
    ):
        issues.append('contact_url')
    return tuple(issues)


def find_cv_identity_overlaps(text: str, personal_info) -> tuple[str, ...]:
    """Report known-value collisions, NOT a name classifier or text redactor.

    A collision can be genuine identity leakage OR LLM field misclassification.
    Callers must fail closed/adjudicate, never blindly delete professional prose.
    No identifier value is returned. Structural exclusion remains the primary
    defense; this auditor is defense-in-depth for values copied into other fields.
    """
    normalized_text = ' '.join(text.casefold().split())
    fields = []
    for key in ('full_name', 'email', 'phone', 'address', 'date_of_birth'):
        value = getattr(personal_info, key, None)
        normalized = ' '.join(str(value).casefold().split()) if value else ''
        if len(normalized) >= 6 and normalized in normalized_text:
            fields.append(key)
    return tuple(fields)


def identity_fields_influence_matching(full_text: str, identity_free_text: str) -> bool:
    """Provenance audit: removing identity fields must not change matching text.

    Does not mistake independently present professional text for field inclusion.
    Does not redact words or classify a person's name.
    """
    return full_text != identity_free_text
