from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field

from cleancopy.ast import ASTNode
from docnote_extract.summaries import SummaryBase

from cleancopywriter.html.plugin_types import ClcPlugin
from cleancopywriter.html.plugin_types import DocnotesPlugin
from cleancopywriter.html.plugin_types import EmbeddingsPlugin
from cleancopywriter.html.plugin_types import PluginManager


@dataclass(slots=True)
class SimplePluginManager(PluginManager):
    """``SimplePluginManagers`` perform no special logic for determining
    if plugins can be used for a particular node type; they simply
    assume all plugins for a given domain (cleancopy, docnotes, and
    embeddings) can be used on any node type, and return the full list
    of plugins every time.
    """
    embeddings_plugins: Sequence[EmbeddingsPlugin] = field(
        default_factory=list)
    clc_plugins: Sequence[ClcPlugin] = field(default_factory=list)
    docnotes_plugins: Sequence[DocnotesPlugin] = field(
        default_factory=list)

    def get_clc_plugins(
            self,
            node_type: type[ASTNode]
            ) -> Sequence[ClcPlugin]:
        return self.clc_plugins

    def get_docnotes_plugins(
            self,
            summary_type: type[SummaryBase]
            ) -> Sequence[DocnotesPlugin]:
        return self.docnotes_plugins

    def get_embeddings_plugins(
            self,
            embedding_type: str
            ) -> Sequence[EmbeddingsPlugin]:
        return self.embeddings_plugins
