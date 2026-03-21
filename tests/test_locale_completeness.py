"""Ensure en.json and zh.json have identical key sets."""

import json
import os


def test_locale_key_parity():
    import wenzi.i18n as i18n_mod
    locales_dir = os.path.join(os.path.dirname(i18n_mod.__file__), "locales")
    with open(os.path.join(locales_dir, "en.json"), encoding="utf-8") as f:
        en_keys = set(json.load(f).keys())
    with open(os.path.join(locales_dir, "zh.json"), encoding="utf-8") as f:
        zh_keys = set(json.load(f).keys())

    missing_in_zh = en_keys - zh_keys
    missing_in_en = zh_keys - en_keys

    errors = []
    if missing_in_zh:
        errors.append(f"Keys in en.json but missing in zh.json: {sorted(missing_in_zh)}")
    if missing_in_en:
        errors.append(f"Keys in zh.json but missing in en.json: {sorted(missing_in_en)}")

    assert not errors, "\n".join(errors)
