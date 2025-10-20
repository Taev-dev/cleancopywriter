from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from cleancopy.spectypes import InlineFormatting
from docnote import Note
from docnote_extract.crossrefs import Crossref
from docnote_extract.crossrefs import GetattrTraversal
from docnote_extract.normalization import NormalizedSpecialType

from cleancopywriter.html.templates import CrossrefSummaryTemplate
from cleancopywriter.html.templates import FallbackContainerTemplate
from cleancopywriter.html.templates import HtmlAttr
from cleancopywriter.html.templates import HtmlGenericElement
from cleancopywriter.html.templates import HtmlTemplate
from cleancopywriter.html.templates import PlaintextTemplate
from cleancopywriter.html.templates import UnlinkableCrossrefSummaryTemplate

UNDERLINE_TAGNAME = 'clc-ul'
INLINE_PRE_CLASSNAME = 'clc-fmt-pre'


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


def dunder_all_factory(
        names: Sequence[str],
        ) -> list[HtmlGenericElement]:
    retval: list[HtmlGenericElement] = []
    for name in names:
        retval.append(HtmlGenericElement(
            tag='li',
            body=[PlaintextTemplate(name)]))

    return retval


_specialform_lookup: dict[NormalizedSpecialType, CrossrefSummaryTemplate] = {
    NormalizedSpecialType.ANY: UnlinkableCrossrefSummaryTemplate(
        qualname='typing.Any',
        shortname='Any'),
    NormalizedSpecialType.LITERAL_STRING: UnlinkableCrossrefSummaryTemplate(
        qualname='typing.LiteralString',
        shortname='LiteralString'),
    NormalizedSpecialType.NEVER: UnlinkableCrossrefSummaryTemplate(
        qualname='typing.Never',
        shortname='Never'),
    NormalizedSpecialType.NORETURN: UnlinkableCrossrefSummaryTemplate(
        qualname='typing.NoReturn',
        shortname='NoReturn'),
    NormalizedSpecialType.SELF: UnlinkableCrossrefSummaryTemplate(
        qualname='typing.Self',
        shortname='Self'),
    NormalizedSpecialType.NONE: UnlinkableCrossrefSummaryTemplate(
        qualname='builtins.None',
        shortname='None'),
}


def specialform_type_factory(
        normtype: NormalizedSpecialType
        ) -> CrossrefSummaryTemplate:
    return _specialform_lookup[normtype]


def literal_value_factory(
        value: int | bool | str | bytes | Crossref
        ) -> FallbackContainerTemplate | CrossrefSummaryTemplate:
    if isinstance(value, Crossref):
        if value.module_name is None:
            raise ValueError(
                'Crossreffed literal values can only be enums; module name '
                + 'is required!', value)
        if value.toplevel_name is None:
            raise ValueError(
                'Crossreffed literal values can only be enums; toplevel name '
                + 'is required!', value)
        if (
            len(value.traversals) != 1
            or not isinstance(value.traversals[0], GetattrTraversal)
        ):
            raise ValueError(
                'Crossreffed literal values can only be enums; must have '
                + 'exactly one ``GetattrTraversal``!', value)

        member_name = value.traversals[0].name
        return UnlinkableCrossrefSummaryTemplate(
            qualname=
                f'{value.module_name}:{value.toplevel_name}.{member_name}',
            shortname=f'{value.toplevel_name}.{member_name}')

    return FallbackContainerTemplate(
        wraps=[formatting_factory(
            spectype=InlineFormatting.PRE,
            body=[PlaintextTemplate(repr(value))])])
