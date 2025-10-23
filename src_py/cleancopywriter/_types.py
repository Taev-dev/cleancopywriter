from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

type DocumentID = Hashable


@dataclass(slots=True)
class DocumentBase[TI: DocumentID, TS, TIR]:
    id_: TI
    src: TS
    intermediate_representation: TIR
