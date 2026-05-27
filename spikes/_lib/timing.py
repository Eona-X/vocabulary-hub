from __future__ import annotations

import gc
import time
from dataclasses import dataclass
from statistics import median
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class Timing:
    samples_s: list[float]
    timed_out: bool = False

    @property
    def n(self) -> int:
        return len(self.samples_s)

    @property
    def best_s(self) -> float:
        return min(self.samples_s) if self.samples_s else float("inf")

    @property
    def p50_s(self) -> float:
        return median(self.samples_s) if self.samples_s else float("inf")

    @property
    def p95_s(self) -> float:
        if not self.samples_s:
            return float("inf")
        s = sorted(self.samples_s)
        k = max(0, int(round(0.95 * len(s))) - 1)
        return s[k]

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "best_s": self.best_s,
            "p50_s": self.p50_s,
            "p95_s": self.p95_s,
            "samples_s": self.samples_s,
            "timed_out": self.timed_out,
        }


def time_once(fn: Callable[[], T]) -> tuple[T, float]:
    gc.collect()
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def time_best_of(
    fn: Callable[[], T],
    n: int = 3,
    warmup: int = 1,
    timeout_s: float | None = None,
) -> tuple[T | None, Timing]:
    """Best-of-N timing. If a sample (or the warmup) takes longer than timeout_s,
    abort further samples and mark the Timing as timed_out (best-effort — the
    current call is not interrupted)."""
    last: T | None = None
    samples: list[float] = []

    for _ in range(warmup):
        last, dt = time_once(fn)
        if timeout_s is not None and dt > timeout_s:
            return last, Timing(samples_s=[dt], timed_out=True)

    for _ in range(n):
        last, dt = time_once(fn)
        samples.append(dt)
        if timeout_s is not None and dt > timeout_s:
            return last, Timing(samples_s=samples, timed_out=True)

    return last, Timing(samples_s=samples)
