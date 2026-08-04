"""Tests for script cleanup and deterministic fallbacks."""

from __future__ import annotations

import unittest

from agents.script_agent.agent import fallback_script


class FallbackScriptTests(unittest.TestCase):
    def test_longform_fallback_uses_verified_article_without_promotions(self) -> None:
        sentences = [
            f"Verified update number {index} explains the gameplay change and its practical effect for players today."
            for index in range(1, 25)
        ]
        sentences.insert(5, "Enter with your email to join our giveaway today.")
        sentences.insert(6, "One entry per person.")
        sentences.extend(
            [
                "Per 3 established Helpful marks this begins the appended comment section.",
                "This reader comment must never become verified narration content.",
            ]
        )
        knowledge = {
            "title": "A verified gaming update",
            "summary": "The update changes several parts of the game for current players.",
            "article_text": " ".join(sentences),
            "avoid": [],
        }
        config = {
            "cta": "Subscribe for more GTA 6 news and analysis.",
            "max_words_per_line": 22,
            "max_lines": 22,
            "target_min_words": 250,
            "excluded_script_fragments": [],
        }

        script = fallback_script(knowledge, config)

        self.assertGreaterEqual(len(script.split()), 250)
        self.assertLessEqual(len(script.splitlines()), 22)
        self.assertNotIn("giveaway", script.lower())
        self.assertNotIn("one entry", script.lower())
        self.assertNotIn("reader comment", script.lower())
        self.assertTrue(script.endswith(config["cta"]))

    def test_shortform_fallback_does_not_expand_from_article(self) -> None:
        knowledge = {
            "title": "A verified gaming update",
            "summary": "The update changes the game for players today.",
            "article_text": "This source sentence should not enter a short script.",
        }
        config = {
            "cta": "Follow for more GTA 6 breakdowns.",
            "max_words_per_line": 12,
            "max_lines": 7,
        }

        script = fallback_script(knowledge, config)

        self.assertNotIn("source sentence", script.lower())

    def test_extracted_claims_are_used_and_broken_words_are_repaired(self) -> None:
        knowledge = {
            "title": "A verified gaming update",
            "summary": "The report describes a new update for current players.",
            "claims": [{"claim": "The update could benefit cus to mers", "status": "reported"}],
            "script_angles": ["The change matters in Oc to ber"],
            "article_text": "The title has a long his to ry among players.",
        }
        config = {
            "cta": "Subscribe for more GTA 6 news and analysis.",
            "max_words_per_line": 34,
            "max_lines": 22,
            "target_min_words": 40,
            "excluded_script_fragments": [],
        }

        script = fallback_script(knowledge, config)

        self.assertIn("customers", script)
        self.assertIn("October", script)
        self.assertNotIn("cus to mers", script)


if __name__ == "__main__":
    unittest.main()
