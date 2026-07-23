"""Request-local Anchor publication timings exposed through ``Server-Timing``.

The timings are diagnostic metadata only: they never affect an Anchor's
version binding, replay identity, or publication.  Keeping the accumulator
request-local makes a duplicate request's admission wait distinct from the
owner request's renderer work.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Iterator


ANCHOR_SERVER_TIMING_STAGES = (
    'working-set',
    'gpu-queue',
    'gsplat',
    'contributor-digest',
    'png',
    'json-base64',
)


@dataclass
class AnchorServerTiming:
    """Accumulate the fixed, additive Anchor ``Server-Timing`` phases."""

    _durations_ns: dict[str, int] = field(
        default_factory=lambda: {
            stage: 0 for stage in ANCHOR_SERVER_TIMING_STAGES
        }
    )

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        """Record wall-clock time for one known phase, including failures."""

        if stage not in self._durations_ns:
            raise ValueError(f'unknown Anchor Server-Timing stage: {stage}')
        started_ns = perf_counter_ns()
        try:
            yield
        finally:
            self._durations_ns[stage] += max(0, perf_counter_ns() - started_ns)

    def duration_ms(self, stage: str) -> float:
        """Return one stage duration in the milliseconds required by the header."""

        try:
            duration_ns = self._durations_ns[stage]
        except KeyError as error:
            raise ValueError(f'unknown Anchor Server-Timing stage: {stage}') from error
        return duration_ns / 1_000_000

    def header_value(self) -> str:
        """Return all stages in a deterministic standard ``Server-Timing`` value."""

        return ', '.join(
            f'{stage};dur={self.duration_ms(stage):.3f}'
            for stage in ANCHOR_SERVER_TIMING_STAGES
        )
