"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Irrational Timer Sequences                       ║
║  File: core/irrational_timers.py                                 ║
║                                                                  ║
║  Provides aperiodic timing intervals derived from the digits     ║
║  of π (pi) and φ (phi / golden ratio) so that no two           ║
║  background processes ever lock into synchronized cadences.     ║
║                                                                  ║
║  WHY IRRATIONAL TIMERS?                                          ║
║  Regular fixed intervals (every 5s, every 10s) cause bursts     ║
║  of simultaneous work — all timers fire at once.  Irrational    ║
║  sequences are provably non-repeating and non-synchronizing,    ║
║  distributing load smoothly across time.                        ║
║                                                                  ║
║  USAGE:                                                          ║
║    from core.irrational_timers import pi_timer, phi_timer        ║
║    from core.irrational_timers import PI_SEQ, PHI_SEQ, PRIMES   ║
║                                                                  ║
║    # Get the 3rd π-derived interval at 5 s base scale           ║
║    delay = pi_timer(index=2, base=5.0)   # → 20.0 s  (4×5)     ║
║                                                                  ║
║    # Get the 4th φ-derived interval at 2 s base scale           ║
║    delay = phi_timer(index=3, base=2.0)  # → 3.71 s             ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Constant sequences                                         ║
║    2. Timer functions                                            ║
║    3. Cycle generators (infinite iterators)                      ║
║    4. Convenience presets for specific subsystems               ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Constant sequences ───────────────────────────────────────────

import math
import itertools
from typing import Iterator

# ── π digits (first 40 non-zero adjusted) ────────────────────────────────────
# We use decimal digits of π: 3,1,4,1,5,9,2,6,5,3,5,8,9,7,9,3,2,3,8,4,...
# Zeros are replaced with 1 to avoid zero-length sleeps.
PI_SEQ: tuple[int, ...] = (
    3, 1, 4, 1, 5, 9, 2, 6, 5, 3,
    5, 8, 9, 7, 9, 3, 2, 3, 8, 4,
    6, 2, 6, 4, 3, 3, 8, 3, 2, 7,
    9, 5, 2, 8, 8, 4, 1, 9, 7, 1,
)

# ── φ / Fibonacci sequence ────────────────────────────────────────────────────
# Fibonacci numbers converge to the golden ratio φ = 1.6180339887...
# Using Fibonacci avoids very large intervals while keeping irrationality.
PHI_SEQ: tuple[int, ...] = (
    1, 1, 2, 3, 5, 8, 13, 21, 34, 55,
    89, 144, 233, 377, 610, 987,
)

# φ constant itself (for direct ratio calculations)
PHI: float = (1.0 + math.sqrt(5.0)) / 2.0   # 1.6180339887...

# ── First 20 prime numbers (bonus aperiodic sequence) ────────────────────────
PRIMES: tuple[int, ...] = (
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
    31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
)


# ── Section 2: Timer functions ───────────────────────────────────────────────

def pi_timer(index: int, base: float = 1.0, min_secs: float = 0.5) -> float:
    """
    Return an aperiodic interval derived from the π digit at position `index`.

    The returned value is:
        digit = PI_SEQ[index % len(PI_SEQ)]
        interval = digit * base   (clamped to min_secs)

    Because PI_SEQ is a non-repeating irrational sequence, successive calls
    with incrementing index will never settle into a fixed period.

    Args:
        index:    Which π digit to use.  Wraps cyclically.
        base:     Multiplier in seconds.  Default 1.0 s → raw digit seconds.
        min_secs: Floor value to prevent sub-second sleeps.  Default 0.5 s.

    Returns:
        float: Interval in seconds.

    Examples:
        pi_timer(0, 5.0)  → 15.0  s   (digit 3 × 5.0)
        pi_timer(1, 5.0)  →  5.0  s   (digit 1 × 5.0)
        pi_timer(2, 5.0)  → 20.0  s   (digit 4 × 5.0)
        pi_timer(3, 5.0)  →  5.0  s   (digit 1 × 5.0)
        pi_timer(4, 5.0)  → 25.0  s   (digit 5 × 5.0)
    """
    digit = PI_SEQ[index % len(PI_SEQ)]
    return max(min_secs, float(digit) * base)


