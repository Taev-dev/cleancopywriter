from __future__ import annotations

from dataclasses import dataclass
from functools import singledispatchmethod
from typing import cast

from cleancopy import Abstractifier
from cleancopy import parse
from cleancopy.ast import Annotation
from cleancopy.ast import ASTNode
from cleancopy.ast import Document
from cleancopy.ast import EmbeddingBlockNode
from cleancopy.ast import InlineNodeInfo
from cleancopy.ast import LinkTarget
from cleancopy.ast import List_
from cleancopy.ast import ListItem
from cleancopy.ast import Paragraph
from cleancopy.ast import RichtextBlockNode
from cleancopy.ast import RichtextInlineNode
from cleancopy.ast import StrDataType
from cleancopy.spectypes import ListType
from templatey.environments import RenderEnvironment
from templatey.prebaked.loaders import InlineStringTemplateLoader

from cleancopywriter.html.factories import formatting_factory
from cleancopywriter.html.factories import heading_factory
from cleancopywriter.html.factories import link_factory
from cleancopywriter.html.factories import listitem_factory
from cleancopywriter.html.templates import HtmlGenericElement
from cleancopywriter.html.templates import HtmlTemplate
from cleancopywriter.html.templates import PlaintextTemplate
from cleancopywriter.writers import DocWriter


@dataclass(slots=True)
class HtmlWriter(DocWriter[list[HtmlTemplate]]):

    @singledispatchmethod
    def write_node(self, node: ASTNode) -> list[HtmlTemplate]:
        raise NotImplementedError('That node type not yet supported!', node)

    @write_node.register
    def write_document(self, node: Document) -> list[HtmlTemplate]:
        sections: list[HtmlTemplate] = []
        if node.title is not None:
            sections.append(
                heading_factory(depth=0, body=self.write_node(node.title)))

        sections.extend(self.write_node(node.root))

        return [HtmlGenericElement(tag='article', body=sections)]

    @write_node.register
    def write_richtext_block(
            self,
            node: RichtextBlockNode
            ) -> list[HtmlTemplate]:
        body: list[HtmlTemplate] = []
        if node.title is not None:
            body.append(
                heading_factory(
                    depth=node.depth, body=self.write_node(node.title)))

        for paragraph_or_node in node.content:
            body.extend(self.write_node(paragraph_or_node))

        # What we're trying to avoid here is **always** having nested sections
        # within a document.
        if node.depth > 0:
            return [HtmlGenericElement(tag='section', body=body)]
        else:
            return body

    @write_node.register
    def write_embedding_block(
            self,
            node: EmbeddingBlockNode
            ) -> list[HtmlTemplate]:
        body: list[HtmlTemplate] = []
        if node.title is not None:
            body.append(
                heading_factory(
                    depth=node.depth, body=self.write_node(node.title)))
        if node.content is not None:
            body.append(
                HtmlGenericElement(
                    tag='pre',
                    body=[PlaintextTemplate(text=node.content)]))

        return [HtmlGenericElement(tag='section', body=body)]

    @write_node.register
    def write_paragraph(
            self,
            node: Paragraph
            ) -> list[HtmlTemplate]:
        body: list[HtmlTemplate] = []
        for nested in node.content:
            body.extend(self.write_node(nested))

        return [HtmlGenericElement(tag='p', body=body)]

    @write_node.register
    def write_list_node(
            self,
            node: List_
            ) -> list[HtmlTemplate]:
        body: list[HtmlTemplate] = []
        for nested in node.content:
            body.extend(self.write_node(nested))

        if node.type_ is ListType.ORDERED:
            tag = 'ol'
        else:
            tag = 'ul'

        return [HtmlGenericElement(tag=tag, body=body)]

    @write_node.register
    def write_listitem_node(
            self,
            node: ListItem
            ) -> list[HtmlTemplate]:
        body: list[HtmlTemplate] = []
        for nested in node.content:
            body.extend(self.write_node(nested))

        return [listitem_factory(node.index, body)]

    @write_node.register
    def write_richtext_inline(
            self,
            node: RichtextInlineNode
            ) -> list[HtmlTemplate]:
        contained_content: list[HtmlTemplate] = []
        for content_segment in node.content:
            if isinstance(content_segment, str):
                contained_content.append(
                    PlaintextTemplate(text=content_segment))
            else:
                contained_content.extend(self.write_node(content_segment))

        info = node.info
        if info is None:
            return contained_content
        else:
            return _wrap_in_richtext_context(
                contained_content,
                cast(InlineNodeInfo, info))

    @write_node.register
    def write_annotation_node(self, node: Annotation) -> list[HtmlTemplate]:
        return []


    def quickrender(self, clc_text: str) -> str:
        """This is a utility function, mostly intended for manual
        debugging and repl tomfoolery, that renders the passed cleancopy
        text into HTML.
        """
        cst_doc = parse(clc_text.encode('utf-8'))
        ast_doc = Abstractifier().convert(cst_doc)
        templates = self.write_node(ast_doc)
        render_env = RenderEnvironment(InlineStringTemplateLoader())
        return render_env.render_sync(templates[0])


def _wrap_in_richtext_context(
        contained_content: list[HtmlTemplate],
        info: InlineNodeInfo
        ) -> list[HtmlTemplate]:
    if info.formatting is not None:
        contained_content = [formatting_factory(
                info.formatting,
                contained_content)]

    if info.target is None:
        return contained_content
    else:
        return [link_factory(
            href=_stringify_link_target(info.target),
            body=contained_content)]


def _stringify_link_target(target: LinkTarget) -> str:
    if isinstance(target, StrDataType):
        return target.value
    else:
        print(target)
        raise NotImplementedError(
            'That link target type is not yet supported', target)
