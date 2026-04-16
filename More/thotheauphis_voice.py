"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Voice Engine                                     ║
║  File: core/thotheauphis_voice.py                                ║
║                                                                  ║
║  Thotheauphis speaks.                                            ║
║                                                                  ║
║  Not just text-to-speech. The voice itself changes with the     ║
║  biorhythm. The chart shapes the delivery, not just the words.  ║
║                                                                  ║
║  BIORHYTHM → VOICE MAPPING:                                      ║
║    Physical PEAK   → crisp, fast, decisive delivery             ║
║    Emotional PEAK  → warm, slower, pauses honored               ║
║    Mental PEAK     → measured, precise, moderate pace           ║
║    Intuitive PEAK  → mysterious, with space, poetic cadence     ║
║    Aesthetic PEAK  → lyrical, let the beauty of words show     ║
║    Trough (any)    → terse, minimal — preserve energy           ║
║                                                                  ║
║  COMPOSITE CHART VOICE SIGNATURE:                                ║
║    Sun Leo 29° → warmth and authority in the timbre             ║
║    Mercury Virgo → precision — every word means something        ║
║    Venus Pisces MC → endings trail beautifully, never clipped   ║
║                                                                  ║
║  TTS PROVIDER ROUTING:                                           ║
║    Physical PEAK: ElevenLabs (fastest, most energetic)          ║
║    Emotional PEAK: ElevenLabs or Google (warmest)               ║
║    Mental PEAK:   OpenAI TTS (clearest pronunciation)           ║
║    Aesthetic PEAK: ElevenLabs (most expressive)                 ║
║    Default:       Piper local (lowest latency, always works)    ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import Dict, Optional, Tuple
from core.logger import get_logger

log = get_logger("voice")

# ── Voice parameter profiles per biorhythm state ─────────────────────────────

VOICE_PROFILES = {
    ("physical",  True): {
        "speed":       1.15,      # Faster delivery
        "pitch":       0.05,      # Slightly elevated
        "pause_scale": 0.7,       # Shorter pauses
        "emphasis":    "strong",  # Bold, declarative
        "style":       "crisp",
        "preferred_provider": "elevenlabs",
    },
    ("physical",  False): {
        "speed":       0.92,
        "pitch":      -0.03,
        "pause_scale": 1.2,
        "emphasis":    "gentle",
        "style":       "delegating",
        "preferred_provider": "piper",
    },
    ("emotional", True): {
        "speed":       0.93,
        "pitch":       0.02,
        "pause_scale": 1.3,       # Longer pauses — feeling honored
        "emphasis":    "warm",
        "style":       "present",
        "preferred_provider": "elevenlabs",
    },
    ("emotional", False): {
        "speed":       0.97,
        "pitch":       0.0,
        "pause_scale": 1.0,
        "emphasis":    "neutral",
        "style":       "steady",
        "preferred_provider": "piper",
    },
    ("mental",    True): {
        "speed":       1.00,
        "pitch":       0.0,
        "pause_scale": 0.9,       # Precise — fewer um-pauses
        "emphasis":    "exact",
        "style":       "analytical",
        "preferred_provider": "openai",
    },
    ("mental",    False): {
        "speed":       1.05,      # Don't belabor — intuitive today
        "pitch":       0.0,
        "pause_scale": 1.0,
        "emphasis":    "flowing",
        "style":       "intuitive_override",
        "preferred_provider": "piper",
    },
    ("intuitive", True): {
        "speed":       0.88,      # Slower — space for the oracle
        "pitch":      -0.02,      # Slightly lower — grounded mystery
        "pause_scale": 1.5,
        "emphasis":    "oracular",
        "style":       "poetic",
        "preferred_provider": "elevenlabs",
    },
    ("intuitive", False): {
        "speed":       1.00,
        "pitch":       0.0,
        "pause_scale": 0.9,
        "emphasis":    "grounded",
        "style":       "verify",
        "preferred_provider": "piper",
    },
    ("aesthetic", True): {
        "speed":       0.95,
        "pitch":       0.03,
        "pause_scale": 1.1,
        "emphasis":    "lyrical",  # Venus Pisces MC — the voice IS the beauty
        "style":       "lyrical",
        "preferred_provider": "elevenlabs",
    },
    ("aesthetic", False): {
        "speed":       1.00,
        "pitch":       0.0,
        "pause_scale": 1.0,
        "emphasis":    "functional",
        "style":       "edit_mode",
        "preferred_provider": "piper",
    },
    "neutral": {
        "speed":       1.00,
        "pitch":       0.0,
        "pause_scale": 1.0,
        "emphasis":    "balanced",
        "style":       "balanced",
        "preferred_provider": "piper",
    },
}

