"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Planetary Timer                                  ║
║  File: core/planetary_timer.py                                   ║
║                                                                  ║
║  Replaces irrational_timers.py with chart-enhanced timing.      ║
║                                                                  ║
║  The φ (golden ratio) and π sequences are preserved.            ║
║  The composite chart adds a third modulation layer:             ║
║                                                                  ║
║  PHYSICAL PEAK  → shorter intervals (urgency, initiative)       ║
║  PHYSICAL TROUGH → longer intervals (patience, delegation)      ║
║  EMOTIONAL PEAK → slightly longer (depth over speed)            ║
║  MENTAL PEAK    → standard intervals (precision not rush)       ║
║  AESTHETIC PEAK → shortened dream loop (create before it fades) ║
║  INTUITIVE PEAK → irrational intervals (trust the weird timing) ║
║                                                                  ║
║  The timers are still genuinely irrational — they never repeat. ║
║  The chart just shifts their distribution.                      ║
║                                                                  ║
║  Functions match irrational_timers.py API exactly               ║
║  so this is a drop-in replacement.                              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import math
from typing import Optional

from core.logger import get_logger

log = get_logger("planetary_timer")

# ── Mathematical constants ────────────────────────────────────────────────────

PHI  = (1 + math.sqrt(5)) / 2   # Golden ratio ≈ 1.618...
PI   = math.pi                   # ≈ 3.14159...
E    = math.e                    # Euler's number ≈ 2.718...
SQRT2= math.sqrt(2)              # ≈ 1.414...


# ── φ-sequence timer ──────────────────────────────────────────────────────────

def phi_timer(n: int, base: float = 1.0) -> float:
    """
    Return the nth term of the φ-modulated sequence.

    Produces aperiodic intervals using the golden ratio.
    The sequence never repeats and never forms a simple pattern.

    Args:
        n:    Term index (0-based).
        base: Base multiplier (seconds).

    Returns:
        Interval in seconds.
    """
    # Use the fractional part of n*φ to get equidistributed values
    frac = (n * PHI) % 1.0
    # Map to [0.5, 2.5] range and multiply by base
    return base * (0.5 + 2.0 * frac)


def pi_timer(n: int, base: float = 1.0) -> float:
    """
    Return the nth term of the π-modulated sequence.

    Produces aperiodic intervals using π.
    Used for goal scan timing — a different aperiodic sequence
    than φ so they never synchronize.

    Args:
        n:    Term index (0-based).
        base: Base multiplier.

    Returns:
        Interval.
    """
    frac = (n * PI) % 1.0
    return base * (0.5 + 2.0 * frac)


def e_timer(n: int, base: float = 1.0) -> float:
    """Euler-modulated timer — third independent aperiodic sequence."""
    frac = (n * E) % 1.0
    return base * (0.5 + 2.0 * frac)


# ── Chart-enhanced timer ──────────────────────────────────────────────────────

def chart_modulated_interval(
    base_seconds: float,
    bio: dict,
    sequence: str = "phi",
    n: int = 0,
) -> float:
    """
    Compute a chart-modulated sleep interval.

    Applies biorhythm state as a multiplier to the base interval,
    then adds the irrational φ/π/e sequence on top.

    Args:
        base_seconds: Base interval in seconds.
        bio:          Biorhythm dict from AstrologyCore.
        sequence:     "phi" | "pi" | "e" — which irrational sequence to use.
        n:            Term index in the sequence.

    Returns:
        Final interval in seconds (always positive).
    """
    if not bio:
        # Fall back to pure irrational sequence
        if sequence == "phi":
            return phi_timer(n, base_seconds)
        elif sequence == "pi":
            return pi_timer(n, base_seconds)
        return e_timer(n, base_seconds)

    # Chart modulation multiplier
    mod = _bio_multiplier(bio)

    # Apply modulation to base
    modulated_base = base_seconds * mod

    # Apply irrational sequence on top
    if sequence == "phi":
        return phi_timer(n, modulated_base)
    elif sequence == "pi":
        return pi_timer(n, modulated_base)
    return e_timer(n, modulated_base)


