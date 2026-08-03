from pathlib import Path
import unittest
from unittest.mock import patch

from ani_watch_core import (
    AnimeResult,
    build_ani_cli_command,
    extract_selected_link,
    fetch_episodes,
    search_anime,
)


class AniCliCoreTests(unittest.TestCase):
    @patch("ani_watch_core._request_text")
    def test_search_preserves_upstream_result_index(self, request):
        request.return_value = """
            <a href="/anime/naruto-3686"><img alt="Naruto"></a>
            <a href="/anime/naruto-shippuden-3687"><img alt="Naruto &amp; Friends"></a>
        """
        results = search_anime("naruto")
        self.assertEqual(results[0], AnimeResult(1, "naruto-3686", "Naruto"))
        self.assertEqual(results[1].title, "Naruto & Friends")

    @patch("ani_watch_core._request_text")
    def test_fetch_episodes_reads_json(self, request):
        request.return_value = (
            '{"episodes":[{"id":1,"number":1,"filler":false},'
            '{"id":2,"number":2.5,"filler":true}]}'
        )
        episodes = fetch_episodes("example-99")
        self.assertEqual([episode.number for episode in episodes], ["1", "2.5"])
        self.assertTrue(episodes[1].filler)

    def test_build_command_uses_non_interactive_selection(self):
        command = build_ani_cli_command(
            Path("/tmp/ani-cli"),
            "one piece",
            3,
            "12",
            "720p",
            dubbed=True,
            player="vlc",
            download=True,
        )
        self.assertEqual(command[:3], ["/tmp/ani-cli", "one piece", "--select-nth"])
        self.assertIn("--episode", command)
        self.assertIn("--dub", command)
        self.assertIn("--vlc", command)
        self.assertIn("--download", command)

    def test_extract_selected_link_ignores_terminal_colors(self):
        output = (
            "\x1b[1;34manidb.app links fetched\x1b[0m\n"
            "All links:\n720p >https://example.test/720.m3u8\n"
            "Selected link:\nhttps://example.test/video.m3u8\n"
        )
        self.assertEqual(
            extract_selected_link(output), "https://example.test/video.m3u8"
        )


if __name__ == "__main__":
    unittest.main()
