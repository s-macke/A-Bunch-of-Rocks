"""Sound effects via ElevenLabs text-to-sound (D-9, D-21). Cached like everything else."""
import requests

from . import el

LIBRARY = {
    "room_tone": ("quiet empty room tone, faint distant city hum through a window, very soft, no voices, no music", 10.0, True),
    "dust_flash": ("a tiny delicate sparkle, single soft glassy twinkle, very short and quiet", 1.0, False),
    "desert_wind": ("gentle lonely desert wind blowing over open sand, soft and steady, no music, no voices", 10.0, True),
    # wind round 2 (user: "more like noise"): the first wind was a mid-band hiss (2 % energy < 500 Hz)
    "wind_gusts": ("desert wind gusts rising and falling, deep low rumble of moving air, sand grains hissing softly on "
                   "the strongest gusts, wide open empty space, natural field recording, no music, no voices", 20.0, True),
    "wind_howl": ("lonely wind blowing softly across empty desert dunes, slow gusts, a faint low hollow whistle, "
                  "distant and airy, natural field recording, no music, no voices", 20.0, True),
    "wind_breeze": ("warm gentle breeze over open sand with occasional stronger gusts, soft rustle of sand, deep and "
                    "calm, natural field recording, no music, no voices", 20.0, True),
    "clock_tick": ("a single wall clock tick, dry mechanical click, close up, nothing else", 0.6, False),
    "footstep_sand": ("one single slow footstep on soft sand, gentle crunch, nothing else", 0.8, False),
    "sand_scratch": ("a finger writing slowly in dry sand, soft scratching, close, nothing else", 1.5, False),
    "rock_set_down": ("a small stone set down gently on sand and other stones, soft click", 1.0, False),
}


def get(name, confirm=False):
    prompt, seconds, loop = LIBRARY[name]
    payload = {"text": prompt, "duration_seconds": seconds, "loop": loop, "model_id": "eleven_text_to_sound_v2",
               "prompt_influence": 0.5}

    def fetch(p):
        r = requests.post(f"{el.API}/v1/sound-generation", headers=el.headers(), json=p, timeout=300)
        if not r.ok:
            raise RuntimeError(f"SFX {name} failed {r.status_code}: {r.text[:300]}")
        return r.content, None

    est = seconds / 60 * el.PRICE["sfx_per_min"]
    return el.cached_call("sfx", payload, est, fetch, ".mp3", confirm=confirm)


if __name__ == "__main__":
    for n in LIBRARY:
        print(n, get(n).name)
    print(f"spent: ${el.spent():.3f}, requests: {el.requests_made}")
