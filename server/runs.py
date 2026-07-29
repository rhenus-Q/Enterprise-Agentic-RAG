"""Bounded, thread-safe, metadata-only run history."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from copy import deepcopy
from threading import Lock
from typing import Any

from server.schemas import RunDetail, RunSummary

RUN_HISTORY_LIMIT = 50


class RunStore:
    """Keep recent run records in memory, newest record last."""

    def __init__(self, limit: int = RUN_HISTORY_LIMIT) -> None:
        self._records: deque[dict[str, Any]] = deque(maxlen=limit)
        self._by_run_id: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    @property
    def limit(self) -> int:
        """Maximum number of records retained."""

        maxlen = self._records.maxlen
        assert maxlen is not None
        return maxlen

    def add(self, record: Mapping[str, Any] | RunDetail) -> None:
        """Validate and append a metadata-only run record."""

        detail = RunDetail.model_validate(record).model_dump()
        run_id = detail["run_id"]

        with self._lock:
            existing = self._by_run_id.pop(run_id, None)
            if existing is not None:
                self._records.remove(existing)

            if len(self._records) == self.limit:
                evicted = self._records[0]
                self._by_run_id.pop(evicted["run_id"], None)

            self._records.append(detail)
            self._by_run_id[run_id] = detail

    def list_summaries(self) -> list[dict[str, Any]]:
        """Return newest-first public summaries."""

        with self._lock:
            return [
                RunSummary.model_validate(record).model_dump() for record in reversed(self._records)
            ]

    def get(self, run_id: str) -> dict[str, Any] | None:
        """Return a detached run detail record, or None when it is unknown."""

        with self._lock:
            record = self._by_run_id.get(run_id)
            return deepcopy(record) if record is not None else None
