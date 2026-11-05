"""Guard the portable manifest and atomic rebuilds without running network calls."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import build_portable as portable
from tools import verify_portable as verifier


class PortableBundleTest(unittest.TestCase):
    def test_only_explicit_unreferenced_source_images_are_omitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            protected = {"public/assets/images/scene_01.png", "public/assets/images/scene_04.png"}
            # Preserve every current portrait, scene background/hotspot mask and
            # printed inventory record, including names absent from today's UI.
            for pattern in ("public/assets/images/portrait_*.png",
                            "public/assets/images/scenes/*", "public/assets/images/inventory/records/*"):
                protected.update(path.relative_to(portable.BASE).as_posix()
                                 for path in portable.BASE.glob(pattern) if path.is_file())
            protected.add("public/assets/images/scenes/future-mask.png")
            for name in portable.SOURCE_ONLY_ASSETS | protected:
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"original")
            with patch.object(portable, "BUNDLE_ROOTS", ("public",)), \
                    patch.object(portable, "BUNDLE_FILES", ()):
                packaged = {path.relative_to(base).as_posix() for path in portable.bundle_files(base)}
            self.assertEqual(packaged, protected)
            for name in portable.SOURCE_ONLY_ASSETS:
                self.assertEqual((base / name).read_bytes(), b"original")

    def test_runtime_reference_reintroduces_source_images_in_every_source_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for name in portable.SOURCE_ONLY_ASSETS:
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"original")
            self.assertEqual(portable.unreferenced_source_assets(base), portable.SOURCE_ONLY_ASSETS)
            for filename in ("app.py", "launch_game.py", "services/image_selector.py",
                             "config/chatbot_config.json", "templates/chat.html",
                             "public/assets/js/chatbot.js", "public/assets/css/style.css"):
                with self.subTest(filename=filename):
                    source = base / filename
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text("\n".join(Path(name).name for name in portable.SOURCE_ONLY_ASSETS),
                                      encoding="utf-8")
                    self.assertEqual(portable.unreferenced_source_assets(base), set())
                    with patch.object(portable, "BUNDLE_ROOTS", ("public",)), \
                            patch.object(portable, "BUNDLE_FILES", ()):
                        packaged = {path.relative_to(base).as_posix() for path in portable.bundle_files(base)}
                    self.assertTrue(portable.SOURCE_ONLY_ASSETS <= packaged)
                    source.unlink()

    def test_browser_verification_uses_extracted_runtime_while_it_exists(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            runtime = base / "runtime/python.exe"
            runtime.parent.mkdir()
            runtime.write_bytes(b"portable Python")
            archive_path = base / "game.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.write(runtime, "13Fri/runtime/python.exe")
            roots = []

            def run(command, **options):
                if command[0] != "node-for-test":
                    return
                game = Path(options["env"]["GAMEPLAY_QA_GAME_ROOT"])
                self.assertEqual((game / "runtime/python.exe").read_bytes(), b"portable Python")
                self.assertEqual(options["env"]["GAMEPLAY_QA_PYTHON"], str(game / "runtime/python.exe"))
                self.assertEqual(options["cwd"], base)
                self.assertLessEqual(options["timeout"], 180)
                roots.append(game)

            with patch.object(verifier, "bundle_files", return_value=[runtime]), \
                    patch.object(verifier.shutil, "which", return_value="node-for-test"), \
                    patch.object(verifier.subprocess, "run", side_effect=run):
                verifier.verify_archive(archive_path, base=base, browser=True)
            self.assertEqual(len(roots), 1)
            self.assertFalse(roots[0].exists())

    def test_runtime_pruning_preserves_game_dependencies(self):
        removed = (
            "runtime/Lib/ensurepip/_bundled/pip.whl",
            "runtime/Lib/tkinter/__init__.py", "runtime/Lib/turtle.py",
            "runtime/DLLs/tcl86t.dll", "runtime/DLLs/tk86t.dll", "runtime/DLLs/_tkinter.pyd",
        )
        preserved = (
            "runtime/DLLs/libcrypto-3.dll", "runtime/DLLs/libssl-3.dll",
            "runtime/DLLs/_ssl.pyd", "runtime/DLLs/_sqlite3.pyd", "runtime/DLLs/sqlite3.dll",
            "runtime/Lib/site-packages/openai/resources/responses/responses.py",
            "runtime/Lib/site-packages/openai-2.54.0.dist-info/METADATA",
            "runtime/Lib/site-packages/certifi/cacert.pem", "runtime/Lib/unittest/__init__.py",
            "public/assets/images/test/ensurepip.png", "data/knowledge/ai-policy.md",
        )
        for path in removed:
            with self.subTest(path=path):
                self.assertFalse(portable.include_in_archive(path))
        for path in preserved:
            with self.subTest(path=path):
                self.assertTrue(portable.include_in_archive(path))

    def test_keys_saves_and_generated_bytecode_are_excluded(self):
        for path in (
            "data/game.sqlite3", "data/GAME.SQLITE3", "data/game.sqlite3-wal",
            "data/game.sqlite3-shm", "data/game.sqlite3-journal", "config/.env.local",
            "services/__pycache__/game.pyc", "runtime/Lib/site-packages/example.pyo",
        ):
            with self.subTest(path=path):
                self.assertFalse(portable.include_in_archive(path))

    def test_archive_contains_current_files_and_preserves_existing_build_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / "runtime").mkdir()
            (base / "public").mkdir()
            (base / "runtime/python.exe").write_bytes(b"python")
            (base / "public/current.js").write_bytes(b"current game source")
            (base / "public/.env.local").write_bytes(b"secret")
            (base / "launch_game.py").write_text("pass", encoding="utf-8")
            output = base / "dist/game.zip"
            with patch.object(portable, "BUNDLE_ROOTS", ("runtime", "public")), \
                    patch.object(portable, "BUNDLE_FILES", ("launch_game.py",)):
                portable.write_archive(output, base)
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(set(archive.namelist()), {
                        "13Fri/runtime/python.exe", "13Fri/public/current.js", "13Fri/launch_game.py",
                    })
                    self.assertEqual(archive.read("13Fri/public/current.js"), b"current game source")
                previous = output.read_bytes()
                (base / "launch_game.py").unlink()
                with self.assertRaises(FileNotFoundError):
                    portable.write_archive(output, base)
                self.assertEqual(output.read_bytes(), previous)
                self.assertFalse(output.with_suffix(".zip.tmp").exists())

    def test_existing_runtime_can_build_without_copying_onto_itself(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "runtime"
            packages = runtime / "Lib/site-packages"
            packages.mkdir(parents=True)
            (runtime / "python.exe").write_bytes(b"existing Python")
            (packages / "openai.py").write_text("sdk", encoding="utf-8")
            portable.prepare_runtime(runtime, runtime, packages)
            self.assertEqual((runtime / "python.exe").read_bytes(), b"existing Python")
            self.assertEqual((packages / "openai.py").read_text(encoding="utf-8"), "sdk")


if __name__ == "__main__":
    unittest.main()
