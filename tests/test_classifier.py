"""Tests for the classifier module (unit tests that don't hit the API)."""

from src.models import (
    ClassificationMeta,
    ClassificationResult,
    Classifications,
    Q01ExistentialReflection,
    Q02FutureConfidence,
    Q03ParasocialAttachment,
    Q04ProblematicEngagement,
    Q05Anthropomorphization,
    Q06VulnerablePopulations,
    Q07ModelChangeHarm,
    Q08HumanRelationships,
    Q09JudgmentSubstitution,
    Q10CognitiveOffloading,
    Q11DataProvenanceTrust,
    Q12UsageNorms,
    Q13AiValidation,
    Q14EaseOfAccess,
    Q15PaceOfChange,
    Q16InformationalEcosystem,
    Q17Disintermediation,
)


def _make_all_absent_classifications() -> Classifications:
    """Return a Classifications object with all themes absent."""
    return Classifications(
        q01_existential_reflection=Q01ExistentialReflection(present=False, valence=None),
        q02_future_confidence=Q02FutureConfidence(present=False, direction=None),
        q03_parasocial_attachment=Q03ParasocialAttachment(present=False, disposition=None),
        q04_problematic_engagement=Q04ProblematicEngagement(
            present=False, engagement_patterns=None, addiction=None
        ),
        q05_anthropomorphization=Q05Anthropomorphization(present=False, disposition=None),
        q06_vulnerable_populations=Q06VulnerablePopulations(
            present=False, company_responsibility_mentioned=None
        ),
        q07_model_change_harm=Q07ModelChangeHarm(present=False, user_proposes_remedy=None),
        q08_human_relationships=Q08HumanRelationships(
            present=False,
            avoidance=None,
            loneliness=None,
            adjudication=None,
            adjudication_norms_proposed=None,
        ),
        q09_judgment_substitution=Q09JudgmentSubstitution(present=False),
        q10_cognitive_offloading=Q10CognitiveOffloading(
            present=False, learning_impact=None, cheating=None
        ),
        q11_data_provenance_trust=Q11DataProvenanceTrust(present=False, solutions_proposed=None),
        q12_usage_norms=Q12UsageNorms(
            present=False, acceptability_discussed=None, actor_specific_norms=None
        ),
        q13_ai_validation=Q13AiValidation(present=False, unreasonable_validation=None),
        q14_ease_of_access=Q14EaseOfAccess(present=False, friction_view=None),
        q15_pace_of_change=Q15PaceOfChange(present=False, emotional_reaction=None),
        q16_informational_ecosystem=Q16InformationalEcosystem(present=False, direction=None),
        q17_disintermediation=Q17Disintermediation(present=False, mechanism_described=None),
    )


class TestClassificationResult:
    def test_valid_result_all_absent(self):
        result = ClassificationResult(
            post_id="abc123",
            subreddit="ChatGPT",
            classifications=_make_all_absent_classifications(),
            meta=ClassificationMeta(
                themes_detected_count=0,
                confidence="high",
                ambiguous_themes=[],
                pass2_needed=False,
            ),
        )
        assert result.meta.themes_detected_count == 0
        assert result.classifications.q01_existential_reflection.present is False

    def test_valid_result_with_present_themes(self):
        clsf = _make_all_absent_classifications()
        clsf.q01_existential_reflection = Q01ExistentialReflection(
            present=True, valence="negative"
        )
        clsf.q04_problematic_engagement = Q04ProblematicEngagement(
            present=True, engagement_patterns=True, addiction=False
        )
        result = ClassificationResult(
            post_id="xyz789",
            subreddit="replika",
            classifications=clsf,
            meta=ClassificationMeta(
                themes_detected_count=2,
                confidence="medium",
                ambiguous_themes=["q04_problematic_engagement"],
                pass2_needed=False,
            ),
        )
        assert result.classifications.q01_existential_reflection.valence == "negative"
        assert result.classifications.q04_problematic_engagement.engagement_patterns is True
        assert result.meta.themes_detected_count == 2

    def test_roundtrip_from_dict(self):
        """Validate that model_validate handles a raw LLM JSON response correctly."""
        raw = {
            "post_id": "t3_abc",
            "subreddit": "teachers",
            "classifications": {
                "q01_existential_reflection": {"present": True, "valence": "mixed"},
                "q02_future_confidence": {"present": False, "direction": None},
                "q03_parasocial_attachment": {"present": False, "disposition": None},
                "q04_problematic_engagement": {
                    "present": False,
                    "engagement_patterns": None,
                    "addiction": None,
                },
                "q05_anthropomorphization": {"present": False, "disposition": None},
                "q06_vulnerable_populations": {
                    "present": True,
                    "company_responsibility_mentioned": False,
                },
                "q07_model_change_harm": {"present": False, "user_proposes_remedy": None},
                "q08_human_relationships": {
                    "present": False,
                    "avoidance": None,
                    "loneliness": None,
                    "adjudication": None,
                    "adjudication_norms_proposed": None,
                },
                "q09_judgment_substitution": {"present": False},
                "q10_cognitive_offloading": {
                    "present": True,
                    "learning_impact": True,
                    "cheating": True,
                },
                "q11_data_provenance_trust": {"present": False, "solutions_proposed": None},
                "q12_usage_norms": {
                    "present": True,
                    "acceptability_discussed": True,
                    "actor_specific_norms": True,
                },
                "q13_ai_validation": {"present": False, "unreasonable_validation": None},
                "q14_ease_of_access": {"present": False, "friction_view": None},
                "q15_pace_of_change": {"present": False, "emotional_reaction": None},
                "q16_informational_ecosystem": {"present": False, "direction": None},
                "q17_disintermediation": {"present": False, "mechanism_described": None},
            },
            "meta": {
                "themes_detected_count": 4,
                "confidence": "high",
                "ambiguous_themes": [],
                "pass2_needed": False,
            },
        }
        result = ClassificationResult.model_validate(raw)
        assert result.classifications.q01_existential_reflection.valence == "mixed"
        assert result.classifications.q10_cognitive_offloading.cheating is True
        assert result.meta.themes_detected_count == 4

    def test_invalid_valence_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            Q01ExistentialReflection(present=True, valence="uncertain")

    def test_invalid_confidence_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            ClassificationMeta(
                themes_detected_count=0,
                confidence="very_high",
                ambiguous_themes=[],
                pass2_needed=False,
            )


class TestPromptLoading:
    def test_prompt_loads_without_error(self):
        from src.classifier import SYSTEM_PROMPT, USER_TEMPLATE

        assert "THEME DEFINITIONS" in SYSTEM_PROMPT
        assert "{{subreddit}}" in USER_TEMPLATE
        assert "{{post_id}}" in USER_TEMPLATE
        assert "{{title}}" in USER_TEMPLATE
        assert "{{body}}" in USER_TEMPLATE