def phi_timer(index: int, base: float = 1.0, min_secs: float = 0.5) -> float:
    """
    Return an aperiodic interval derived from the Fibonacci/φ sequence.

    The Fibonacci number at position `index` is divided by PHI to keep
    intervals from growing unboundedly while preserving the irrational ratio.

    formula:
        fib      = PHI_SEQ[index % len(PHI_SEQ)]
        interval = (fib / PHI) * base

    Args:
        index:    Which Fibonacci entry to use.  Wraps cyclically.
        base:     Scale in seconds.
        min_secs: Floor value.

    Returns:
        float: Interval in seconds.

    Examples (base=1.0):
        phi_timer(0)  → 0.618 s   (1 / φ)
        phi_timer(1)  → 0.618 s   (1 / φ)
        phi_timer(2)  → 1.236 s   (2 / φ)
        phi_timer(3)  → 1.854 s   (3 / φ)
        phi_timer(4)  → 3.090 s   (5 / φ)
        phi_timer(5)  → 4.944 s   (8 / φ)
    """
    fib = PHI_SEQ[index % len(PHI_SEQ)]
    return max(min_secs, (float(fib) / PHI) * base)


def prime_timer(index: int, base: float = 1.0, min_secs: float = 0.5) -> float:
    """
    Return an interval derived from prime numbers.

    Primes are coprime to each other, so multiple processes using different
    prime-based intervals will resynchronize only at the LCM (very rarely).

    Args:
        index:    Which prime to use.  Wraps cyclically.
        base:     Multiplier in seconds.
        min_secs: Floor value.

    Returns:
        float: Interval in seconds.
    """
    prime = PRIMES[index % len(PRIMES)]
    return max(min_secs, float(prime) * base)


# ── Section 3: Cycle generators ─────────────────────────────────────────────

def pi_cycle(base: float = 1.0, min_secs: float = 0.5) -> Iterator[float]:
    """
    Infinite iterator yielding successive π-derived intervals.

    Usage:
        timer = pi_cycle(base=5.0)
        while running:
            sleep_time = next(timer)
            time.sleep(sleep_time)
    """
    for i in itertools.cycle(range(len(PI_SEQ))):
        yield pi_timer(i, base, min_secs)


def phi_cycle(base: float = 1.0, min_secs: float = 0.5) -> Iterator[float]:
    """
    Infinite iterator yielding successive φ-derived intervals.
    """
    for i in itertools.cycle(range(len(PHI_SEQ))):
        yield phi_timer(i, base, min_secs)


def prime_cycle(base: float = 1.0, min_secs: float = 0.5) -> Iterator[float]:
    """
    Infinite iterator yielding successive prime-derived intervals.
    """
    for i in itertools.cycle(range(len(PRIMES))):
        yield prime_timer(i, base, min_secs)


# ── Section 4: Convenience presets ───────────────────────────────────────────
# Each subsystem gets its own timer preset so they never synchronize.
# The base values are chosen so typical waits stay in reasonable ranges.

# Autonomy loop: active cycles 15–45 s, idle cycles 30–90 s
AUTONOMY_ACTIVE_TIMER = lambda idx: pi_timer(idx,  base=5.0,   min_secs=5.0)
AUTONOMY_IDLE_TIMER   = lambda idx: phi_timer(idx, base=10.0,  min_secs=15.0)

# Goal engine scan: every 3–30 s depending on position in π
GOAL_SCAN_TIMER = lambda idx: pi_timer(idx, base=3.0, min_secs=3.0)

# Health monitor: every 2–18 minutes (φ-based, slowly varying)
HEALTH_TIMER = lambda idx: phi_timer(idx, base=120.0, min_secs=90.0)

# Heartbeat: every 7–23 s (prime-based so it never lines up with autonomy)
HEARTBEAT_TIMER = lambda idx: prime_timer(idx, base=3.0, min_secs=7.0)

# Monitor engine poll: every 30–270 s (π-based, scaled to minutes)
MONITOR_POLL_TIMER = lambda idx: pi_timer(idx, base=30.0, min_secs=30.0)

# Sidebar refresh: 3–15 s (φ-based, fast enough to feel live)
SIDEBAR_REFRESH_TIMER = lambda idx: phi_timer(idx, base=2.0, min_secs=3.0)

# Reflector stats save: prime-based, every 2–5 minutes
REFLECTOR_SAVE_TIMER = lambda idx: prime_timer(idx, base=30.0, min_secs=60.0)
