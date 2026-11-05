"""Build the offline Windows bundle without development tools, keys or saves."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

BASE = Path(__file__).resolve().parents[1]
BUNDLE_ROOTS = ("runtime", "public", "templates", "services", "config", "data")
BUNDLE_FILES = (
    "app.py", "launch_game.py", "게임시작.cmd", "실행방법.txt", "requirements.txt",
    "docs/SCENARIO_COMPLIANCE.md", "docs/INTERACTION_VERIFICATION.md",
    "docs/INVENTORY_AUDIO_UPDATE.md", "docs/CHARACTER_SETTINGS.md", "docs/SIZE_OPTIMIZATION.md",
)
# The game uses a browser, not Tk. Keep all network/SSL, SQLite, package metadata,
# and AI dependencies: pruning individual SDK modules can break lazy imports.
UNUSED_STDLIB = {"ensurepip", "idlelib", "test", "tkinter", "turtledemo", "turtle.py"}
UNUSED_DLLS = {"tcl86t.dll", "tk86t.dll", "_tkinter.pyd"}
# These eight superseded source images stay in the repository. They are the only
# public assets eligible for omission, and a new runtime reference keeps them.
SOURCE_ONLY_ASSETS = {
    *(f"public/assets/images/scene_{number:02d}.png" for number in (2, 3, 5, 6, 7, 8)),
    "public/assets/images/inventory/scrapbook.png",
    "public/assets/images/inventory/warning.png",
}
REFERENCE_SUFFIXES = {
    "services": {".py"},
    "config": {".json", ".toml", ".ini", ".yaml", ".yml", ".txt", ".md"},
    "templates": {".html", ".htm", ".jinja", ".jinja2", ".j2", ".json"},
    "public": {".js", ".mjs", ".css", ".html", ".htm", ".json", ".svg", ".webmanifest"},
}


def unreferenced_source_assets(base=BASE):
    """Omit explicit old images only when no packaged runtime source names them."""
    references = set()
    sources = list(base.glob("*.py"))
    for folder, suffixes in REFERENCE_SUFFIXES.items():
        sources.extend(path for path in (base / folder).rglob("*")
                       if path.is_file() and path.suffix.lower() in suffixes)
    for source in sources:
        content = source.read_text(encoding="utf-8-sig").lower()
        references.update(asset for asset in SOURCE_ONLY_ASSETS
                          if Path(asset).name.lower() in content)
    return SOURCE_ONLY_ASSETS - references


def include_in_archive(relative, unreferenced_assets=()):
    """Filter only generated/private files and explicitly unused runtime tools."""
    relative = Path(relative)
    parts = relative.parts
    name = relative.name.lower()
    if ("__pycache__" in parts or relative.suffix.lower() in (".pyc", ".pyo", ".sqlite3")
            or name.endswith((".sqlite3-wal", ".sqlite3-shm", ".sqlite3-journal"))
            or name.startswith(".env")):
        return False
    if len(parts) >= 3 and parts[:2] == ("runtime", "Lib") and parts[2] in UNUSED_STDLIB:
        return False
    if parts[:2] == ("runtime", "DLLs") and name in UNUSED_DLLS:
        return False
    if relative.as_posix() in unreferenced_assets:
        return False
    return True


def bundle_files(base=BASE):
    unreferenced_assets = unreferenced_source_assets(base)
    files = [base / name for name in BUNDLE_FILES]
    for name in BUNDLE_ROOTS:
        root = base / name
        if not root.is_dir():
            raise FileNotFoundError(root)
        files.extend(path for path in root.rglob("*") if path.is_file())
    for path in sorted(files):
        if not path.is_file():
            raise FileNotFoundError(path)
        if include_in_archive(path.relative_to(base), unreferenced_assets):
            yield path


def write_archive(output, base=BASE):
    """Publish only a complete, verified ZIP, leaving an older build on failure."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    expected = set()
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in bundle_files(base):
                relative = path.relative_to(base)
                arcname = "13Fri/" + relative.as_posix()
                expected.add(arcname)
                archive.write(path, arcname)
        with zipfile.ZipFile(temporary) as archive:
            if set(archive.namelist()) != expected or archive.testzip() is not None:
                raise RuntimeError("Portable archive verification failed.")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def prepare_runtime(runtime, python_root, deps):
    """Copy a Python installation, or safely reuse this project's own runtime."""
    runtime = Path(runtime).resolve()
    python_root = Path(python_root).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    if python_root != runtime:
        for filename in ("python.exe", "python3.dll", "python311.dll", "vcruntime140.dll",
                         "vcruntime140_1.dll", "LICENSE.txt"):
            source = python_root / filename
            if source.is_file():
                shutil.copy2(source, runtime / filename)
        for folder in ("DLLs", "Lib"):
            shutil.copytree(python_root / folder, runtime / folder, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "site-packages", "idlelib", "test"))
    packages = runtime / "Lib/site-packages"
    deps = Path(deps).resolve()
    if deps != packages.resolve():
        shutil.copytree(deps, packages, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "bin"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", type=Path, default=BASE / ".local/python-deps")
    parser.add_argument("--reuse-runtime", action="store_true",
                        help="Package the existing runtime without copying Python or dependencies.")
    parser.add_argument("--output", type=Path, default=BASE / "dist/13Fri-Windows.zip")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Build the portable Windows package on Windows.")
    runtime = BASE / "runtime"
    if not args.reuse_runtime:
        prepare_runtime(runtime, Path(sys.base_prefix), args.deps)
    subprocess.run([str(runtime / "python.exe"), "-I", "-B", "-X", "utf8",
                    str(BASE / "launch_game.py"), "--check"], cwd=BASE, check=True)
    print("Created:", write_archive(args.output))


if __name__ == "__main__":
    main()
