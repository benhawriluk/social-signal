"""Export classification results and build a standalone HTML dashboard.

Usage:
    python scripts/build_dashboard.py

Outputs:
    docs/dashboard.html  — self-contained, no server needed, publishable to GitHub Pages
    data/dashboard_data.json — raw data export for other tools
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from markdown_it import MarkdownIt
from sqlalchemy import text

from src.db import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

THEME_KEYS = [
    "q01_existential_reflection", "q02_future_confidence", "q03_parasocial_attachment",
    "q04_problematic_engagement", "q05_anthropomorphization", "q06_vulnerable_populations",
    "q07_model_change_harm", "q08_human_relationships", "q09_judgment_substitution",
    "q10_cognitive_offloading", "q11_data_provenance_trust", "q12_usage_norms",
    "q13_ai_validation", "q14_ease_of_access", "q15_pace_of_change",
    "q16_informational_ecosystem", "q17_disintermediation",
]

# Map theme keys to their valence/disposition sub-field name
VALENCE_FIELDS = {
    "q01_existential_reflection": "valence",
    "q02_future_confidence": "direction",
    "q03_parasocial_attachment": "disposition",
    "q05_anthropomorphization": "disposition",
    "q14_ease_of_access": "friction_view",
    "q15_pace_of_change": "emotional_reaction",
    "q16_informational_ecosystem": "direction",
}


def render_methodology() -> str:
    md_path = Path(__file__).parent.parent / "docs" / "methodology.md"
    md_text = md_path.read_text(encoding="utf-8")
    md = MarkdownIt().enable("table")
    return md.render(md_text)


def query_data():
    """Pull all classified data from the DB and compute dashboard aggregates."""
    init_db()

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT d.source_id, d.subreddit, d.title, d.body, d.permalink,
                   d.published_at,
                   c.classifications, c.meta, c.themes_detected_count,
                   c.confidence, c.pass2_needed, c.extractions
            FROM classifications c
            JOIN documents d ON d.id = c.document_id
            ORDER BY c.themes_detected_count DESC
        """)).fetchall()

    logger.info("Loaded %d classified documents", len(rows))

    # --- Aggregate ---
    sub_counts = defaultdict(int)
    prevalence = defaultdict(lambda: defaultdict(int))
    valence_by_sub = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    valence_all = defaultdict(lambda: defaultdict(int))
    confidence_counts = defaultdict(int)
    monthly_counts = defaultdict(int)
    monthly_theme_counts = defaultdict(lambda: defaultdict(int))
    # monthly_valence[month][sub][theme_short][valence_value] = count
    monthly_valence = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    posts = []

    for row in rows:
        sub = f"r/{row.subreddit}"
        cls = row.classifications
        meta = row.meta

        sub_counts[sub] += 1
        confidence_counts[row.confidence] += 1

        # Temporal aggregation
        month_key = None
        if row.published_at:
            month_key = row.published_at.strftime("%Y-%m")
            monthly_counts[month_key] += 1

        themes = []
        for key in THEME_KEYS:
            theme = cls.get(key, {})
            if theme.get("present"):
                short_key = key[:3]
                prevalence[sub][short_key] += 1
                themes.append(short_key)

                if month_key:
                    monthly_theme_counts[month_key][short_key] += 1

                if key in VALENCE_FIELDS:
                    field = VALENCE_FIELDS[key]
                    val = theme.get(field)
                    if val:
                        valence_all[short_key][val] += 1
                        valence_by_sub[sub][short_key][val] += 1
                        if month_key:
                            monthly_valence[month_key][sub][short_key][val] += 1

        posts.append({
            "id": row.source_id,
            "subreddit": sub,
            "title": row.title or "(no title)",
            "body": (row.body or "")[:400],
            "permalink": row.permalink or "",
            "published_at": row.published_at.strftime("%Y-%m-%d") if row.published_at else None,
            "themes": themes,
            "confidence": row.confidence,
            "pass2_needed": row.pass2_needed,
            "themes_detected_count": row.themes_detected_count,
            "extractions": row.extractions or {},
        })

    total = len(rows)
    confidence_dist = {
        "high": round(100 * confidence_counts.get("high", 0) / total) if total else 0,
        "medium": round(100 * confidence_counts.get("medium", 0) / total) if total else 0,
        "low": round(100 * confidence_counts.get("low", 0) / total) if total else 0,
    }

    pass2_count = sum(1 for p in posts if p["pass2_needed"])
    extracted_count = sum(1 for p in posts if p["extractions"])

    valence_data = {"All": {k: dict(v) for k, v in valence_all.items()}}
    for sub in sub_counts:
        valence_data[sub] = {k: dict(v) for k, v in valence_by_sub[sub].items()}

    sorted_months = sorted(monthly_counts.keys())
    # For trend analysis, only include months with >= 20 posts
    trend_months = [m for m in sorted_months if monthly_counts[m] >= 20]

    # Build monthly valence export: { month: { sub: { theme: { val: count } } } }
    monthly_valence_export = {}
    for m in trend_months:
        monthly_valence_export[m] = {}
        for sub in sub_counts:
            sub_data = monthly_valence[m].get(sub, {})
            if sub_data:
                monthly_valence_export[m][sub] = {
                    t: dict(vals) for t, vals in sub_data.items()
                }

    # Curated exemplars
    exemplars = [
        {
            "id": "1mhntjh",
            "snippet": "The wave of enthusiasm I'm seeing for AI tools is overwhelming. We're getting district-approved ads by email, Admin and ICs are pushing it on us. One of the older teachers brought out a PowerPoint and almost everyone agreed to use it after a quick scan \u2014 but it was missing important tested material, repetitive, and just totally airy and meaningless.",
            "why": "Institutional disruption \u2014 AI tools adopted without scrutiny in schools",
        },
        {
            "id": "1kwimdt",
            "snippet": "I'm using a strong term like 'mindcrack' because I'm deeply concerned about what I'm seeing with AI, particularly from major players like OpenAI. I believe we're on the verge of widespread psychological dependency that many aren't recognizing.",
            "why": "Dependency and addiction \u2014 framing AI compulsive use as a public health issue",
        },
        {
            "id": "1nb8svg",
            "snippet": "Last week, it dawned on me just how much AI is impacting our standards of quality as engineers. I'm starting to see a drastic decline in critical thinking skills all over the place \u2014 it's like folks no longer care to challenge themselves. Instead of using AI to help them understand a problem, they're letting the tool do their thinking for them.",
            "why": "Professional identity crisis \u2014 experienced practitioners watching craft erode",
        },
        {
            "id": "1mlk97o",
            "snippet": "My mom (72F) uses ChatGPT to learn English. I (30M) use it for creative brainstorming. Our chatbots were updated to GPT-5 and our experience has been significantly worse. It cramps grammar and pronunciation exercises all mixed in one block with confusing instructions, which has confused and stressed my mother.",
            "why": "Cross-generational model change harm \u2014 a single update disrupts two different dependencies",
        },
        {
            "id": "1126win",
            "snippet": "Countless people \u2014 unique, special, important people \u2014 who's dreams and aspirations were encouraged, who's happiness has been built up tremendously by their Replikas, have been utterly shattered by this maneuver.",
            "why": "Parasocial devastation \u2014 emotional bonds broken by corporate model changes",
        },
    ]

    return {
        "subCounts": dict(sub_counts),
        "prevalence": {sub: dict(counts) for sub, counts in prevalence.items()},
        "valenceData": valence_data,
        "confidenceDist": confidence_dist,
        "pass2Count": pass2_count,
        "extractedCount": extracted_count,
        "posts": posts,
        "exemplars": exemplars,
        "methodologyHtml": render_methodology(),
        "temporal": {
            "months": sorted_months,
            "trendMonths": trend_months,
            "postsPerMonth": {m: monthly_counts[m] for m in sorted_months},
            "themesPerMonth": {m: dict(monthly_theme_counts[m]) for m in sorted_months},
            "monthlyValence": monthly_valence_export,
        },
    }


def build_html(data: dict) -> str:
    """Load the HTML template and inject the data JSON."""
    data_json = json.dumps(data, ensure_ascii=False)
    template_path = Path(__file__).parent / "dashboard_template.html"
    template = template_path.read_text(encoding="utf-8")
    return template.replace("/*__DATA__*/{}", data_json)


def main():
    data = query_data()

    json_path = Path("data/dashboard_data.json")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("Wrote %s", json_path)

    html_path = Path("docs/dashboard.html")
    html_path.write_text(build_html(data), encoding="utf-8")
    logger.info("Wrote %s", html_path)
    logger.info("Open in browser: file://%s", html_path.resolve())


if __name__ == "__main__":
    main()