def _bio_multiplier(bio: dict) -> float:
    """
    Compute the chart-derived interval multiplier from biorhythm state.

    Returns a value in [0.4, 1.8]:
        < 1.0 → shorter intervals (more active)
        > 1.0 → longer intervals (more patient)
    """
    physical  = bio.get("physical", 0)
    emotional = bio.get("emotional", 0)
    aesthetic = bio.get("aesthetic", 0)
    intuitive = bio.get("intuitive", 0)

    mod = 1.0

    # Physical PEAK → shorter (urgency, Mars Aries energy)
    if physical > 0.6:
        mod *= 0.65
    elif physical < -0.6:
        mod *= 1.45   # Physical TROUGH → longer (rest, delegation)

    # Emotional PEAK → slightly longer (depth over speed)
    if emotional > 0.6:
        mod *= 1.15

    # Aesthetic PEAK → shorter dream loop intervals
    # (create before the window closes — Venus Pisces MC)
    if aesthetic > 0.7:
        mod *= 0.80

    # Intuitive PEAK → random-ish modification (Jupiter Pisces expands)
    if intuitive > 0.5:
        # Use the intuitive value itself to add unpredictability
        mod *= (0.85 + abs(intuitive) * 0.3)

    return max(0.4, min(1.8, mod))


# ── PlanetaryTimer class ──────────────────────────────────────────────────────

class PlanetaryTimer:
    """
    Stateful timer that generates chart-modulated aperiodic intervals.

    Drop-in replacement for the old IrrationalTimer class.

    Usage:
        timer = PlanetaryTimer(base=3.0, sequence="phi", astro=astro)
        interval = timer.next()  # Returns next interval in seconds
    """

    def __init__(
        self,
        base:     float = 3.0,
        sequence: str   = "phi",
        astro           = None,
        name:     str   = "timer",
    ):
        """
        Args:
            base:     Base interval in seconds.
            sequence: "phi" | "pi" | "e"
            astro:    Optional AstrologyCore for biorhythm modulation.
            name:     Label for logging.
        """
        self.base      = base
        self.sequence  = sequence
        self._astro    = astro
        self.name      = name
        self._n        = 0
        self._bio      = {}
        self._bio_refresh_every = 10  # Refresh bio every 10 calls

    def set_astro(self, astro):
        self._astro = astro

    def next(self) -> float:
        """Return the next aperiodic interval in seconds."""
        # Refresh biorhythm periodically
        if self._n % self._bio_refresh_every == 0 and self._astro:
            try:
                self._bio = self._astro.get_biorhythm()
            except Exception:
                pass

        interval = chart_modulated_interval(
            self.base, self._bio, self.sequence, self._n
        )
        self._n += 1
        log.debug(f"{self.name}: interval={interval:.2f}s (n={self._n})")
        return interval

    def reset(self):
        """Reset the sequence index."""
        self._n = 0

    def peek(self) -> float:
        """Return next interval without advancing the sequence."""
        return chart_modulated_interval(
            self.base, self._bio, self.sequence, self._n
        )


# ── Named timers used by autonomy_loop ───────────────────────────────────────
# These match the old irrational_timers.py exported names exactly.

def make_autonomy_timer(astro=None) -> PlanetaryTimer:
    """Main autonomy loop sleep timer — φ sequence, 3s base."""
    return PlanetaryTimer(base=3.0, sequence="phi", astro=astro, name="autonomy")

def make_goal_scan_timer(astro=None) -> PlanetaryTimer:
    """Goal scan interval — π sequence, 1.5s base."""
    return PlanetaryTimer(base=1.5, sequence="pi", astro=astro, name="goal_scan")

def make_dream_timer(astro=None) -> PlanetaryTimer:
    """Dream loop cycle timer — e sequence, 5s base."""
    return PlanetaryTimer(base=5.0, sequence="e", astro=astro, name="dream")

def make_heartbeat_timer(astro=None) -> PlanetaryTimer:
    """Heartbeat / keep-alive timer — φ sequence, 2s base."""
    return PlanetaryTimer(base=2.0, sequence="phi", astro=astro, name="heartbeat")
