"""
Step 6: Consolidation — the single entry point Person 2's debate agents will call.

Given a health claim, this runs the full evidence pipeline internally
(search → fetch → filter → chunk → quality metadata → stance) and returns
a clean list of EvidenceSnippet objects matching the shared schema.

Person 2 doesn't need to know or care about the 5 steps inside —
they just call get_evidence_for_claim(claim) and get snippets back.
"""

import sys
from pathlib import Path

# Make the shared schema importable regardless of where this is run from
sys.path.append(str(Path(__file__).resolve().parents[1]))  # points at backend/app/
from core.schemas import EvidenceSnippet

from pubmed_search import search_pubmed
from pubmed_fetch import fetch_abstracts
from snippet_chunker import chunk_abstract
from quality_extractor import enrich_snippet
from stance_classifier import classify_snippets_stance  # remove is_relevant from this import




def extract_claim_keywords(claim: str) -> tuple[list[str], list[str]]:
    """
    Splits the claim into two keyword groups — roughly 'subject/intervention'
    (first half) and 'outcome' (second half) — so relevance checking can
    require a match from BOTH sides, not just any two words from one side.
    """
    import re
    stopwords = {"a", "an", "the", "is", "are", "do", "does", "of", "for",
                 "to", "and", "or", "improve", "improves", "prevent",
                 "prevents", "reduce", "reduces", "increase", "increases",
                 "supplements", "supplement", "supplementation"}

    words = re.findall(r"[a-zA-Z]+", claim.lower())
    words = [w for w in words if w not in stopwords and len(w) > 2]

    midpoint = len(words) // 2
    subject_terms = words[:midpoint] if midpoint > 0 else words
    outcome_terms = words[midpoint:] if midpoint > 0 else words

    return subject_terms, outcome_terms


def is_relevant(paper: dict, subject_terms: list[str], outcome_terms: list[str]) -> bool:
    """
    Requires at least one match from subject/intervention terms AND
    at least one match from outcome terms. Uses stem matching (checks
    if the term, minus a trailing 's', appears as a substring) to
    handle singular/plural mismatches like 'infection' vs 'infections'.
    """
    text = (paper["title"] + " " + paper["abstract"]).lower()

    def stem_match(term: str, text: str) -> bool:
        stem = term.rstrip("s")  # "infections" -> "infection", still matches "infections" too
        return stem in text

    has_subject = any(stem_match(term, text) for term in subject_terms)
    has_outcome = any(stem_match(term, text) for term in outcome_terms)
    return has_subject and has_outcome

def get_evidence_for_claim(claim: str, retmax: int = 8) -> list[EvidenceSnippet]:
    subject_terms, outcome_terms = extract_claim_keywords(claim)

    ids = search_pubmed(claim, retmax=retmax)
    papers = fetch_abstracts(ids)

    relevant_papers = [p for p in papers if is_relevant(p, subject_terms, outcome_terms)]

    all_snippets = []
    for paper in relevant_papers:
        snippets = chunk_abstract(paper)
        pubmed_types = paper.get("pubmed_types", [])
        snippets = [enrich_snippet(s, pubmed_types) for s in snippets]
        snippets = classify_snippets_stance(claim, snippets)
        all_snippets.extend(snippets)

    # ... rest stays the same (converting to EvidenceSnippet objects)

    # Convert raw dicts into validated EvidenceSnippet objects
    evidence_snippets = []
    for s in all_snippets:
        evidence_snippets.append(EvidenceSnippet(
            id=s["id"],
            text=s["text"],
            stance=s["stance"] if s["stance"] in ("support", "contradict", "neutral") else "neutral",
            study_design=s.get("study_design"),
            sample_size=s.get("sample_size"),
            pub_date=s.get("pub_date"),
            source_credibility=s.get("source_credibility"),
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/" if "pmid" in s else None,
        ))

    return evidence_snippets


if __name__ == "__main__":
    claim = "vitamin D supplements prevent respiratory infections"
    evidence = get_evidence_for_claim(claim, retmax=5)

    print(f"Got {len(evidence)} evidence snippets for: '{claim}'\n")
    for e in evidence:
        print(f"[{e.id}] stance={e.stance} | design={e.study_design} | credibility={e.source_credibility}")
        print(f"  {e.text[:100]}...\n")