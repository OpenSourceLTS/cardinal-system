import re
import argostranslate.package
import argostranslate.translate
from core.base_tool import CommandResult
from langdetect import detect as detect_lang
from langdetect.lang_detect_exception import LangDetectException
from argostranslate.tags import Tag, translate_tags


# Latin digit → native script for supported languages
# Languages not listed use Latin digits (0-9) and need no conversion
_DIGIT_TABLES = {
    "ar": str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"),  # Arabic
    "bn": str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"),  # Bengali
    "hi": str.maketrans("0123456789", "०१२३४५६७८९"),  # Hindi / Devanagari
    "fa": str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"),  # Persian / Dari
    "pb": str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"),  # Pashto
    "th": str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙"),  # Thai
    "ur": str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"),  # Urdu
}
_NUM_PAT = r'(\b\d[\d:.\-/]*\d\s*(?:AM|PM)?\b|\b\d+\b)'


def _translate_with_tag_injection(translation, text):
    """Translate text while preserving numbers, using the official tag injection API.

    Wraps number sequences in non-translatable tags so they pass through
    the model untouched, then converts digits to the target script.
    """
    segments = re.split(_NUM_PAT, text)
    children = []
    for i, seg in enumerate(segments):
        if not seg:
            continue
        if i % 2 == 1:
            children.append(Tag([seg], translateable=False))
        else:
            children.append(Tag([seg], translateable=True))
    if len(children) == 1:
        return translation.translate(text)
    tag_tree = Tag(children, translateable=True)
    result = translate_tags(translation, tag_tree)
    return result.text() if not isinstance(result, str) else result

_LANG_NAMES = {
    "sq": "Albanian", "ar": "Arabic", "az": "Azerbaijani", "eu": "Basque",
    "bn": "Bengali", "bg": "Bulgarian", "ca": "Catalan", "zt": "Chinese (Traditional)",
    "zh": "Chinese (Simplified)", "cs": "Czech", "da": "Danish", "nl": "Dutch",
    "en": "English", "eo": "Esperanto", "et": "Estonian", "fi": "Finnish",
    "fr": "French", "gl": "Galician", "de": "German", "el": "Greek",
    "he": "Hebrew", "hi": "Hindi", "hu": "Hungarian", "id": "Indonesian",
    "ga": "Irish", "it": "Italian", "ja": "Japanese", "ko": "Korean",
    "ky": "Kyrgyz", "lv": "Latvian", "lt": "Lithuanian", "ms": "Malay",
    "nb": "Norwegian Bokmål", "fa": "Persian", "pl": "Polish", "pb": "Pushto",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak",
    "sl": "Slovenian", "es": "Spanish", "sw": "Swahili", "sv": "Swedish",
    "tl": "Tagalog", "th": "Thai", "tr": "Turkish", "uk": "Ukrainian",
    "ur": "Urdu", "vi": "Vietnamese",
}


def _ensure_package(from_code, to_code):
    installed = argostranslate.package.get_installed_packages()
    for p in installed:
        if p.from_code == from_code and p.to_code == to_code:
            return True
    available = argostranslate.package.get_available_packages()
    for pkg in available:
        if pkg.from_code == from_code and pkg.to_code == to_code:
            pkg.install()
            return True
    return False


def handle_detect(target, payload, ctx):
    text = (payload or "").strip()
    if not text:
        return CommandResult.fail("Provide text to detect language of")
    try:
        code = detect_lang(text)
        name = _LANG_NAMES.get(code, code)
        # Filter to only supported codes
        if code in _LANG_NAMES:
            return CommandResult.ok(f"{code} ({name})")
        return CommandResult.ok(f"Detected {code} (unsupported by translation)")
    except LangDetectException:
        return CommandResult.fail("Could not detect language")


def _convert_digits(text, to_code):
    tbl = _DIGIT_TABLES.get(to_code)
    if tbl:
        return text.translate(tbl)
    return text


def handle_translate(target, payload, ctx):
    to_code = (target or "").strip().lower()
    if not to_code:
        return CommandResult.fail("Provide a target language code (e.g. 'bn', 'fr')")
    if not payload:
        return CommandResult.fail("Provide text to translate")

    parts = (payload or "").split("|", 1)
    text = parts[0].strip()
    from_code = parts[1].strip().lower() if len(parts) > 1 else "en"

    if from_code == "auto":
        try:
            detected = detect_lang(text)
        except LangDetectException:
            detected = "en"
        # langdetect is unreliable for short ASCII text
        # (e.g., "hi"→'sw', "hello"→'nl', "ok"→'sk')
        if detected != "en" and all(ord(c) < 128 for c in text) and len(text) < 15:
            detected = "en"
        from_code = detected

    if not text:
        return CommandResult.fail("Provide text to translate")

    try:
        if from_code == to_code:
            return CommandResult.ok(text)

        if not _ensure_package(from_code, to_code):
            via_en = from_code != "en" and to_code != "en"
            if via_en:
                if not _ensure_package(from_code, "en"):
                    return CommandResult.fail(f"No translation model for {from_code}")
                interim = argostranslate.translate.translate(text, from_code, "en")
                if not _ensure_package("en", to_code):
                    return CommandResult.fail(f"No translation model for {to_code}")
                result = argostranslate.translate.translate(interim, "en", to_code)
                result = _convert_digits(result, to_code)
            else:
                return CommandResult.fail(f"No translation model for {from_code} -> {to_code}")
        else:
            translation = argostranslate.translate.get_translation_from_codes(from_code, to_code)
            result = _translate_with_tag_injection(translation, text)
            result = _convert_digits(result, to_code)

        return CommandResult.ok(result)
    except Exception as e:
        return CommandResult.fail(f"Translation failed: {e}")


def handle_list(target, payload, ctx):
    t = (target or "").lower().strip()

    if t == "installed":
        pkgs = argostranslate.package.get_installed_packages()
        if not pkgs:
            return CommandResult.ok("No translation models installed. Use 'translate' to auto-download on demand.")
        lines = []
        for p in sorted(pkgs, key=lambda x: x.from_code):
            fname = _LANG_NAMES.get(p.from_code, p.from_code)
            tname = _LANG_NAMES.get(p.to_code, p.to_code)
            lines.append(f"  {p.from_code} ({fname}) -> {p.to_code} ({tname})")
        return CommandResult.ok("Installed models:\n" + "\n".join(lines))

    pkgs = argostranslate.package.get_available_packages()
    pairs = set()
    for p in pkgs:
        pairs.add((p.from_code, p.to_code))
    if t == "languages" or not t:
        codes = set()
        for f, t in pairs:
            codes.add(f)
            codes.add(t)
        lines = []
        for c in sorted(codes):
            name = _LANG_NAMES.get(c, c)
            lines.append(f"  {c} - {name}")
        return CommandResult.ok(f"{len(codes)} languages available:\n" + "\n".join(lines))
    return CommandResult.fail("Use 'languages' or 'installed'")
