import unittest
from unittest.mock import patch

from entigram.cli_runner.runner import launch_agent


class TestCodexRunner(unittest.TestCase):
    def test_codex_uses_native_initial_prompt(self):
        prompt = "\x1b[200~Initialize from .etg/boot.json. Silent boot. Ready.\x1b[201~"

        with patch("platform.system", return_value="Darwin"):
            with patch("subprocess.run") as run:
                success, message = launch_agent(
                    ".",
                    "Codex",
                    yolo=True,
                    initial_prompt=prompt,
                    model="gpt-5",
                )

        self.assertTrue(success)
        self.assertEqual(message, "Launched Codex with native initial prompt.")
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertEqual(args[:2], ["osascript", "-e"])
        self.assertIn("codex --model gpt-5 --ask-for-approval never", args[2])
        self.assertIn("Initialize from .etg/boot.json. Silent boot. Ready.", args[2])
        self.assertNotIn("\x1b[200~", args[2])
        self.assertNotIn("\x1b[201~", args[2])
        self.assertNotIn("^[[200~", args[2])
        self.assertNotIn("^[[201~", args[2])
        self.assertNotIn("/usr/bin/expect", args[2])


if __name__ == "__main__":
    unittest.main()
