from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

from cleancopy.ast import MentionDataType
from cleancopy.ast import ReferenceDataType
from cleancopy.ast import TagDataType
from cleancopy.ast import VariableDataType

type DocumentID = Hashable


@dataclass(slots=True)
class DocumentBase[TI: DocumentID, TS, TIR]:
    id_: TI
    src: TS
    intermediate_representation: TIR


class LinkTargetResolver(Protocol):
    """Mentions, tags, variables, and references can be used arbitrarily
    within metadata, which are then left up to plugins to handle.
    However, when used as the ``__target__`` of a link, the link target
    resolver is called to convert the value into a URL.
    """

    def __call__(
            self,
            target:
                MentionDataType
                | TagDataType
                | VariableDataType
                | ReferenceDataType
            ) -> str:
        ...
