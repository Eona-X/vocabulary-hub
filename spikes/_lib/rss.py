from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

import psutil


@dataclass
class RssSample:
    peak_bytes: int
    baseline_bytes: int

    @property
    def delta_bytes(self) -> int:
        return max(0, self.peak_bytes - self.baseline_bytes)


class _PeakSampler:
    def __init__(self, pid: int, interval_s: float, include_children: bool):
        self.proc = psutil.Process(pid)
        self.interval = interval_s
        self.include_children = include_children
        self.peak = 0
        self.baseline = 0
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def _read(self) -> int:
        try:
            rss = self.proc.memory_info().rss
            if self.include_children:
                for c in self.proc.children(recursive=True):
                    try:
                        rss += c.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            return rss
        except psutil.NoSuchProcess:
            return 0

    def _loop(self) -> None:
        while not self._stop.is_set():
            rss = self._read()
            if rss > self.peak:
                self.peak = rss
            self._stop.wait(self.interval)
        # final read in case the work spiked between ticks
        rss = self._read()
        if rss > self.peak:
            self.peak = rss

    def start(self) -> None:
        self.baseline = self._read()
        self.peak = self.baseline
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self) -> RssSample:
        self._stop.set()
        if self._t is not None:
            self._t.join()
        return RssSample(peak_bytes=self.peak, baseline_bytes=self.baseline)


@contextmanager
def sample_peak_rss(pid: int | None = None, interval_s: float = 0.05, include_children: bool = True):
    s = _PeakSampler(pid or os.getpid(), interval_s, include_children)
    s.start()
    try:
        yield lambda: RssSample(peak_bytes=s.peak, baseline_bytes=s.baseline)
    finally:
        # caller can read the sample via the yielded callable; final value stored below
        s.stop()


def measure_peak_rss(fn, pid: int | None = None, interval_s: float = 0.05, include_children: bool = True) -> tuple[object, RssSample]:
    s = _PeakSampler(pid or os.getpid(), interval_s, include_children)
    s.start()
    try:
        out = fn()
    finally:
        sample = s.stop()
    return out, sample
