from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyParamSpec:
    name: str
    label: str
    type: str
    default: Any


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    description: str
    strategy_class: type
    params: tuple[StrategyParamSpec, ...]
    required_data: tuple[str, ...] = field(default_factory=tuple)

    @property
    def defaults(self) -> dict[str, Any]:
        return {p.name: p.default for p in self.params}
