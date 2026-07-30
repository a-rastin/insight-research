from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RuntimeRecord:
    key: str
    value: str


class Repository(Protocol):
    """Persistence seam used by the application and its tests."""

    def migrate(self) -> tuple[str, ...]: ...
    def rollback(self, steps: int | None = None) -> tuple[str, ...]: ...
    def ping(self) -> bool: ...
    def put(self, record: RuntimeRecord) -> None: ...
    def get(self, key: str) -> RuntimeRecord | None: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._records: dict[str, RuntimeRecord] = {}
        self.migrated = False

    def migrate(self) -> tuple[str, ...]:
        if self.migrated:
            return ()
        self.migrated = True
        return ("in-memory",)

    def rollback(self, steps: int | None = None) -> tuple[str, ...]:
        if steps is not None and steps < 0:
            raise ValueError("steps cannot be negative")
        changed = ("in-memory",) if self.migrated and steps != 0 else ()
        if steps != 0:
            self._records.clear()
            self.migrated = False
        return changed

    def ping(self) -> bool:
        return self.migrated

    def put(self, record: RuntimeRecord) -> None:
        self._records[record.key] = record

    def get(self, key: str) -> RuntimeRecord | None:
        return self._records.get(key)
