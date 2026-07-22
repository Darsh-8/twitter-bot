from dataclasses import dataclass


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _clamp01(self.value))

    def meets(self, threshold: float) -> bool:
        return self.value >= threshold


@dataclass(frozen=True, slots=True)
class ImportanceScore:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _clamp01(self.value))

    def meets(self, threshold: float) -> bool:
        return self.value >= threshold


EmbeddingVector = list[float]
