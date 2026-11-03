"""Generated cleanup must never remove saves, source art or QA reports."""

import contextlib
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tools import clean_generated as cleanup


class GeneratedCleanupTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.local = self.root / ".local"
        self.local.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def copy(self, name, saved=False):
        folder = self.local / name
        game = folder / "13Fri"
        for relative in ("launch_game.py", "runtime/python.exe", "templates/chat.html"):
            file = game / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"fixture")
        database = game / "data/train_state.sqlite3"
        database.parent.mkdir()
        with contextlib.closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("CREATE TABLE games (id TEXT)")
            if saved:
                connection.execute("INSERT INTO games VALUES ('keep-player-save')")
        return folder

    def test_copy_with_any_game_save_or_settings_is_protected(self):
        saved = self.copy("배포본 검수 1", saved=True)
        configured = self.copy("배포본 검수 2")
        (configured / "13Fri/.env.local").write_text("settings", encoding="utf-8")
        self.assertFalse(cleanup.disposable_copy(saved))
        self.assertFalse(cleanup.disposable_copy(configured))

    def test_targets_must_stay_below_local_and_cannot_be_local_itself(self):
        with patch.object(cleanup, "LOCAL", self.local):
            for target in (self.local, self.root):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    cleanup.checked_target(target)

    def test_apply_removes_only_disposable_copies_and_profile(self):
        disposable = self.copy("배포본 검수 3")
        saved = self.copy("배포본 검수 4", saved=True)
        profile = self.local / "registered-qa/chrome-profile"
        profile.mkdir(parents=True)
        (profile / "cache").write_bytes(b"temporary")
        report = profile.parent / "checks.json"
        report.write_text("{}", encoding="utf-8")
        reference = self.local / "reference-01.png"
        reference.write_bytes(b"original art")
        with patch.object(cleanup, "ROOT", self.root), \
                patch.object(cleanup, "LOCAL", self.local), \
                patch("sys.argv", ["clean_generated.py", "--apply"]), \
                contextlib.redirect_stdout(io.StringIO()):
            cleanup.main()
        self.assertFalse(disposable.exists())
        self.assertFalse(profile.exists())
        self.assertTrue(saved.exists())
        self.assertTrue(report.exists())
        self.assertEqual(reference.read_bytes(), b"original art")

    def test_dry_run_keeps_every_file(self):
        disposable = self.copy("배포본 검수 5")
        with patch.object(cleanup, "ROOT", self.root), \
                patch.object(cleanup, "LOCAL", self.local), \
                patch("sys.argv", ["clean_generated.py"]), \
                contextlib.redirect_stdout(io.StringIO()):
            cleanup.main()
        self.assertTrue(disposable.exists())


if __name__ == "__main__":
    unittest.main()
