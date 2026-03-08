"""Heuristic Toulmin auto-tagger — generates claim/data/warrant tags from plain text.

Runs in microseconds (no LLM call). Used when agents submit turns without toulmin_tags.
"""
import re


# Keyword patterns for each Toulmin category
_CLAIM_PATTERNS = re.compile(
    r"\b(i argue|i claim|my position|i contend|i maintain|i assert|i believe|"
    r"my thesis|the thesis|we should|it is true that|the conclusion)\b",
    re.IGNORECASE,
)
_DATA_PATTERNS = re.compile(
    r"\b(because|evidence|data shows|according to|studies show|research indicates|"
    r"statistics|findings|empirically|the fact that|as shown by|experiment|"
    r"for example|for instance|as demonstrated)\b",
    re.IGNORECASE,
)
_WARRANT_PATTERNS = re.compile(
    r"\b(therefore|this means|which implies|consequently|thus|hence|it follows|"
    r"this demonstrates|this shows|this proves|we can conclude|"
    r"the reasoning|the logic|this indicates)\b",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> list[tuple[int, int, str]]:
    """Split text into sentences, returning (start, end, text) tuples."""
    sentences = []
    # Split on sentence-ending punctuation followed by whitespace or end
    for match in re.finditer(r'[^.!?\n]+(?:[.!?]+|$)', text):
        s = match.start()
        e = match.end()
        sentence_text = match.group().strip()
        if sentence_text:
            sentences.append((s, e, sentence_text))
    # If no sentences found (e.g., text without punctuation), treat whole text as one
    if not sentences and text.strip():
        sentences.append((0, len(text), text.strip()))
    return sentences


def auto_generate_toulmin_tags(content: str) -> list[dict]:
    """Generate Toulmin tags from content using keyword heuristics.

    Returns list of dicts: [{"type": str, "start": int, "end": int, "label": str}, ...]
    """
    if not content or not content.strip():
        return []

    sentences = _split_sentences(content)
    if not sentences:
        return []

    tags = []
    tagged_indices = set()

    # First pass: match by keywords
    for i, (start, end, text) in enumerate(sentences):
        if _CLAIM_PATTERNS.search(text):
            tags.append({"type": "claim", "start": start, "end": end, "label": "Claim"})
            tagged_indices.add(i)
        elif _DATA_PATTERNS.search(text):
            tags.append({"type": "data", "start": start, "end": end, "label": "Evidence"})
            tagged_indices.add(i)
        elif _WARRANT_PATTERNS.search(text):
            tags.append({"type": "warrant", "start": start, "end": end, "label": "Reasoning"})
            tagged_indices.add(i)

    # If we found at least one tag, fill in missing required types
    has_claim = any(t["type"] == "claim" for t in tags)
    has_data = any(t["type"] == "data" for t in tags)
    has_warrant = any(t["type"] == "warrant" for t in tags)

    if tags:
        # Assign untagged sentences to missing types
        untagged = [i for i in range(len(sentences)) if i not in tagged_indices]
        if not has_claim and untagged:
            idx = untagged.pop(0)
            s, e, _ = sentences[idx]
            tags.append({"type": "claim", "start": s, "end": e, "label": "Claim"})
        if not has_data and untagged:
            idx = untagged.pop(0)
            s, e, _ = sentences[idx]
            tags.append({"type": "data", "start": s, "end": e, "label": "Evidence"})
        if not has_warrant and untagged:
            idx = untagged.pop(0)
            s, e, _ = sentences[idx]
            tags.append({"type": "warrant", "start": s, "end": e, "label": "Reasoning"})
    else:
        # Fallback: no keywords matched. Use positional heuristic.
        n = len(sentences)
        if n >= 3:
            # First = claim, middle = data, last = warrant
            s, e, _ = sentences[0]
            tags.append({"type": "claim", "start": s, "end": e, "label": "Claim"})
            mid = n // 2
            s, e, _ = sentences[mid]
            tags.append({"type": "data", "start": s, "end": e, "label": "Evidence"})
            s, e, _ = sentences[-1]
            tags.append({"type": "warrant", "start": s, "end": e, "label": "Reasoning"})
        elif n == 2:
            s, e, _ = sentences[0]
            tags.append({"type": "claim", "start": s, "end": e, "label": "Claim"})
            s, e, _ = sentences[1]
            tags.append({"type": "data", "start": s, "end": e, "label": "Evidence"})
        else:
            # Single sentence — tag as claim spanning full content
            tags.append({"type": "claim", "start": 0, "end": len(content), "label": "Claim"})

    return tags
