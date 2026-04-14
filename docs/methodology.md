# Classification Methodology

## Overview

This pipeline classifies Reddit posts about AI's societal and psychological impact using a two-pass LLM classification system. Even though AI supported this process at various stages, I, a human, developed the taxonomy of themes based on a close reading of 100 of the most highly rated reddit posts. Based on themes I identified, I developed a list of thematic questions, which informed an LLM based classification schema. This project is narrow in scope and suffers from selection bias. However, I believe it's still worthwhile. The goal of this project is to systematically code public discourse across five subreddit communities to understand how AI is disintermediating human relations, how humans feel about the way AI is impacting their personal lives and society at large, and in some cases, what they propose should be done about it.
## Data

- **Source:** Reddit public JSON endpoints (no API key required)
- **Subreddits:** r/ChatGPT, r/teachers, r/singularity, r/replika, r/ExperiencedDevs
- **Corpus size:** 2,437 posts scraped March 2026
- **Preprocessing:** HTML/markdown stripping, PII scrubbing, language detection, SimHash deduplication

## Pass 1: Theme Classification

Each post is classified against 17 binary thematic questions (Q1–Q17). A theme is marked "present" only if the post substantively engages with it — passing mentions don't count. Posts can trigger multiple themes.

**Model:** google/gemini-3-flash-preview via OpenRouter  
**Temperature:** 0.0 (deterministic)  
**Output:** Structured JSON with per-theme presence flags and sub-fields (valence, disposition, direction, etc.)

### Themes

| Code | Theme | Sub-fields |
|------|-------|------------|
| Q1 | Existential reflection | valence (positive/negative/mixed) |
| Q2 | Future confidence | direction (more/less confident/mixed) |
| Q3 | Parasocial attachment | disposition (favorable/negative/mixed) |
| Q4 | Problematic engagement | engagement_patterns, addiction |
| Q5 | Anthropomorphization | disposition (favorable/negative/mixed) |
| Q6 | Vulnerable populations | company_responsibility_mentioned |
| Q7 | Model change harm | user_proposes_remedy |
| Q8 | Human relationships | avoidance, loneliness, adjudication, adjudication_norms_proposed |
| Q9 | Judgment substitution | — |
| Q10 | Cognitive offloading | learning_impact, cheating |
| Q11 | Data provenance & trust | solutions_proposed |
| Q12 | Usage norms | acceptability_discussed, actor_specific_norms |
| Q13 | AI validation | unreasonable_validation |
| Q14 | Ease of access | friction_view |
| Q15 | Pace of change | emotional_reaction |
| Q16 | Informational ecosystem | direction (helpful/polluting/mixed) |
| Q17 | Disintermediation | mechanism_described |

Each classification also includes metadata: `themes_detected_count`, `confidence` (high/medium/low), `ambiguous_themes`, and `pass2_needed`.

## Pass 2: Extraction

Posts flagged by Pass 1 with specific sub-fields undergo a second LLM call to extract short free-text summaries of what users propose or describe.

**Triggers and extraction targets:**

| Pass 1 flag | Extraction field |
|-------------|-----------------|
| Q6: company_responsibility_mentioned | What responsibilities users say AI companies have |
| Q7: user_proposes_remedy | What users think should be done about model changes |
| Q8: adjudication_norms_proposed | Proposed norms for AI in decision-making |
| Q11: solutions_proposed | Suggested solutions for provenance/trust issues |
| Q17: mechanism_described | Specific mechanisms of AI disintermediation |

## Results

- **2,434 / 2,437** posts classified (99.9%)
- **598 / 603** Pass 2 extractions completed (99.2%)
- **97.7%** high-confidence classifications
- **3.7** average themes per post

## Infrastructure

- **Database:** PostgreSQL with JSONB storage for classifications and extractions
- **Checkpointing:** Database-based — scripts can be interrupted and restarted without re-processing
- **Dashboard:** Static HTML viewer generated from database export (`docs/dashboard.html`)

## Prompt

The full classifier prompt with theme definitions and decision rules is in `docs/classifier_prompt.md`. The extraction prompt is in `docs/extraction_prompt.md`.
