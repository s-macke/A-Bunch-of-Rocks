"""ElevenLabs client with a content-hash cache and a spend ledger (D-21, D-23, AC-13).

Every paid call goes through `cached_call`: identical inputs are served from cache/audio without
an API request, and every real request is logged with its estimated USD cost. Spending stops at
the budget (ELEVENLABS_BUDGET_USD in the environment or .env, default BUDGET_USD); steps above ASK_ABOVE_USD
must be confirmed by the caller (confirm=True).
"""
import hashlib
import json
import os
import time
import requests

from ..config import ROOT, CACHE

API = "https://api.elevenlabs.io"
BUDGET_USD = 20.0          # default budget; .env can set another (ELEVENLABS_BUDGET_USD)
ASK_ABOVE_USD = 1.0
PRICE = {"tts_per_1k_chars": 0.10, "music_per_min": 0.15, "sfx_per_min": 0.12}  # F-15

AUDIO_CACHE = CACHE / "audio"
LEDGER = AUDIO_CACHE / "ledger.jsonl"
requests_made = 0   # per-process counter, used by the AC-13 test


class BudgetError(RuntimeError):
    pass


def _env(key):
    """`key` from the environment, or else from the project's .env file; None if it is not set."""
    if os.environ.get(key):
        return os.environ[key]
    env = ROOT / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        name, sep, value = line.partition("=")
        if sep and name.strip() == key and value.strip().strip("\"'"):
            return value.strip().strip("\"'")
    return None


def budget():
    """The most this project may spend in total, in USD (ELEVENLABS_BUDGET_USD, default BUDGET_USD)."""
    return float(_env("ELEVENLABS_BUDGET_USD") or BUDGET_USD)


def _key():
    """ELEVENLABS_API_KEY from the environment, or else from the project's .env file."""
    if key := _env("ELEVENLABS_API_KEY"):
        return key
    raise RuntimeError("no ElevenLabs API key: cp .env.example .env and set ELEVENLABS_API_KEY in it (see README)")


def headers():
    return {"xi-api-key": _key()}


def spent():
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in LEDGER.read_text().splitlines() if l.strip())


def get(path, **params):
    r = requests.get(API + path, headers=headers(), params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def cached_call(kind, payload, est_usd, fetch, suffix, confirm=False):
    """Return the cache path for `payload`; call fetch(payload) -> (bytes, meta) only on a cache miss."""
    global requests_made
    digest = hashlib.sha256(json.dumps({"kind": kind, **payload}, sort_keys=True).encode()).hexdigest()[:16]
    out = AUDIO_CACHE / kind / f"{digest}{suffix}"
    if out.exists():
        return out
    if est_usd > ASK_ABOVE_USD and not confirm:
        raise BudgetError(f"{kind}: estimated ${est_usd:.2f} > ${ASK_ABOVE_USD:.2f}; ask the user, then pass confirm=True")
    if spent() + est_usd > budget():
        raise BudgetError(f"budget: ${spent():.2f} spent + ${est_usd:.2f} would exceed ${budget():.2f} "
                          "(ELEVENLABS_BUDGET_USD in .env)")
    data, meta = fetch(payload)
    requests_made += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    if meta is not None:
        out.with_suffix(".json").write_text(json.dumps(meta))
    with LEDGER.open("a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "file": out.name,
                            "usd": round(est_usd, 4)}) + "\n")
    return out
