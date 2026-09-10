from __future__ import annotations

import json
from pathlib import Path

import pytest

COMPONENT_ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "entity_assistant"
STRINGS_FILE = COMPONENT_ROOT / "strings.json"
TRANSLATIONS_DIR = COMPONENT_ROOT / "translations"


def _leaf_key_paths(node, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                paths.update(_leaf_key_paths(value, path))
            else:
                paths.add(path)
    return paths


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _translation_files() -> list[Path]:
    return sorted(TRANSLATIONS_DIR.glob("*.json"))


def test_strings_file_exists() -> None:
    assert STRINGS_FILE.exists()


def test_translations_directory_populated() -> None:
    files = _translation_files()
    assert files, "no translation files found"


@pytest.mark.parametrize("locale_path", _translation_files(), ids=lambda p: p.name)
def test_translation_has_all_strings_keys(locale_path: Path) -> None:
    baseline = _leaf_key_paths(_load_json(STRINGS_FILE))
    locale = _leaf_key_paths(_load_json(locale_path))
    missing = baseline - locale
    assert not missing, f"{locale_path.name} is missing keys: {sorted(missing)}"


@pytest.mark.parametrize("locale_path", _translation_files(), ids=lambda p: p.name)
def test_translation_has_no_extra_keys(locale_path: Path) -> None:
    baseline = _leaf_key_paths(_load_json(STRINGS_FILE))
    locale = _leaf_key_paths(_load_json(locale_path))
    extra = locale - baseline
    assert not extra, f"{locale_path.name} has extra keys: {sorted(extra)}"


def test_en_translation_matches_strings() -> None:
    en_path = TRANSLATIONS_DIR / "en.json"
    assert _load_json(en_path) == _load_json(STRINGS_FILE)
