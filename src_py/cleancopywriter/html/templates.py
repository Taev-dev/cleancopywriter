from __future__ import annotations

import typing
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import field
from dataclasses import fields
from functools import singledispatch
from textwrap import dedent
from typing import Annotated
from typing import Self
from typing import overload

from cleancopy.spectypes import InlineFormatting
from docnote import MarkupLang
from docnote import Note
from docnote_extract.crossrefs import CallTraversal
from docnote_extract.crossrefs import Crossref
from docnote_extract.crossrefs import CrossrefTraversal
from docnote_extract.crossrefs import GetattrTraversal
from docnote_extract.crossrefs import GetitemTraversal
from docnote_extract.crossrefs import SyntacticTraversal
from docnote_extract.normalization import NormalizedConcreteType
from docnote_extract.normalization import NormalizedEmptyGenericType
from docnote_extract.normalization import NormalizedLiteralType
from docnote_extract.normalization import NormalizedSpecialType
from docnote_extract.normalization import NormalizedType
from docnote_extract.normalization import NormalizedUnionType
from docnote_extract.normalization import TypeSpec
from docnote_extract.summaries import CallableColor
from docnote_extract.summaries import CallableSummary
from docnote_extract.summaries import ClassSummary
from docnote_extract.summaries import CrossrefSummary
from docnote_extract.summaries import DocText
from docnote_extract.summaries import MethodType
from docnote_extract.summaries import ModuleSummary
from docnote_extract.summaries import NamespaceMemberSummary
from docnote_extract.summaries import ParamStyle
from docnote_extract.summaries import ParamSummary
from docnote_extract.summaries import RetvalSummary
from docnote_extract.summaries import SignatureSummary
from docnote_extract.summaries import SummaryMetadataProtocol
from docnote_extract.summaries import VariableSummary
from templatey import Content
from templatey import DynamicClassSlot
from templatey import Slot
from templatey import Var
from templatey import template
from templatey.prebaked.loaders import InlineStringTemplateLoader
from templatey.prebaked.template_configs import html
from templatey.templates import FieldConfig
from templatey.templates import template_field

if typing.TYPE_CHECKING:
    from cleancopywriter.html.documents import HtmlDocumentCollection

UNDERLINE_TAGNAME = 'clc-ul'
INLINE_PRE_CLASSNAME = 'clc-fmt-pre'


_loader = InlineStringTemplateLoader()
type HtmlTemplate = HtmlGenericElement | PlaintextTemplate
type NamespaceItemTemplate = (
    ModuleSummaryTemplate
    | VariableSummaryTemplate
    | ClassSummaryTemplate
    | CallableSummaryTemplate)


@template(
    html,
    '<{content.tag}{slot.attrs: __prefix__=" "}>{slot.body}</{content.tag}>',
    loader=_loader,
    kw_only=True)
class HtmlGenericElement:
    tag: Content[str]
    attrs: Slot[HtmlAttr] = field(default_factory=list)
    body: DynamicClassSlot


@template(html, '{content.key}="{var.value}"', loader=_loader)
class HtmlAttr:
    key: Content[str]
    value: Var[str]


@template(html, '{var.text}', loader=_loader)
class PlaintextTemplate:
    text: Var[str]


@template(
    html,
    # Note: we're not doing a role of list here, because the child elements
    # may or may not be list items (because they can also be used outside of
    # a literal) and therefore there's no way to distinguish between them
    dedent('''\
        <docnote-fallback-container>
            {slot.wraps}
        </docnote-fallback-container>'''),
    loader=_loader)
class FallbackContainerTemplate:
    """Fallback templates are used for docnote things we haven't fully
    implemented yet, where we want to wrap a generic HTML element in
    a container.
    """
    wraps: Slot[HtmlGenericElement]


@template(
    html,
    dedent('''\
        <docnote-module role="article">
            <header>
                <docnote-name obj-type="module" role="heading" aria-level="1">
                    {var.fullname}
                </docnote-name>
                <docnote-docstring obj-type="module">
                    {slot.docstring}
                </docnote-docstring>
                <docnote-module-dunderall role="list">
                    {slot.dunder_all}
                </docnote-module-dunderall>
            </header>
            {slot.members}
        </docnote-module>
        '''),
    loader=_loader)
