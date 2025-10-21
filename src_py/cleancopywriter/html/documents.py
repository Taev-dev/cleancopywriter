from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from cleancopy import Abstractifier
from cleancopy import parse
from cleancopy.ast import Document

from cleancopywriter.html.writer import HtmlWriter


@dataclass(slots=True, kw_only=True)
class HtmlDocumentCollection:
    # TODO: need to decide how this should work with other output types
    # (ie, writers other than html)
    writer: HtmlWriter = field(default_factory=HtmlWriter)
    abstractifier: Abstractifier = field(default_factory=Abstractifier)

    def preprocess(self, *, clc_text: bytes | str) -> Document:
        """Applies any cleancopy tree transformers and returns the
        resulting cleancopy document AST.
        """
        if isinstance(clc_text, str):
            clc_text = clc_text.encode('utf-8')

        cst_doc = parse(clc_text)
        # TODO: we'll need to apply transformers after conversion but before
        # returning!
        return self.abstractifier.convert(cst_doc)
