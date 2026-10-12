"""
Step 6: Consolidation — the single entry point for the rest of the system.

Given a health claim, this runs the full evidence pipeline internally:
analyse claim → search → fetch → filter → chunk → quality metadata → stance
and returns a clean list of EvidenceSnippet objects matching the shared schema.

Two entry points:
- get_evidence_with_analysis(claim) -> (ClaimAnalysis, list[EvidenceSnippet])   # used by the API
- get_evidence_for_claim(claim)     -> list[EvidenceSnippet]                     # unchanged signature

Run the test from the backend/ folder:
    python -m app.retrieval.evidence_pipeline
"""

import re
from typing import Callable, Optional

from app.core.schemas import ClaimAnalysis, EvidenceSnippet
from app.retrieval.claim_analyzer import analyze_claim
from app.retrieval.pubmed_search import search_pubmed
from app.retrieval.pubmed_fetch import fetch_abstracts
from app.retrieval.snippet_chunker import chunk_abstract
from app.retrieval.quality_extractor import enrich_snippet
from app.retrieval.stance_classifier import classify_snippets_stance

HUMAN_FILTER = " AND humans[mh]"


def extract_claim_keywords(claim: str) -> tuple[list[str], list[str]]:
    """
    FALLBACK ONLY (used if the claim analyzer fails).
    Splits the claim into two keyword groups — roughly 'subject/intervention'
    (first half) and 'outcome' (second half).
    """
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
    at least one match from outcome terms. Uses stem matching (term minus a
    trailing 's') to handle singular/plural mismatches.
    """
    text = (paper["title"] + " " + paper["abstract"]).lower()

    def stem_match(term: str, text: str) -> bool:
        stem = term.rstrip("s")
        return bool(stem) and stem in text

    has_subject = any(stem_match(term, text) for term in subject_terms)
    has_outcome = any(stem_match(term, text) for term in outcome_terms)
    return has_subject and has_outcome


def _build_analysis(claim: str) -> ClaimAnalysis:
    analysis = analyze_claim(claim)
    if analysis and analysis.intervention_terms and analysis.outcome_terms:
        return analysis

    subject_terms, outcome_terms = extract_claim_keywords(claim)
    return ClaimAnalysis(
        original_claim=claim,
        checkable_claim=claim,
        pubmed_query=claim,
        intervention_terms=subject_terms,
        outcome_terms=outcome_terms,
        analysis_fallback=True,
    )


def _search_with_fallbacks(analysis: ClaimAnalysis, retmax: int) -> tuple[str, list[str]]:
    """Try the most precise query first, then progressively looser ones."""
    queries = [f"({analysis.pubmed_query}){HUMAN_FILTER}", analysis.pubmed_query, analysis.original_claim]

    for q in dict.fromkeys(queries):  # de-duplicate, keep order
        ids = search_pubmed(q, retmax=retmax)
        if ids:
            return q, ids
    return queries[-1], []


ProgressFn = Callable[[str, float], None]


def get_evidence_with_analysis(
    claim: str, retmax: int = 8, on_progress: Optional[ProgressFn] = None,
) -> tuple[ClaimAnalysis, list[EvidenceSnippet]]:
    """on_progress(message, fraction) is called at each step (fractions 0.05-0.50 of the full run)."""
    report = on_progress or (lambda message, fraction: None)

    report("Understanding your claim...", 0.05)
    analysis = _build_analysis(claim)

    report("Searching PubMed for relevant studies...", 0.15)
    query_used, ids = _search_with_fallbacks(analysis, retmax)
    analysis.search_query_used = query_used
    if not ids:
        report("No studies found on PubMed for this claim.", 0.50)
        return analysis, []

    report(f"Found {len(ids)} studies - reading the abstracts...", 0.22)
    papers = fetch_abstracts(ids)
    relevant_papers = [
        p for p in papers
        if is_relevant(p, analysis.intervention_terms, analysis.outcome_terms)
    ]
    report(f"{len(relevant_papers)} of {len(papers)} studies look relevant to the claim.", 0.28)

    all_snippets = []
    for i, paper in enumerate(relevant_papers, start=1):
        report(f"Checking study {i} of {len(relevant_papers)} against the claim...",
               0.28 + 0.22 * (i - 1) / max(len(relevant_papers), 1))
        snippets = chunk_abstract(paper)
        pubmed_types = paper.get("pubmed_types", [])
        snippets = [enrich_snippet(s, pubmed_types) for s in snippets]
        # Stance is judged against the checkable version of the claim
        snippets = classify_snippets_stance(analysis.checkable_claim, snippets)
        all_snippets.extend(snippets)

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

    return analysis, evidence_snippets


def get_evidence_for_claim(claim: str, retmax: int = 8) -> list[EvidenceSnippet]:
    """Unchanged signature (used by the baseline and evaluation)."""
    return get_evidence_with_analysis(claim, retmax)[1]


if __name__ == "__main__":
    claim = "Vitamin D is present in the sun during entire day"
    analysis, evidence = get_evidence_with_analysis(claim, retmax=8)

    print(f"Checkable claim: {analysis.checkable_claim}")
    print(f"Query used:      {analysis.search_query_used}")
    print(f"Fallback used:   {analysis.analysis_fallback}\n")
    print(f"Got {len(evidence)} evidence snippets\n")
    for e in evidence:
        print(f"[{e.id}] stance={e.stance} | design={e.study_design} | credibility={e.source_credibility}")
        print(f"  {e.text[:100]}...\n")