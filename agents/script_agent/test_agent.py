"""Tests for script cleanup and deterministic fallbacks."""

from __future__ import annotations

import unittest

from agents.script_agent.agent import fallback_script, has_spacing_damage, source_material_sentences


class FallbackScriptTests(unittest.TestCase):
    def test_normal_prose_with_multiple_articles_is_not_spacing_damage(self) -> None:
        line = "The company revealed a date for a new gameplay video after weeks of silence."
        self.assertFalse(has_spacing_damage(line))

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

    def test_extracted_claims_are_used_but_editorial_angles_are_not_spoken(self) -> None:
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
        self.assertNotIn("October", script)
        self.assertNotIn("The change matters", script)
        self.assertNotIn("cus to mers", script)

    def test_longform_fallback_excludes_site_boilerplate_and_reader_prompts(self) -> None:
        knowledge = {
            "title": "A verified gaming update",
            "summary": "A detailed report describes changes affecting current players.",
            "claims": [
                {"claim": "Release date, map, characters, gameplay and more, updated regularly."},
            ],
            "article_text": " ".join(
                [
                    "Release date, map, characters, gameplay and more, updated regularly.",
                    "The publisher described a specific change affecting current players today.",
                    "Are you worried about what this update means for the next release?",
                ]
                * 12
            ),
            "avoid": [],
        }
        config = {
            "cta": "Subscribe for more GTA 6 news and analysis.",
            "max_words_per_line": 22,
            "max_lines": 22,
            "target_min_words": 40,
            "excluded_script_fragments": [],
        }

        script = fallback_script(knowledge, config)

        self.assertNotIn("updated regularly", script.lower())
        self.assertNotIn("are you worried", script.lower())
        self.assertIn("specific change", script.lower())

    def test_source_material_stops_before_affiliate_and_reader_prompts(self) -> None:
        knowledge = {
            "article_text": (
                "Rockstar announced a detailed gameplay preview for August 27. "
                "The program will appear on Netflix before YouTube. "
                "Will you be watching on Netflix or not? "
                "You can pre-order your copy with this link."
            )
        }

        sentences = source_material_sentences(knowledge)
        joined = " ".join(sentences)

        self.assertIn("Netflix before YouTube", joined)
        self.assertNotIn("Will you", joined)
        self.assertNotIn("pre-order your copy", joined)


if __name__ == "__main__":
    unittest.main()
