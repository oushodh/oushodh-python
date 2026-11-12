"""The medical text of a medicine."""

from __future__ import annotations

from typing import TypedDict


class Monograph(TypedDict):
    source: str
    indications: str | None
    composition: str | None
    pharmacology: str | None
    dosage: str | None
    interactions: str | None
    contraindications: str | None
    side_effects: str | None
    pregnancy_lactation: str | None
    precautions: str | None
    overdose: str | None
    storage: str | None