class ModuleSummaryTemplate:
    fullname: Var[str]
    docstring: Slot[HtmlGenericElement | PlaintextTemplate]
    dunder_all: Slot[HtmlGenericElement]
    members: Slot[NamespaceItemTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: ModuleSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = templatify_doctext(
                summary_node.docstring, for_collection)

        if summary_node.dunder_all is None:
            dunder_all = []
        else:
            dunder_all = dunder_all_factory(sorted(summary_node.dunder_all))

        return cls(
            fullname=summary_node.name,
            docstring=docstring,
            dunder_all=dunder_all,
            members=[
                get_template_cls(member).from_summary(member, for_collection)
                for member in cls.sort_members(summary_node.members)
                if should_include(member.metadata)])

    @classmethod
    def sort_members(
            cls,
            members: frozenset[NamespaceMemberSummary]
            ) -> list[NamespaceMemberSummary]:
        # TODO: this needs to support ordering index and groupings!
        return sorted(members, key=lambda member: member.name)


@template(
    html,
    dedent('''\
        <docnote-attribute>
            <header>
                <docnote-name obj-type="attribute" role="heading" aria-level="2">
                    {var.name}
                </docnote-name>
                {slot.typespec}
            </header>
            <docnote-notes>
                {slot.notes}
            </docnote-notes>
        </docnote-attribute>
        '''),  # noqa: E501
    loader=_loader)
class VariableSummaryTemplate:
    name: Var[str]
    typespec: Slot[TypespecTemplate]
    notes: Slot[HtmlGenericElement | PlaintextTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: VariableSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        rendered_notes: list[HtmlTemplate] = []
        for note in summary_node.notes:
            rendered_notes.extend(templatify_doctext(note, for_collection))

        return cls(
            name=summary_node.name,
            typespec=
                [templatify_typespec(summary_node.typespec)]
                if summary_node.typespec is not None
                else (),
            notes=rendered_notes)


@template(
    html,
    dedent('''\
        <docnote-class>
            <header>
                <docnote-name obj-type="class" role="heading" aria-level="2">
                    {var.name}
                </docnote-name>
                <docnote-class-metaclass>
                    {slot.metaclass}
                </docnote-class-metaclass>
                <docnote-class-bases-container>
                    <docnote-class-bases role="list">
                        {slot.bases:
                        __prefix__='<docnote-class-base role="listitem">',
                        __suffix__='</docnote-class-base>'}
                    </docnote-class-bases>
                </docnote-class-bases-container>
                <docnote-docstring obj-type="class">
                    {slot.docstring}
                </docnote-docstring>
            </header>
            {slot.members}
        </docnote-class>
        '''),
    loader=_loader)
class ClassSummaryTemplate:
    name: Var[str]
    metaclass: Slot[NormalizedConcreteTypeTemplate]
    bases: Slot[NormalizedConcreteTypeTemplate]
    docstring: Slot[HtmlGenericElement | PlaintextTemplate]
    members: Slot[NamespaceItemTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: ClassSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = templatify_doctext(
                summary_node.docstring, for_collection)

        return cls(
            name=summary_node.name,
            metaclass=
                [templatify_concrete_typespec(summary_node.metaclass)]
                if summary_node.metaclass is not None
                else (),
            docstring=docstring,
            bases=[
                templatify_concrete_typespec(base)
                for base in summary_node.bases],
            members=[
                get_template_cls(member).from_summary(member, for_collection)
                for member in cls.sort_members(summary_node.members)
                if should_include(member.metadata)])

    @classmethod
    def sort_members(
            cls,
            members: frozenset[NamespaceMemberSummary]
            ) -> list[NamespaceMemberSummary]:
        # TODO: this needs to support ordering index and groupings!
        return sorted(members, key=lambda member: member.name)


def _transform_is_generator(value: bool) -> str:
    if value:
        return 'generator="true"'
    else:
        return 'generator="false"'


def _transform_method_type(value: MethodType | None) -> str:
    if value is MethodType.INSTANCE:
        return 'method-type="instancemethod"'
    elif value is MethodType.CLASS:
        return 'method-type="classmethod"'
    elif value is MethodType.STATIC:
        return 'method-type="staticmethod"'
    else:
        return 'method-type="null"'


def _transform_callable_color(value: CallableColor) -> str:
    if value is CallableColor.ASYNC:
        return 'call-color="async"'
    else:
        return 'call-color="sync"'


@template(
    html,
    dedent('''\
        <docnote-callable>
            <header>
                <docnote-name obj-type="callable" role="heading" aria-level="2">
                    {var.name}
                </docnote-name>
                <docnote-docstring obj-type="callable">
                    {slot.docstring}
                </docnote-docstring>
                <docnote-tags>
                    <docnote-tag {content.color}></docnote-tag>
                    <docnote-tag {content.method_type}></docnote-tag>
                    <docnote-tag {content.is_generator}></docnote-tag>
                </docnote-tags>
            </header>
            <docnote-callable-signatures>
                {slot.signatures}
            </docnote-callable-signatures>
        </docnote-callable>
        '''),  # noqa: E501
    loader=_loader)
class CallableSummaryTemplate:
    name: Var[str]
    docstring: Slot[HtmlGenericElement | PlaintextTemplate]

    color: Content[CallableColor] = template_field(FieldConfig(
        transformer=_transform_callable_color))
    method_type: Content[MethodType | None] = template_field(FieldConfig(
        transformer=_transform_method_type))
    is_generator: Content[bool] = template_field(FieldConfig(
        transformer=_transform_is_generator))

    signatures: Slot[SignatureSummaryTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: CallableSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = templatify_doctext(
                summary_node.docstring, for_collection)

        return cls(
            name=summary_node.name,
            docstring=docstring,
            color=summary_node.color,
            method_type=summary_node.method_type,
            is_generator=summary_node.is_generator,
            signatures=[
                SignatureSummaryTemplate.from_summary(
                    signature, for_collection)
                for signature in cls.sort_signatures(summary_node.signatures)
                if should_include(signature.metadata)])

    @classmethod
    def sort_signatures(
            cls,
            members: frozenset[SignatureSummary]
            ) -> list[SignatureSummary]:
        # TODO: this needs to support groupings, and we need to verify that
        # ordering index is always set on signature summaries!
        return sorted(members, key=lambda member: member.ordering_index or 0)


@template(
    html,
    dedent('''\
        <docnote-callable-signature>
            <header>
                <docnote-docstring obj-type="callable-signature">
                    {slot.docstring}
                </docnote-docstring>
            </header>
            <docnote-callable-signature-params role="list">
                {slot.params}
            </docnote-callable-signature-params>
            <docnote-callable-signature-retval>
                {slot.retval}
            </docnote-callable-signature-retval>
        </docnote-callable-signature>
        '''),
    loader=_loader)
class SignatureSummaryTemplate:
    params: Slot[ParamSummaryTemplate]
    retval: Slot[RetvalSummaryTemplate]
    docstring: Slot[HtmlGenericElement | PlaintextTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: SignatureSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = templatify_doctext(
                summary_node.docstring, for_collection)

        return cls(
            params=[
                ParamSummaryTemplate.from_summary(param, for_collection)
                for param in cls.sort_params(summary_node.params)
                if should_include(param.metadata)],
            retval=[
                RetvalSummaryTemplate.from_summary(
                    summary_node.retval, for_collection)],
            docstring=docstring)

    @classmethod
    def sort_params(
            cls,
            members: frozenset[ParamSummary]
            ) -> list[ParamSummary]:
        # TODO: this needs to support groupings (probably just for kwarg-only
        # params though)
        return sorted(members, key=lambda member: member.index)


def _transform_param_style(value: ParamStyle) -> str:
    return f'style="{value.value}"'


@template(
    html,
    dedent('''\
        <docnote-callable-signature-param {content.style} role="listitem">
            <header>
                <docnote-name obj-type="callable-signature-param-item" role="heading" aria-level="3">
                    {var.name}
                </docnote-name>
                {slot.typespec}
            </header>
            <docnote-callable-signature-param-default>
                {slot.default}
            </docnote-callable-signature-param-default>
            <docnote-notes>
                {slot.notes}
            </docnote-notes>
        </docnote-callable-signature-param>
        '''),  # noqa: E501
    loader=_loader)
class ParamSummaryTemplate:
    style: Content[ParamStyle] = template_field(FieldConfig(
        transformer=_transform_param_style))
    name: Var[str]
    typespec: Slot[TypespecTemplate]
    default: Slot[ValueReprTemplate]
    notes: Slot[HtmlGenericElement | PlaintextTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: ParamSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        rendered_notes: list[HtmlTemplate] = []
        for note in summary_node.notes:
            rendered_notes.extend(templatify_doctext(note, for_collection))

        rendered_default: list[ValueReprTemplate] = []
        if summary_node.default is not None:
            rendered_default.append(
                ValueReprTemplate(repr(summary_node.default)))

        return cls(
            style=summary_node.style,
            name=summary_node.name,
            default=rendered_default,
            typespec=[templatify_typespec(summary_node.typespec)]
                if summary_node.typespec is not None
                else (),
            notes=rendered_notes)


@template(
    html,
    # Note: the parent signature is responsible for wrapping this in the retval
    # container tag.
    dedent('''\
        <header>
            {slot.typespec}
        </header>
        <docnote-notes>
            {slot.notes}
        </docnote-notes>
        '''),
    loader=_loader)
class RetvalSummaryTemplate:
    typespec: Slot[TypespecTemplate]
    notes: Slot[HtmlGenericElement | PlaintextTemplate]

    @classmethod
    def from_summary(
            cls,
            summary_node: RetvalSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        rendered_notes: list[HtmlTemplate] = []
        for note in summary_node.notes:
            rendered_notes.extend(templatify_doctext(note, for_collection))

        return cls(
            typespec=[templatify_typespec(summary_node.typespec)]
                if summary_node.typespec is not None
                else (),
            notes=rendered_notes)


@template(
    html,
    dedent('''\
        <docnote-value-repr>
            {var.reprified_value}
        </docnote-value-repr>
        '''),
    loader=_loader)
class ValueReprTemplate:
    reprified_value: Var[str]


type NormalizedTypeTemplate = (
    NormalizedUnionTypeTemplate
    | NormalizedEmptyGenericTypeTemplate
    | NormalizedConcreteTypeTemplate
    | NormalizedSpecialTypeTemplate
    | NormalizedLiteralTypeTemplate)


def _transform_lowercase_bool(value: bool) -> str:
    if value:
        return 'true'
    else:
        return 'false'


def _transform_tagspec_key(value: str) -> str:
    return value.removeprefix('has_')


@template(
    html,
    '<docnote-tag {content.key}="{content.value}"></docnote-tag>',
    loader=_loader)
class TypespecTagTemplate:
    """Typespec tags are used for eg ``ClassVar[...]``, ``Final[...]``,
    etc.
    """
    key: Content[str] = template_field(
        FieldConfig(transformer=_transform_tagspec_key))
    value: Content[bool] = template_field(
        FieldConfig(transformer=_transform_lowercase_bool))


@template(
    html,
    dedent('''\
        <docnote-typespec>
            <docnote-normtype>
                {slot.normtype}
            </docnote-normtype>
            <docnote-tags>
                {slot.typespec_tags}
            </docnote-tags>
        </docnote-typespec>'''),
    loader=_loader)
class TypespecTemplate:
    normtype: Slot[NormalizedTypeTemplate]
    typespec_tags: Slot[TypespecTagTemplate]


@template(
    html,
    # Note: we're not doing a role of list here, because the child elements
    # may or may not be list items (because they can also be used outside of
    # a union) and therefore there's no way to distinguish between them
    dedent('''\
        <docnote-normtype-union-container>
            <docnote-normtype-union>
                {slot.normtypes}
            </docnote-normtype-union>
        </docnote-normtype-union-container>'''),
    loader=_loader)
class NormalizedUnionTypeTemplate:
    normtypes: Slot[NormalizedTypeTemplate]


@template(
    html,
    dedent('''\
        <docnote-normtype-concrete>
            <docnote-normtype-concrete-primary>
                {slot.primary}
            </docnote-normtype-concrete-primary>
            <docnote-normtype-params-container>
                <docnote-normtype-params>
                    {slot.params}
                </docnote-normtype-params>
            </docnote-normtype-params-container>
        </docnote-normtype-concrete>'''),
    loader=_loader)
class NormalizedConcreteTypeTemplate:
    primary: Slot[CrossrefSummaryTemplate]
    params: Slot[NormalizedTypeTemplate]


@template(
    html,
    dedent('''\
        <docnote-normtype-emptygeneric>
            <docnote-normtype-params-container>
                <docnote-normtype-params>
                    {slot.params}
                </docnote-normtype-params>
            </docnote-normtype-params-container>
        </docnote-normtype-emptygeneric>'''),
    loader=_loader)
class NormalizedEmptyGenericTypeTemplate:
    params: Slot[NormalizedTypeTemplate]


@template(
    html,
    dedent('''\
        <docnote-normtype-specialform>
            {slot.type_}
        </docnote-normtype-specialform>'''),
    loader=_loader)
class NormalizedSpecialTypeTemplate:
    type_: Slot[CrossrefSummaryTemplate]


@template(
    html,
    # Note: we're not doing a role of list here, because the child elements
    # may or may not be list items (because they can also be used outside of
    # a literal) and therefore there's no way to distinguish between them
    dedent('''\
        <docnote-normtype-literal>
            {slot.values}
        </docnote-normtype-literal>'''),
    loader=_loader)
class NormalizedLiteralTypeTemplate:
    values: Slot[FallbackContainerTemplate | CrossrefSummaryTemplate]


@template(
    html,
    dedent('''\
        <abbr title="{var.qualname}{var.traversals}">
            {slot.crossref_target}
        </abbr>
        '''),
    loader=_loader)
class CrossrefSummaryTemplate:
    qualname: Var[str]
    traversals: Var[str | None] = field(default=None, kw_only=True)
    crossref_target: Slot[CrossrefLinkTemplate | CrossrefTextTemplate]

    @classmethod
    def from_crossref(cls, crossref: Crossref) -> Self:
        if crossref.toplevel_name is None:
            shortname = qualname = f'<Module {crossref.module_name}>'
        else:
            # These are actually unknown in case of traversals...
            # TODO: that needs fixing! probably with <> brackets.
            shortname = crossref.toplevel_name
            qualname = f'{crossref.module_name}:{crossref.toplevel_name}'

        traversals = (''.join(
            _flatten_typespec_traversals(crossref.traversals))
            if crossref.traversals else None)

        # TODO: we need to convert the slot to be an environment function
        # operating on the document collection so that linkability can be
        # determined lazily at render time
        return cls(
            qualname=qualname,
            traversals=traversals,
            crossref_target=[
                CrossrefTextTemplate(
                    shortname=shortname,
                    has_traversals=traversals is not None)])

    @classmethod
    def from_summary(
            cls,
            summary_node: CrossrefSummary,
            for_collection: HtmlDocumentCollection
            ) -> Self:
        if summary_node.crossref is None:
            raise ValueError('Cannot templatify a nonexistent crossref!')

        return cls.from_crossref(summary_node.crossref)


@template(
    html,
    '<a href="{var.target}">{slot.text}</a>',
    loader=_loader)
class CrossrefLinkTemplate:
    target: Var[str]
    text: Slot[CrossrefTextTemplate]

    has_traversals: bool = field(init=False)

    def __post_init__(self):
        for text_instance in self.text:
            text_instance.has_traversals = self.has_traversals


@template(
    html,
    '{var.shortname}{content.has_traversals}',
    loader=_loader)
class CrossrefTextTemplate:
    shortname: Var[str]
    has_traversals: Content[bool] = template_field(
        FieldConfig(
            transformer=lambda value: '<...>' if value else None))


def templatify_doctext(
        doctext: DocText,
        for_collection: HtmlDocumentCollection,
        ) -> list[HtmlTemplate]:
    if doctext.markup_lang is None:
        return [
            HtmlGenericElement(
                tag='code',
                body=[PlaintextTemplate(doctext.value)],
                attrs=[HtmlAttr(key='class', value=INLINE_PRE_CLASSNAME)])]

    if isinstance(doctext.markup_lang, str):
        if doctext.markup_lang in set(MarkupLang.CLEANCOPY.value):
            markup_lang = MarkupLang.CLEANCOPY
        else:
            markup_lang = None
    else:
        markup_lang = doctext.markup_lang

    if markup_lang is not MarkupLang.CLEANCOPY:
        raise ValueError(
            'Unsupported markup language for doctext!', doctext)

    ast_doc = for_collection.preprocess(clc_text=doctext.value)
    return for_collection.writer.write_node(ast_doc)


def templatify_concrete_typespec(
        typespec: TypeSpec
        ) -> NormalizedConcreteTypeTemplate:
    """Use this to render the (concrete, ie, cannot be a union etc)
    typespec -- ie, metaclasses and base classes.
    """
    result = templatify_normalized_type(typespec.normtype)
    if not isinstance(result, NormalizedConcreteTypeTemplate):
        raise TypeError(
            'Invalid concrete type (metaclass or base)', typespec)

    return result


def templatify_typespec(
        typespec: TypeSpec
        ) -> TypespecTemplate:
    tags: list[TypespecTagTemplate] = []

    for dc_field in fields(typespec):
        if dc_field.name != 'normtype':
            tags.append(TypespecTagTemplate(
                key=dc_field.name,
                value=getattr(typespec, dc_field.name)))

    return TypespecTemplate(
        normtype=[templatify_normalized_type(typespec.normtype)],
        typespec_tags=tags)


@singledispatch
def templatify_normalized_type(
        normtype: NormalizedType
        ) -> NormalizedTypeTemplate:
    raise TypeError('Unknown normalized type!', normtype)

@templatify_normalized_type.register
def _(
        normtype: NormalizedUnionType
        ) -> NormalizedUnionTypeTemplate:
    return NormalizedUnionTypeTemplate(
        normtypes=[
            templatify_normalized_type(nested_normtype)
            for nested_normtype in normtype.normtypes])

@templatify_normalized_type.register
def _(
        normtype: NormalizedEmptyGenericType
        ) -> NormalizedEmptyGenericTypeTemplate:
    return NormalizedEmptyGenericTypeTemplate(
        params=[
            templatify_normalized_type(param_typespec.normtype)
            for param_typespec in normtype.params])

@templatify_normalized_type.register
def _(
        normtype: NormalizedConcreteType
        ) -> NormalizedConcreteTypeTemplate:
    return NormalizedConcreteTypeTemplate(
        primary=[CrossrefSummaryTemplate.from_crossref(normtype.primary)],
        params=[
            templatify_normalized_type(param_typespec.normtype)
            for param_typespec in normtype.params])

@templatify_normalized_type.register
def _(
        normtype: NormalizedSpecialType
        ) -> NormalizedSpecialTypeTemplate:
    return NormalizedSpecialTypeTemplate(
        type_=[specialform_type_factory(normtype)])

@templatify_normalized_type.register
def _(
        normtype: NormalizedLiteralType
        ) -> NormalizedLiteralTypeTemplate:
    return NormalizedLiteralTypeTemplate(
        values=[
            literal_value_factory(value)
            for value in normtype.values])


@overload
def get_template_cls(
        summary: ModuleSummary
        ) -> type[ModuleSummaryTemplate]: ...
@overload
def get_template_cls(
        summary: VariableSummary
        ) -> type[VariableSummaryTemplate]: ...
@overload
def get_template_cls(
        summary: ClassSummary
        ) -> type[ClassSummaryTemplate]: ...
@overload
def get_template_cls(
        summary: CallableSummary
        ) -> type[CallableSummaryTemplate]: ...
@overload
def get_template_cls(
        summary: CrossrefSummary
        ) -> type[CrossrefSummaryTemplate]: ...
def get_template_cls(
        summary:
            ModuleSummary
            | VariableSummary
            | ClassSummary
            | CallableSummary
            | CrossrefSummary
        ) -> (
            type[ModuleSummaryTemplate]
            | type[VariableSummaryTemplate]
            | type[ClassSummaryTemplate]
            | type[CallableSummaryTemplate]
            | type[CrossrefSummaryTemplate]
        ):
    """Gets the appropriate template class for the passed summary
    object. Only supports objects that can be contained within a
    namespace; the rest should be known directly based on the structure
    of the summary.
    """
    if isinstance(summary, ModuleSummary):
        return ModuleSummaryTemplate
    elif isinstance(summary, VariableSummary):
        return VariableSummaryTemplate
    elif isinstance(summary, ClassSummary):
        return ClassSummaryTemplate
    elif isinstance(summary, CallableSummary):
        return CallableSummaryTemplate
    elif isinstance(summary, CrossrefSummary):
        return CrossrefSummaryTemplate
    else:
        raise TypeError('Unsupported summary type', summary)


def should_include(
        metadata: SummaryMetadataProtocol
        ) -> bool:
    if metadata.extracted_inclusion is True:
        return True
    if metadata.extracted_inclusion is False:
        return False

    return metadata.to_document and not metadata.disowned


def _flatten_typespec_traversals(
        traversals: Sequence[CrossrefTraversal],
        *,
        _index=0
        ) -> Iterator[str]:
    """This is a backstop to collapse crossref traversals into a string
    that can be rendered.
    """
    if len(traversals) <= _index:
        return

    this_traversal = traversals[_index]

    if isinstance(this_traversal, GetattrTraversal):
        yield f'.{this_traversal.name}'

    elif isinstance(this_traversal, CallTraversal):
        yield f'(*{this_traversal.args}, **{this_traversal.kwargs})'

    elif isinstance(this_traversal, GetitemTraversal):
        yield f'[{this_traversal.key}]'

    elif isinstance(this_traversal, SyntacticTraversal):
        yield f'<{this_traversal.type_.value}: {this_traversal.key}>'

    else:
        raise TypeError('Invalid traversal type for typespec!', this_traversal)

    yield from _flatten_typespec_traversals(traversals, _index=_index + 1)




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
    NormalizedSpecialType.ANY: CrossrefSummaryTemplate(
            qualname='typing.Any',
            crossref_target=[
                CrossrefTextTemplate(
                    shortname='Any',
                    has_traversals=False)]),
    NormalizedSpecialType.LITERAL_STRING: CrossrefSummaryTemplate(
            qualname='typing.LiteralString',
            crossref_target=[
                CrossrefTextTemplate(
                    shortname='LiteralString',
                    has_traversals=False)]),
    NormalizedSpecialType.NEVER: CrossrefSummaryTemplate(
            qualname='typing.Never',
            crossref_target=[
                CrossrefTextTemplate(
                    shortname='Never',
                    has_traversals=False)]),
    NormalizedSpecialType.NORETURN: CrossrefSummaryTemplate(
            qualname='typing.NoReturn',
            crossref_target=[
                CrossrefTextTemplate(
                    shortname='NoReturn',
                    has_traversals=False)]),
    NormalizedSpecialType.SELF: CrossrefSummaryTemplate(
            qualname='typing.Self',
            crossref_target=[
                CrossrefTextTemplate(
                    shortname='Self',
                    has_traversals=False)]),
    NormalizedSpecialType.NONE: CrossrefSummaryTemplate(
            qualname='builtins.None',
            crossref_target=[
                CrossrefTextTemplate(
                    shortname='None',
                    has_traversals=False)]),
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

        return CrossrefSummaryTemplate.from_crossref(value)

    return FallbackContainerTemplate(
        wraps=[formatting_factory(
            spectype=InlineFormatting.PRE,
            body=[PlaintextTemplate(repr(value))])])
