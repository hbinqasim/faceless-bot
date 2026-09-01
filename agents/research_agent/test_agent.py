"""Tests for research article cleanup."""

from __future__ import annotations

import unittest

from agents.research_agent.agent import trim_article_boilerplate


class ResearchCleanupTests(unittest.TestCase):
    def test_reader_prompt_and_related_stories_are_removed(self) -> None:
        text = (
            "The publisher confirmed that premium pre-orders exceeded expectations. "
            "The standard edition costs less than the premium edition. "
            "Will you be buying the premium edition? Leave your thoughts in the comments. "
            "Sonic confirms an unrelated crossover."
        )

        cleaned = trim_article_boilerplate(text)

        self.assertIn("premium pre-orders", cleaned)
        self.assertNotIn("Will you be buying", cleaned)
        self.assertNotIn("Sonic", cleaned)


if __name__ == "__main__":
    unittest.main()
