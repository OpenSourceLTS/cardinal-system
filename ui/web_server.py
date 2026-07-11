import asyncio
import json
import uuid
from io import BytesIO
from pathlib import Path

import edge_tts
from flask import Flask, request, jsonify

from core.engine import CardinalSystemEngine
from core import history
from core.manifest import load_tool_class
from core.mcp_server import _ROUTER


PROJECT_ROOT = Path(__file__).parent.parent

app = Flask(__name__, static_folder=None)
engine: CardinalSystemEngine = None


def init_engine():
    global engine
    engine = CardinalSystemEngine()


init_engine()


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response


@app.route("/")
def root():
    return "Cardinal API server — access the UI at http://localhost:5173", 200


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# Session CRUD
@app.route("/api/sessions", methods=["GET", "POST"])
def sessions():
    if request.method == "GET":
        return jsonify({"sessions": history.list_sessions()})

    sid = uuid.uuid4().hex[:12]
    try:
        data = request.get_json(silent=True)
        if data and "id" in data:
            sid = data["id"]
    except Exception:
        pass
    history.create(sid)
    return jsonify({"id": sid, "created": True}), 201


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    history.delete(session_id)
    return jsonify({"deleted": True})


@app.route("/api/history/<session_id>")
def get_history(session_id):
    return jsonify({"history": history.load(session_id)})


# Chat endpoint
@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 204

    try:
        data = request.get_json()
        message = data.get("message", "")
        session_id = data.get("session_id", "")

        # Router detects language and translates non-English to English
        send_text, user_original = _ROUTER.route_user_input(message)
        user_translated = send_text if send_text != user_original else ""

        result = engine.process_request(send_text, session_id=session_id)
        response_text = result.get("response", "")
        prefs = _load_prefs()
        spoken_lang = prefs.get("spoken_lang", "")
        translated_response = ""
        translation_time = 0
        if spoken_lang and spoken_lang != "en" and response_text:
            import time
            t0 = time.time()
            global _translate_ctx
            if _translate_ctx is None:
                from core.base_tool import ExecutionContext
                _translate_ctx = ExecutionContext()
            payload = f"{response_text} | en"
            tr = _translate_tool.execute("translate", spoken_lang, payload, {}, _translate_ctx)
            if tr.success:
                translated_response = tr.value
            translation_time = round(time.time() - t0, 2)

        if session_id and user_original:
            history.append(session_id, "user", send_text, user_original=user_original)
        for tr in result.get("results", []):
            tn = tr.get("tool", "")
            args = tr.get("arguments", {})
            output = tr.get("output", "")
            if tn and session_id:
                history.append(session_id, "tool", output, tool_name=tn, tool_args=json.dumps(args))
        if session_id and result.get("is_chat") and response_text:
            history.append(session_id, "assistant", response_text, translated_response)

        return jsonify({
            "success": result.get("success", False),
            "response": response_text,
            "translated_response": translated_response,
            "user_translated": user_translated,
            "translation_time": translation_time,
            "results": result.get("results", []),
            "is_chat": bool(result.get("is_chat")),
            "error": result.get("error", ""),
            "stats": result.get("stats", {}),
            "raw_output": result.get("raw_output", ""),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {e}",
            "raw_output": ""
        }), 500


def _load_prefs():
    pf = PROJECT_ROOT / "memory" / "settings.md"
    if not pf.exists():
        return {}
    prefs = {}
    for line in pf.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, _, v = line.partition(":")
            prefs[k.strip()] = v.strip()
    return prefs


def _tts_voice_for(code):
    code = code.lower().strip()
    if code in TTS_VOICE_MAP_CACHE:
        return TTS_VOICE_MAP_CACHE[code]
    return "en-US-JennyNeural"


TTS_VOICE_MAP_CACHE = {
    "ar": "ar-SA-ZariyahNeural", "az": "az-AZ-BanuNeural",
    "bg": "bg-BG-KalinaNeural", "bn": "bn-BD-NabanitaNeural",
    "ca": "ca-ES-JoanaNeural", "cs": "cs-CZ-VlastaNeural",
    "da": "da-DK-ChristelNeural", "de": "de-DE-KatjaNeural",
    "el": "el-GR-AthinaNeural", "en": "en-US-JennyNeural",
    "es": "es-ES-ElviraNeural", "et": "et-EE-AnuNeural",
    "fa": "fa-IR-DilaraNeural", "fi": "fi-FI-NooraNeural",
    "fr": "fr-FR-DeniseNeural", "ga": "ga-IE-OrlaNeural",
    "gl": "gl-ES-SabelaNeural", "he": "he-IL-HilaNeural",
    "hi": "hi-IN-SwaraNeural", "hu": "hu-HU-NoemiNeural",
    "id": "id-ID-GadisNeural", "it": "it-IT-ElsaNeural",
    "ja": "ja-JP-NanamiNeural", "ko": "ko-KR-SunHiNeural",
    "ky": "kk-KZ-AigulNeural", "lt": "lt-LT-OnaNeural",
    "lv": "lv-LV-EveritaNeural", "ms": "ms-MY-YasminNeural",
    "nb": "nb-NO-PernilleNeural", "nl": "nl-NL-FennaNeural",
    "pb": "ps-AF-LatifaNeural", "pl": "pl-PL-ZofiaNeural",
    "pt": "pt-BR-FranciscaNeural", "ro": "ro-RO-AlinaNeural",
    "ru": "ru-RU-SvetlanaNeural", "sk": "sk-SK-ViktoriaNeural",
    "sl": "sl-SI-PetraNeural", "sq": "sq-AL-AnilaNeural",
    "sv": "sv-SE-SofieNeural", "sw": "sw-KE-ZuriNeural",
    "th": "th-TH-PremwadeeNeural", "tl": "fil-PH-BlessicaNeural",
    "tr": "tr-TR-EmelNeural", "uk": "uk-UA-PolinaNeural",
    "ur": "ur-PK-UzmaNeural", "vi": "vi-VN-HoaiMyNeural",
    "zh": "zh-CN-XiaoxiaoNeural", "zt": "zh-TW-HsiaoChenNeural",
}

_translate_tool = load_tool_class("libretranslate")()
_translate_ctx = None


@app.route("/api/preferences", methods=["GET"])
def preferences():
    return jsonify(_load_prefs())


_tts_cache = {}

@app.route("/api/tts", methods=["GET"])
def tts():
    text = request.args.get("text", "")
    lang = request.args.get("lang", "")
    if not text:
        return "Missing text", 400
    if not lang:
        prefs = _load_prefs()
        lang = prefs.get("spoken_lang", "bn")
    voice = _tts_voice_for(lang)
    cache_key = f"{lang}:{text}"
    if cache_key in _tts_cache:
        return _tts_cache[cache_key]
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        mp3_data = loop.run_until_complete(_edge_tts_synth(text, voice))
        loop.close()
        resp = (mp3_data, 200, {"Content-Type": "audio/mpeg"})
        _tts_cache[cache_key] = resp
        return resp
    except Exception as e:
        return f"TTS error: {e}", 500


async def _edge_tts_synth(text, voice):
    communicate = edge_tts.Communicate(text, voice)
    buf = BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def run_server(host: str = "0.0.0.0", port: int = 8080):
    import warnings
    warnings.filterwarnings("ignore", message=".*development server.*")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()
