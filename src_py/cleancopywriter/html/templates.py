from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from textwrap import dedent

from docnote_extract.summaries import CallableColor
from docnote_extract.summaries import MethodType
from docnote_extract.summaries import ParamStyle
from templatey import Content
from templatey import DynamicClassSlot
from templatey import Slot
from templatey import Var
from templatey import template
from templatey.prebaked.loaders import InlineStringTemplateLoader
from templatey.prebaked.template_configs import html
from templatey.templates import FieldConfig
from templatey.templates import template_field

_loader = InlineStringTemplateLoader()
type HtmlTemplate = (
    HtmlGenericElement
    | PlaintextTemplate
    | ModuleSummaryTemplate
    | VariableSummaryTemplate
    | ClassSummaryTemplate
    | CallableSummaryTemplate
    | TypespecTemplate
    | SignatureSummaryTemplate
    | ParamSummaryTemplate
    | RetvalSummaryTemplate)
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

    signatures: Slot[SignatureSummaryTemplate]  # type: ignore


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


@dataclass(slots=True)
class _CrossrefSummaryTemplateBase:
    qualname: Var[str]
    shortname: Var[str]
    traversals: Var[str | None] = field(default=None, kw_only=True)

    has_traversals: Content[bool] = template_field(  # noqa: RUF009
        FieldConfig(
            transformer=lambda value: '<...>' if value else None),
        init=False)

    def __post_init__(self):
        self.has_traversals = (self.traversals is not None)


@template(
    html,
    dedent('''\
        <abbr title="{var.qualname}{var.traversals}">
            <a href="{var.target}">{var.shortname}{content.has_traversals}</a>
        </abbr>
        '''),
    loader=_loader)
class LinkableCrossrefSummaryTemplate(_CrossrefSummaryTemplateBase):
    # Note: the error here is because it's not understanding our use of
    # ``param()`` in the base class
    target: Var[str]


@template(
    html,
    dedent('''\
        <abbr title="{var.qualname}{var.traversals}">
            {var.shortname}{content.has_traversals}
        </abbr>
        '''),
    loader=_loader)
class UnlinkableCrossrefSummaryTemplate(_CrossrefSummaryTemplateBase):
    """This just inherits from the summary template base.
    """


type CrossrefSummaryTemplate = (
    LinkableCrossrefSummaryTemplate | UnlinkableCrossrefSummaryTemplate)
