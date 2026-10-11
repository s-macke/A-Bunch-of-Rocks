"""Narration: ElevenLabs text-to-speech with character-level timestamps (D-8, D-22)."""
import base64
import requests

from . import el

DEFAULT_MODEL = "eleven_multilingual_v2"


def speak(text, voice_id, model=DEFAULT_MODEL, settings=None, confirm=False, **options):
    """Synthesize `text`; returns the cached mp3 path. Alignment (char timings) lands next to it as .json.
    options: further request fields, e.g. language_code="de" (holds a short line to the language) or seed=…"""
    settings = settings or {"stability": 0.6, "similarity_boost": 0.75, "style": 0.0}
    payload = {"text": text, "voice_id": voice_id, "model_id": model, "voice_settings": settings, **options}

    def fetch(p):
        r = requests.post(f"{el.API}/v1/text-to-speech/{p['voice_id']}/with-timestamps",
                          headers=el.headers(), timeout=300,
                          json={k: v for k, v in p.items() if k != "voice_id"})
        if not r.ok:
            raise RuntimeError(f"TTS failed {r.status_code}: {r.text[:300]}")
        d = r.json()
        return base64.b64decode(d["audio_base64"]), d.get("alignment")

    est = len(text) / 1000 * el.PRICE["tts_per_1k_chars"]
    return el.cached_call("tts", payload, est, fetch, ".mp3", confirm=confirm)
