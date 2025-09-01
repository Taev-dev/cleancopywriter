from __future__ import annotations

from typing import Annotated

from cleancopy.spectypes import InlineFormatting
from docnote import Note

from cleancopywriter.html.templates import HtmlAttr
from cleancopywriter.html.templates import HtmlGenericElement
from cleancopywriter.html.templates import HtmlTemplate

UNDERLINE_CLASSNAME = 'clc-ul'


def link_factory(
        body: list[HtmlTemplate],
        href: str,
        ) -> HtmlGenericElement:
    return HtmlGenericElement(
        tag='a',
        attrs=[HtmlAttr(key='href', value=href)],
        body=body)


def heading_factory(
        depth: Annotated[int, Note('Note: zero-indexed!')],
        body: list[HtmlTemplate]
        ) -> HtmlGenericElement:
    """Beyond what you'd expect, this:
    ++  converts a zero-indexed depth to a 1-indexed heading
    ++  clamps the value to the allowable HTML range [1, 6]
    """
    if depth < 0:
        heading_level = 1
    elif depth > 5:  # noqa: PLR2004
        heading_level = 6
    elif type(depth) is not int:
        heading_level = int(depth) + 1
    else:
        heading_level = depth + 1

    return HtmlGenericElement(
        tag=f'h{heading_level}',
        body=body)


def formatting_factory(
        spectype: InlineFormatting,
        body: list[HtmlTemplate]
        ) -> HtmlGenericElement:
    if spectype is InlineFormatting.PRE:
        tag = 'pre'
        attrs = []

    elif spectype is InlineFormatting.UNDERLINE:
        tag = 'span'
        attrs = [HtmlAttr(key='class', value=UNDERLINE_CLASSNAME)]

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


def listitem_factory(
        index: int | None,
        body: list[HtmlTemplate]
        ) -> HtmlGenericElement:
    """Convenience wrapper to set explicit values on ordered lists."""
    if index is None:
        attrs = []

    else:
        if type(index) is not int:
            index = int(index)
        attrs = [HtmlAttr(key='value', value=str(index))]

    return HtmlGenericElement(tag='li', attrs=attrs, body=body)
