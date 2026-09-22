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

For each snippet, classify ONLY the evidence contained in that snippet.

Labels:

- "support" — the snippet provides evidence that directly supports the claim.
- "contradict" — the snippet provides evidence that directly contradicts the claim.
- "neutral" — the snippet is not directly about the claim, does not provide enough evidence, or discusses a different outcome.

CRITICAL RULE:

The claim has TWO essential parts:
1. Intervention: vitamin D supplementation
2. Outcome: prevention/reduction of respiratory infections

A snippet must address BOTH parts to be "support" or "contradict".

If the snippet discusses vitamin D but the outcome is something else, classify it as "neutral".

Examples of outcomes that are NOT the target outcome:
- hypercalcaemia
- falls
- osteoporosis
- mortality
- rickets
- COVID-19
- safety/adverse effects
- vitamin D levels
- other diseases or conditions

For example:
"Vitamin D supplementation has little to no effect on hypercalcaemia"
→ neutral

"Vitamin D supplementation reduces respiratory infections"
→ support

"Vitamin D supplementation has little or no effect on respiratory infections"
→ contradict

Other rules:

1. Merely mentioning vitamin D supplementation is NOT enough.
2. Merely mentioning respiratory infections is NOT enough.
3. Background information is neutral.
4. Study methodology is neutral.
5. Participant descriptions are neutral.
6. Judge ONLY the snippet itself.
7. Do not infer the overall conclusion of the paper.
8. Do not use information from other snippets.
9. If the snippet reports no statistically significant effect on respiratory infections, classify it as contradict only when the result directly tests vitamin D supplementation against the respiratory-infection outcome.
10. If the snippet is ambiguous or lacks enough information to determine the relationship between vitamin D supplementation and respiratory infections, classify it as neutral.

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
    from pubmed_search import search_pubmed
    from pubmed_fetch import fetch_abstracts
    from snippet_chunker import chunk_abstract
    from quality_extractor import enrich_snippet

    test_claim = "vitamin D supplements prevent respiratory infections"
    claim_keywords = ["vitamin D", "25(OH)D", "cholecalciferol", "25-hydroxyvitamin"]
    ids = search_pubmed(test_claim, retmax=10)
    papers = fetch_abstracts(ids)

    # Filter out clearly irrelevant papers before spending tokens on them
    relevant_papers = [
        p for p in papers
        if is_relevant(p)
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