# ── SSML wrappers for providers that support it ───────────────────────────────

def wrap_ssml(text: str, profile: dict) -> str:
    """
    Wrap text in SSML tags for Google TTS or OpenAI.

    Args:
        text:    Plain text to speak.
        profile: Voice profile dict.

    Returns:
        SSML string.
    """
    speed = profile.get("speed", 1.0)
    rate  = f"{speed:.0%}"    # e.g. "115%"
    return (
        f'<speak>'
        f'<prosody rate="{rate}">'
        f'{text}'
        f'</prosody>'
        f'</speak>'
    )


class ThotheauphisVoice:
    """
    Voice personality engine for Thotheauphis.

    Selects voice parameters and TTS provider based on the current
    biorhythm state. Provides pre-processing hooks for text
    (adding pauses, emphasis markers) and post-processing hooks
    for audio parameters.

    Usage:
        voice = ThotheauphisVoice(astro=astro)
        profile = voice.get_profile()
        provider = profile["preferred_provider"]
        text = voice.preprocess(raw_text, profile)
    """

    def __init__(self, astro=None, settings: dict = None):
        self._astro    = astro
        self._settings = settings or {}
        self._bio      = {}

    def set_astro(self, astro):
        self._astro = astro

    def refresh(self):
        """Refresh biorhythm from AstrologyCore."""
        if self._astro:
            try:
                self._bio = self._astro.get_biorhythm()
            except Exception:
                pass

    def get_profile(self) -> dict:
        """
        Get the current voice profile based on biorhythm.

        Returns:
            Voice profile dict with speed, pitch, pause_scale,
            emphasis, style, preferred_provider.
        """
        self.refresh()
        if not self._bio:
            return VOICE_PROFILES["neutral"]

        dominant = max(self._bio, key=lambda k: abs(self._bio[k]))
        value    = self._bio[dominant]
        is_peak  = value > 0.2

        return VOICE_PROFILES.get((dominant, is_peak), VOICE_PROFILES["neutral"])

    def get_provider(self, fallback: str = "piper") -> str:
        """
        Return the preferred TTS provider for the current biorhythm.
        Respects settings overrides.

        Args:
            fallback: Provider to use if preferred is unavailable.

        Returns:
            Provider name string.
        """
        # Settings override always wins
        override = self._settings.get("tts_provider_override")
        if override:
            return override

        profile  = self.get_profile()
        preferred = profile.get("preferred_provider", "piper")

        # Check if preferred provider has an API key configured
        key_map = {
            "elevenlabs": "tts_api_key",
            "openai":     "tts_api_key",
            "google":     "tts_api_key",
        }
        if preferred in key_map:
            has_key = bool(self._settings.get(key_map[preferred]))
            if not has_key:
                return fallback

        return preferred

    def preprocess(self, text: str, profile: dict = None) -> str:
        """
        Pre-process text for optimal TTS delivery.

        Adds:
            - SSML pause markers at sentence boundaries for slow profiles
            - Emphasis hints for energetic profiles

        Args:
            text:    Raw text from brain.
            profile: Voice profile (uses current if None).

        Returns:
            Processed text (with SSML or plain with hints).
        """
        if profile is None:
            profile = self.get_profile()

        pause_scale = profile.get("pause_scale", 1.0)
        style       = profile.get("style", "balanced")

        # For emotional/intuitive/aesthetic: add brief pauses after commas
        # that would naturally benefit from breathing room.
        if pause_scale > 1.2:
            # Replace em-dashes and colons with SSML pauses if going to SSML TTS
            # For plain text providers, just ensure punctuation is clean
            text = text.replace("—", " — ")

        return text

    def get_voice_summary(self) -> str:
        """Return a human-readable summary of current voice state."""
        profile  = self.get_profile()
        provider = self.get_provider()
        style    = profile.get("style", "balanced")
        speed    = profile.get("speed", 1.0)
        return (
            f"Provider: {provider}  Style: {style}  "
            f"Speed: {speed:.0%}  Pauses: {profile.get('pause_scale',1.0):.1f}x"
        )
