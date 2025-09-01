from __future__ import annotations

from functools import singledispatchmethod
from typing import Protocol

from cleancopy.ast import ASTNode


class DocWriter[T](Protocol):

    @singledispatchmethod
    def write_node(self, node: ASTNode) -> T:
        """This must implement writing / rendering for all AST node
        types.
        """
        ...
