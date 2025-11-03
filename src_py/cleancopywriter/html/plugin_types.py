from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated
from typing import Protocol

from cleancopy.ast import ASTNode
from cleancopy.ast import EmbeddingBlockNode
from docnote import Note
from docnote_extract.summaries import SummaryBase
from templatey._types import TemplateParamsInstance

from cleancopywriter.html.generic_templates import HtmlAttr


class PluginManager(Protocol):

    def get_embeddings_plugins(
            self,
            embedding_type: Annotated[
                str,
                Note('''This is the string embed type -- in other words,
                    the string value that was passed under the
                    ``__embed__`` key in the cleancopy node.''')]
            ) -> Sequence[EmbeddingsPlugin]:
        ...

    def get_clc_plugins(
            self,
            node_type: type[ASTNode]
            ) -> Sequence[ClcPlugin]:
        ...

    def get_docnotes_plugins(
            self,
            summary_type: type[SummaryBase]
            ) -> Sequence[DocnotesPlugin]:
        ...


class EmbeddingsPlugin(Protocol):
    """Embeddings plugins can be used to implement special behavior for
    ``__embed__`` nodes. These will completely replace the typical
    fallback behavior, allowing you to inject arbitrary content into the
    rendered document.

    Note that unlike ``ClcPlugin``s and ``DocnotesPlugin``s, embeddings
    plugins are applied on a short-circuiting basis. In other words, all
    possible plugins for a particular embed type are called in order,
    and the first one to return a non-None result is applied, and the
    rest skipped.
    """
    plugin_name: str

    def __call__(
            self,
            node: EmbeddingBlockNode,
            embedding_type: str,
            ) -> PluginInjection | None: ...


class ClcPlugin(Protocol):
    """Plugins can be used to inject extra functionality into the
    templates used for rendering objects.

    Returning a value of None indicates that no injection should be
    performed. This is equivalent to an empty ``PluginInjection``.

    Note that plugins are cumulative; more than one plugin can add
    injections to the template associated with a particular node.
    """

    def __call__(self, node: ASTNode) -> PluginInjection | None: ...


class DocnotesPlugin(Protocol):
    """Plugins can be used to inject extra functionality into the
    templates used for rendering objects.

    Returning a value of None indicates that no injection should be
    performed. This is equivalent to an empty ``PluginInjection``.

    Note that plugins are cumulative; more than one plugin can add
    injections to the template associated with a particular node.
    """

    def __call__(self, summary: SummaryBase) -> PluginInjection | None: ...


@dataclass(slots=True)
class PluginInjection:
    widgets: Sequence[TemplateParamsInstance] | None = None
    attrs: Sequence[HtmlAttr] | None = None
