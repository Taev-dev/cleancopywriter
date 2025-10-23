from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import overload

from cleancopy import Abstractifier
from cleancopy import parse
from cleancopy.ast import Document as ClcDocument
from docnote_extract import SummaryTreeNode
from templatey._types import TemplateParamsInstance

from cleancopywriter._types import DocumentBase
from cleancopywriter._types import DocumentID
from cleancopywriter.html.templates import ModuleSummaryTemplate
from cleancopywriter.html.writer import HtmlWriter


@dataclass(slots=True)
class HtmlDocument[TI: DocumentID, TS](
        DocumentBase[TI, TS, TemplateParamsInstance]):
    """This is used as a base class for all supported html document
    types.
    """


@dataclass(slots=True)
class DocnoteHtmlDocument[TI: DocumentID](HtmlDocument[TI, SummaryTreeNode]):
    """This is used for all documents constructed from a docnote
    extraction.
    """


@dataclass(slots=True)
class ClcHtmlDocument[TI: DocumentID](HtmlDocument[TI, ClcDocument]):
    """This is used for all documents constructed from a cleancopy
    document.
    """


@dataclass(slots=True)
class _ProxyViewDescriptor:
    """This is a bit of a hack. The goal here is to allow dataclasses
    to include generated views into things **as part of their repr**.
    The general strategy is to use a non-init field as a proxy to the
    view_builder attribute.

    Instead of using a [[descriptor-typed
    field](https://docs.python.org/3/library/dataclasses.html#descriptor-typed-fields)]
    -- which cannot be assigned init=False -- we simply set the field
    as normal, allow the dataclass to be processed, **and then**
    overwrite the field with the descriptor.
    """
    view_builder: Callable[[Any], Any]

    def __get__(self, obj: Any | None, objtype: type | None = None):
        if obj is None:
            return '...'
        elif objtype is None:
            return '...'
        else:
            return self.view_builder(obj)


@dataclass(slots=True, kw_only=True)
class HtmlDocumentCollection[T: DocumentID](Mapping[T, HtmlDocument]):
    # TODO: need to decide how this should work with other output types
    # (ie, writers other than html)
    writer: HtmlWriter = field(default_factory=HtmlWriter)
    abstractifier: Abstractifier = field(default_factory=Abstractifier)

    _documents: dict[T, HtmlDocument] = field(default_factory=dict, repr=False)
    # This gets replaced by a _ProxyViewDescriptor!
    documents: tuple[T, ...] = field(init=False)

    def preprocess(self, *, clc_text: bytes | str) -> ClcDocument:
        """Applies any cleancopy tree transformers and returns the
        resulting cleancopy document AST.
        """
        if isinstance(clc_text, str):
            clc_text = clc_text.encode('utf-8')

        cst_doc = parse(clc_text)
        # TODO: we'll need to apply transformers after conversion but before
        # returning!
        return self.abstractifier.convert(cst_doc)

    @overload
    def add(self, id_: T, *, docnote_src: SummaryTreeNode) -> None: ...
    @overload
    def add(self, id_: T, *, clc_src: ClcDocument) -> None: ...

    def add(
            self,
            id_: T,
            *,
            docnote_src: SummaryTreeNode | None = None,
            clc_src: ClcDocument | None = None
            ) -> None:
        """Constructs a document from the passed source object and adds
        it to the collection.
        """
        if id_ in self._documents:
            raise ValueError('Duplicate document ID!', id_)

        if (
            docnote_src is not None
            # We're anticipating adding more document types here, hence the
            # all() instead of a simple singular ``is None`` check
            and all(alt_src is None for alt_src in (clc_src,))
        ):
            self._documents[id_] = DocnoteHtmlDocument(
                id_=id_,
                src=docnote_src,
                intermediate_representation=ModuleSummaryTemplate.from_summary(
                    docnote_src.module_summary,
                    self))

        elif (
            clc_src is not None
            # We're anticipating adding more document types here, hence the
            # all() instead of a simple singular ``is None`` check
            and all(alt_src is None for alt_src in (docnote_src,))
        ):
            templatified = self.writer.write_document(clc_src)
            if len(templatified) != 1:
                raise RuntimeError(
                    'Impossible branch: multiple root nodes for written clc '
                    + 'document!', clc_src)

            self._documents[id_] = ClcHtmlDocument(
                id_=id_,
                src=clc_src,
                intermediate_representation=templatified[0])

        else:
            raise TypeError(
                'Can only specify one document source when adding to a '
                + 'collection!')

    def __contains__(self, id_: object) -> bool:
        return id_ in self._documents

    def __getitem__(self, id_: T) -> HtmlDocument:
        return self._documents[id_]

    def __iter__(self) -> Iterator[T]:
        return iter(self._documents)

    def __len__(self) -> int:
        return len(self._documents)

    @overload
    def get(self, key: T, /) -> HtmlDocument | None: ...
    @overload
    def get[TD](self, key: T, /, default: TD) -> TD | HtmlDocument: ...

    def get(self, key: T, /, default: object | None = None):
        return self._documents.get(key, default)

HtmlDocumentCollection.documents = _ProxyViewDescriptor(
    view_builder=lambda doc_coll: tuple(doc_coll._documents))  # type: ignore
