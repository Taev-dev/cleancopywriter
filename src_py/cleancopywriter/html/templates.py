from __future__ import annotations

from dataclasses import field

from templatey import Content
from templatey import Slot
from templatey import Var
from templatey import template
from templatey.prebaked.loaders import InlineStringTemplateLoader
from templatey.prebaked.template_configs import html

_loader = InlineStringTemplateLoader()
type HtmlTemplate = (
    HtmlGenericElement
    | PlaintextTemplate)


@template(
    html,
    '<{content.tag}{slot.attrs: __prefix__=" "}>{slot.body}</{content.tag}>',
    loader=_loader,
    kw_only=True)
class HtmlGenericElement:
    tag: Content[str]
    attrs: Slot[HtmlAttr] = field(default_factory=list)
    # Pyright has an intermittent bug with not recognizing htmltemplate as
    # a dataclass instance. This probably has something to do with our
    # missing intersection type.
    body: Slot[HtmlTemplate]  # type: ignore


@template(html, '{content.key}="{var.value}"', loader=_loader)
class HtmlAttr:
    key: Content[str]
    value: Var[str]


@template(html, '{var.text}', loader=_loader)
class PlaintextTemplate:
    text: Var[str]
