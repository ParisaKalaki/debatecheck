"""
Step 5: Classify each snippet's stance toward the claim (support/contradict/neutral).

Uses one Gemini API call per paper (not per snippet) to keep costs down.
Uses the new google-genai SDK (the old google-generativeai package is deprecated).
"""

import os
import json
from pathlib import Path
from google import genai
from dotenv import load_dotenv

# Load .env from the project root, regardless of where this script is run from
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=env_path)


client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


STANCE_PROMPT_TEMPLATE = """You are classifying evidence snippets from medical research abstracts against a health claim.

CLAIM: "{claim}"

STEP 1 - Identify the two essential parts of the claim:
1. Intervention/exposure (what is done, taken, or consumed)
2. Outcome (the health effect the claim is about)

STEP 2 - Classify each snippet using ONLY the evidence it contains.

Labels:
- "support": the snippet provides evidence that the claim is true.
- "contradict": the snippet provides evidence that the claim is false (e.g. no effect, no significant difference, or the opposite effect).
- "neutral": anything else.

CRITICAL RULE:
A snippet must address BOTH the claim's intervention AND its outcome to be "support" or "contradict".
If it discusses the intervention but a different outcome (e.g. safety, side effects, biomarker levels, a different disease),
or the outcome but a different intervention, classify it as "neutral".

Other rules:
1. Background information, study methodology, and participant descriptions are neutral.
2. Judge ONLY the snippet itself. Do not infer the paper's overall conclusion or use other snippets.
3. "No statistically significant effect" counts as "contradict" only if the snippet directly tests the claim's intervention against the claim's outcome.
4. If the snippet is ambiguous or lacks enough information, classify it as neutral.

Snippets:
{snippets_text}

Respond ONLY with a valid JSON array, no markdown and no explanation.

[{{"id": "snippet_id_here", "stance": "support"}}, {{"id": "snippet_id_here", "stance": "neutral"}}]
"""


def is_relevant(paper: dict, claim_keywords: list[str]) -> bool:
    """Cheap relevance check — does the abstract mention claim-related keywords?"""
    text = (paper["title"] + " " + paper["abstract"]).lower()
    matches = [kw for kw in claim_keywords if kw.lower() in text]
    return len(matches) >= 1  # at least one keyword must appear


def classify_snippets_stance(claim: str, snippets: list[dict]) -> list[dict]:
    if not snippets:
        return snippets

    snippets_text = "\n".join(f"[{s['id']}] {s['text']}" for s in snippets)
    prompt = STANCE_PROMPT_TEMPLATE.format(claim=claim, snippets_text=snippets_text)

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )
    raw_text = response.text.strip()

    raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        stance_results = json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"WARNING: could not parse Gemini response as JSON:\n{raw_text}")
        return snippets

    stance_map = {r["id"]: r["stance"] for r in stance_results}

    for snippet in snippets:
        snippet["stance"] = stance_map.get(snippet["id"], "neutral")

    return snippets


if __name__ == "__main__":
    # Run from the backend/ folder: python -m app.retrieval.stance_classifier
    from app.retrieval.pubmed_search import search_pubmed
    from app.retrieval.pubmed_fetch import fetch_abstracts
    from app.retrieval.snippet_chunker import chunk_abstract
    from app.retrieval.quality_extractor import enrich_snippet

    test_claim = "vitamin D supplements prevent respiratory infections"
    claim_keywords = ["vitamin D", "25(OH)D", "cholecalciferol", "25-hydroxyvitamin"]
    ids = search_pubmed(test_claim, retmax=10)
    papers = fetch_abstracts(ids)

    # Filter out clearly irrelevant papers before spending tokens on them
    relevant_papers = [
        p for p in papers
        if is_relevant(p, claim_keywords)
    ]
    print(
        f"Retrieved {len(papers)} papers, "
        f"kept {len(relevant_papers)} relevant papers"
    )

    all_snippets = []
    for paper in relevant_papers:
        snippets = chunk_abstract(paper)
        pubmed_types = paper.get("pubmed_types", [])
        snippets = [enrich_snippet(s, pubmed_types) for s in snippets]
        snippets = classify_snippets_stance(test_claim, snippets)
        all_snippets.extend(snippets)

    for s in all_snippets:
        print(f"[{s['id']}] stance={s['stance']} | design={s['study_design']} | credibility={s['source_credibility']}")
        print(f"  {s['text'][:120]}...\n")