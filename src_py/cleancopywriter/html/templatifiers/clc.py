from __future__ import annotations

import typing
from functools import singledispatch
from typing import cast

from cleancopy.ast import Annotation
from cleancopy.ast import ASTNode
from cleancopy.ast import Document
from cleancopy.ast import EmbeddingBlockNode
from cleancopy.ast import InlineNodeInfo
from cleancopy.ast import LinkTarget
from cleancopy.ast import List_
from cleancopy.ast import ListItem
from cleancopy.ast import MentionDataType
from cleancopy.ast import Paragraph
from cleancopy.ast import ReferenceDataType
from cleancopy.ast import RichtextBlockNode
from cleancopy.ast import RichtextInlineNode
from cleancopy.ast import StrDataType
from cleancopy.ast import TagDataType
from cleancopy.ast import VariableDataType
from cleancopy.spectypes import InlineFormatting
from cleancopy.spectypes import ListType

from cleancopywriter.html.generic_templates import HtmlAttr
from cleancopywriter.html.generic_templates import HtmlGenericElement
from cleancopywriter.html.generic_templates import HtmlTemplate
from cleancopywriter.html.generic_templates import PlaintextTemplate
from cleancopywriter.html.generic_templates import heading_factory
from cleancopywriter.html.generic_templates import link_factory
from cleancopywriter.html.generic_templates import listitem_factory

if typing.TYPE_CHECKING:
    from cleancopywriter.html.documents import HtmlDocumentCollection
else:
    # We do this to make the @singledispatch work at runtime even though the
    # document collection isn't defined
    HtmlDocumentCollection = object

UNDERLINE_TAGNAME = 'clc-ul'
INLINE_PRE_CLASSNAME = 'clc-fmt-pre'


def formatting_factory(
        spectype: InlineFormatting,
        body: list[HtmlTemplate]
        ) -> HtmlGenericElement:
    if spectype is InlineFormatting.PRE:
        tag = 'code'
        attrs = [HtmlAttr(key='class', value=INLINE_PRE_CLASSNAME)]

    elif spectype is InlineFormatting.UNDERLINE:
        tag = UNDERLINE_TAGNAME
        attrs = []

    elif spectype is InlineFormatting.STRONG:
        tag = 'strong'
        attrs = []

    elif spectype is InlineFormatting.EMPHASIS:
        tag = 'em'
        attrs = []

    elif spectype is InlineFormatting.STRIKE:
        tag = 's'
        attrs = []

    else:
        raise TypeError(
            'Invalid spectype for inline formatting!', spectype)

    return HtmlGenericElement(
        tag=tag,
        attrs=attrs,
        body=body)


@singledispatch
def templatify_node(
        node: ASTNode,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    raise NotImplementedError('That node type not yet supported!', node)


@templatify_node.register
def templatify_document(
        node: Document,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    sections: list[HtmlTemplate] = []
    if node.title is not None:
        sections.append(
            heading_factory(
                depth=0,
                body=templatify_node(node.title, doc_coll=doc_coll)))

    sections.extend(templatify_node(node.root, doc_coll=doc_coll))

    return [
        HtmlGenericElement(
            tag='clc-doc',
            body=sections,
            attrs=[HtmlAttr(key='role', value='article')])]


@templatify_node.register
def templatify_richtext_block(
        node: RichtextBlockNode,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    body: list[HtmlTemplate] = []
    if node.title is not None:
        body.append(
            heading_factory(
                depth=node.depth,
                body=templatify_node(node.title, doc_coll=doc_coll)))

    for paragraph_or_node in node.content:
        body.extend(templatify_node(paragraph_or_node, doc_coll=doc_coll))

    # What we're trying to avoid here is **always** having nested sections
    # within a document.
    if node.depth > 0:
        return [HtmlGenericElement(tag='clc-block', body=body)]
    else:
        return body


@templatify_node.register
def templatify_embedding_block(
        node: EmbeddingBlockNode,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    body: list[HtmlTemplate] = []
    if node.title is not None:
        body.append(
            heading_factory(
                depth=node.depth,
                body=templatify_node(node.title, doc_coll=doc_coll)))
    if node.content is not None:
        body.append(
            HtmlGenericElement(
                tag='pre',
                body=[PlaintextTemplate(text=node.content)]))

    return [HtmlGenericElement(tag='clc-block', body=body)]


@templatify_node.register
def templatify_paragraph(
        node: Paragraph,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    body: list[HtmlTemplate] = []
    for nested in node.content:
        if isinstance(nested, RichtextInlineNode):
            # We want to wrap these in standard <p> tags, and this is the
            # only easy place to do so (especially since we use inline
            # richtext within titles, and <p> isn't valid within <h#>)
            body.append(
                HtmlGenericElement(
                    tag='p',
                    body=templatify_node(nested, doc_coll=doc_coll)))

        else:
            body.extend(templatify_node(nested, doc_coll=doc_coll))

    # Notes:
    #   ++  because we have <ul>/<ol> next to <p> within the same cleancopy
    #       paragraph, and because both list tags in HTML are invalid
    #       inside paragraphs, we need to use a custom tag
    #   ++  this will inherit from HtmlGenericElement, which has the same
    #       API surface as a normal div
    #   ++  this can be styled as desired
    return [HtmlGenericElement(tag='clc-p', body=body)]


@templatify_node.register
def templatify_list_node(
        node: List_,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    body: list[HtmlTemplate] = []
    for nested in node.content:
        body.extend(templatify_node(nested, doc_coll=doc_coll))

    if node.type_ is ListType.ORDERED:
        tag = 'ol'
    else:
        tag = 'ul'

    return [HtmlGenericElement(tag=tag, body=body)]


@templatify_node.register
def templatify_listitem_node(
        node: ListItem,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    body: list[HtmlTemplate] = []
    for nested in node.content:
        body.extend(templatify_node(nested, doc_coll=doc_coll))

    return [listitem_factory(node.index, body)]


@templatify_node.register
def templatify_richtext_inline(
        node: RichtextInlineNode,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    contained_content: list[HtmlTemplate] = []
    for content_segment in node.content:
        if isinstance(content_segment, str):
            contained_content.append(
                PlaintextTemplate(text=content_segment))
        else:
            contained_content.extend(
                templatify_node(content_segment, doc_coll=doc_coll))

    info = node.info
    if info is None:
        return contained_content
    else:
        return _wrap_in_richtext_context(
            contained_content,
            cast(InlineNodeInfo, info))


@templatify_node.register
def templatify_annotation_node(
        node: Annotation,
        *,
        doc_coll: HtmlDocumentCollection
        ) -> list[HtmlTemplate]:
    return []


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

    elif isinstance(target, ReferenceDataType):
        # TODO: actual implementation
        return f'#{target.value}'

    elif isinstance(target, MentionDataType):
        raise NotImplementedError(
            'That link target type is not yet supported', target)

    elif isinstance(target, VariableDataType):
        raise NotImplementedError(
            'That link target type is not yet supported', target)

    elif isinstance(target, TagDataType):
        raise NotImplementedError(
            'That link target type is not yet supported', target)

    else:
        raise TypeError('Link target was not a link target type!', target)
