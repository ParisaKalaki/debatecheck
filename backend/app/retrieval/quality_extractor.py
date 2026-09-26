"""
Step 4: Extract quality metadata for each snippet.

Primary method: use PubMed's own official PublicationType metadata
(authoritative, curated by journal/NLM indexers).

Fallback method: regex pattern matching on the snippet text itself,
used only when PubMed didn't provide a usable PublicationType.
"""

import re


STUDY_DESIGN_PATTERNS = [
    (r"\brandomized controlled (?:pilot )?trial\b|\bRCT\b|\brandomised controlled (?:pilot )?trial\b", "RCT"),
    (r"\bsystematic review\b", "systematic_review"),
    (r"\bmeta-analysis\b", "meta_analysis"),
    (r"\bcohort study\b|\bprospective cohort\b|\bretrospective cohort\b", "cohort_study"),
    (r"\bcase report\b|\bcase series\b", "case_report"),
    (r"\bobservational study\b|\bcross-sectional\b", "observational"),
    (r"\bpilot trial\b|\bpilot study\b", "pilot_trial"),
    (r"\bnarrative review\b", "narrative_review"),
]

PUBMED_TYPE_MAPPING = {
    "Randomized Controlled Trial": "RCT",
    "Systematic Review": "systematic_review",
    "Meta-Analysis": "meta_analysis",
    "Observational Study": "observational",
    "Case Reports": "case_report",
    "Review": "narrative_review",
    "Clinical Trial": "clinical_trial",
}


def map_pubmed_type_to_design(pubmed_types: list[str]) -> str | None:
    """Authoritative: use PubMed's own curated PublicationType field."""
    for pt in pubmed_types:
        if pt in PUBMED_TYPE_MAPPING:
            return PUBMED_TYPE_MAPPING[pt]
    return None


def extract_study_design_from_text(text: str) -> str | None:
    """Fallback: guess study design from the snippet text using regex."""
    quality_rank = ["systematic_review", "meta_analysis", "RCT", "cohort_study",
                     "pilot_trial", "observational", "narrative_review", "case_report"]

    matches = []
    for pattern, label in STUDY_DESIGN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(label)

    if not matches:
        return None

    for label in quality_rank:
        if label in matches:
            return label
    return matches[0]


def extract_sample_size(text: str) -> int | None:
    patterns = [
        r"\benroll(?:ed|ing)?\s+(\d+)\s+(?:healthy\s+)?(?:adults|participants|patients|subjects)",
        r"\bn\s*=\s*(\d+)",
        r"\b(\d+)\s+participants\b",
        r"\b(\d+)\s+patients\b",
        r"\b(\d+)\s+subjects\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def estimate_source_credibility(study_design: str | None) -> str:
    high = {"systematic_review", "meta_analysis", "RCT"}
    medium = {"cohort_study", "observational", "pilot_trial", "clinical_trial"}
    low = {"case_report", "narrative_review"}

    if study_design in high:
        return "high"
    elif study_design in medium:
        return "medium"
    elif study_design in low:
        return "low"
    return "unknown"


def enrich_snippet(snippet: dict, pubmed_types: list[str] = None) -> dict:
    """
    Fill in study_design, sample_size, source_credibility for one snippet.
    Tries PubMed's official metadata first, falls back to text-based guessing.
    """
    study_design = None
    if pubmed_types:
        study_design = map_pubmed_type_to_design(pubmed_types)

    if not study_design:
        study_design = extract_study_design_from_text(snippet["text"])

    sample_size = extract_sample_size(snippet["text"])
    credibility = estimate_source_credibility(study_design)

    snippet["study_design"] = study_design
    snippet["sample_size"] = sample_size
    snippet["source_credibility"] = credibility
    return snippet


if __name__ == "__main__":
    from app.retrieval.pubmed_search import search_pubmed
    from app.retrieval.pubmed_fetch import fetch_abstracts
    from app.retrieval.snippet_chunker import chunk_abstract

    test_claim = "intermittent fasting longevity"
    ids = search_pubmed(test_claim, retmax=2)
    papers = fetch_abstracts(ids)

    for paper in papers:
        snippets = chunk_abstract(paper)
        pubmed_types = paper.get("pubmed_types", [])
        enriched = [enrich_snippet(s, pubmed_types) for s in snippets]

        for s in enriched:
            print(f"[{s['id']}] design={s['study_design']} | n={s['sample_size']} | credibility={s['source_credibility']}")
            print(f"  {s['text'][:120]}...\n")