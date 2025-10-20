from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import fields
from functools import singledispatchmethod

from cleancopy import Abstractifier
from cleancopy import parse
from docnote import MarkupLang
from docnote_extract import Docnotes
from docnote_extract import SummaryTreeNode
from docnote_extract.crossrefs import CallTraversal
from docnote_extract.crossrefs import Crossref
from docnote_extract.crossrefs import CrossrefTraversal
from docnote_extract.crossrefs import GetattrTraversal
from docnote_extract.crossrefs import GetitemTraversal
from docnote_extract.crossrefs import SyntacticTraversal
from docnote_extract.crossrefs import SyntacticTraversalType
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
from docnote_extract.summaries import DocText
from docnote_extract.summaries import MethodType
from docnote_extract.summaries import ModuleSummary
from docnote_extract.summaries import ParamStyle
from docnote_extract.summaries import ParamSummary
from docnote_extract.summaries import RetvalSummary
from docnote_extract.summaries import SignatureSummary
from docnote_extract.summaries import SummaryBase
from docnote_extract.summaries import SummaryMetadataProtocol
from docnote_extract.summaries import VariableSummary

from cleancopywriter.html.factories import INLINE_PRE_CLASSNAME
from cleancopywriter.html.factories import dunder_all_factory
from cleancopywriter.html.factories import literal_value_factory
from cleancopywriter.html.factories import specialform_type_factory
from cleancopywriter.html.templates import CallableSummaryTemplate
from cleancopywriter.html.templates import ClassSummaryTemplate
from cleancopywriter.html.templates import HtmlAttr
from cleancopywriter.html.templates import HtmlGenericElement
from cleancopywriter.html.templates import HtmlTemplate
from cleancopywriter.html.templates import ModuleSummaryTemplate
from cleancopywriter.html.templates import NormalizedConcreteTypeTemplate
from cleancopywriter.html.templates import NormalizedEmptyGenericTypeTemplate
from cleancopywriter.html.templates import NormalizedLiteralTypeTemplate
from cleancopywriter.html.templates import NormalizedSpecialTypeTemplate
from cleancopywriter.html.templates import NormalizedTypeTemplate
from cleancopywriter.html.templates import NormalizedUnionTypeTemplate
from cleancopywriter.html.templates import ParamSummaryTemplate
from cleancopywriter.html.templates import PlaintextTemplate
from cleancopywriter.html.templates import RetvalSummaryTemplate
from cleancopywriter.html.templates import SignatureSummaryTemplate
from cleancopywriter.html.templates import TypespecTagTemplate
from cleancopywriter.html.templates import TypespecTemplate
from cleancopywriter.html.templates import UnlinkableCrossrefSummaryTemplate
from cleancopywriter.html.templates import ValueReprTemplate
from cleancopywriter.html.templates import VariableSummaryTemplate
from cleancopywriter.html.writer import HtmlWriter


@dataclass
class DocnotesTransformer:
    """This transforms extracted docnotes instances into a set of
    HTML templates.
    """
    writer: HtmlWriter
    abstractifier: Abstractifier

    def should_include(
            self,
            metadata: SummaryMetadataProtocol
            ) -> bool:
        if metadata.extracted_inclusion is True:
            return True
        if metadata.extracted_inclusion is False:
            return False

        return metadata.to_document and not metadata.disowned

    def transform(
            self,
            docnotes: Docnotes
            ) -> dict[str, dict[str, HtmlTemplate]]:
        retval: dict[str, dict[str, HtmlTemplate]] = {}
        for pkg_name, summary_tree in docnotes.summaries.items():
            retval[pkg_name] = self._transform(summary_tree)

        return retval

    def _transform(
            self,
            summary_tree: SummaryTreeNode
            ) -> dict[str, HtmlTemplate]:
        """This does the actual transformation of a single summary tree
        node.
        """
        retval: dict[str, HtmlTemplate] = {}
        for summary_node in summary_tree.flatten():
            if summary_node.to_document:
                retval[summary_node.fullname] = self._dispatch_transform(
                    summary_node.module_summary)

        return retval

    @singledispatchmethod
    def _dispatch_transform(self, summary_node: SummaryBase) -> HtmlTemplate:
        return HtmlGenericElement(
            tag='p',
            body=[
                PlaintextTemplate(
                    f'unknown/unsupported node: ({type(summary_node)=}) '
                    + f'{summary_node.crossref} '
                    + f'({summary_node.metadata})')])

    @_dispatch_transform.register
    def _(self, summary_node: ModuleSummary) -> ModuleSummaryTemplate:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = self.render_doctext(summary_node.docstring)

        if summary_node.dunder_all is None:
            dunder_all = []
        else:
            dunder_all = dunder_all_factory(
                sorted(summary_node.dunder_all))

        return ModuleSummaryTemplate(
            fullname=summary_node.name,
            docstring=docstring,
            dunder_all=dunder_all,
            members=[
                self._dispatch_transform(member)
                for member in summary_node.members
                if self.should_include(member.metadata)])

    @_dispatch_transform.register
    def _(self, summary_node: VariableSummary) -> VariableSummaryTemplate:
        rendered_notes: list[HtmlTemplate] = []
        for note in summary_node.notes:
            rendered_notes.extend(self.render_doctext(note))

        return VariableSummaryTemplate(
            name=summary_node.name,
            typespec=
                [self.render_typespec(summary_node.typespec)]
                if summary_node.typespec is not None
                else (),
            notes=rendered_notes)

    @_dispatch_transform.register
    def _(self, summary_node: ClassSummary) -> ClassSummaryTemplate:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = self.render_doctext(summary_node.docstring)

        return ClassSummaryTemplate(
            name=summary_node.name,
            metaclass=
                [self.render_concrete_typespec(summary_node.metaclass)]
                if summary_node.metaclass is not None
                else (),
            docstring=docstring,
            bases=[
                self.render_concrete_typespec(base)
                for base in summary_node.bases],
            members=[
                self._dispatch_transform(member)
                for member in summary_node.members
                if self.should_include(member.metadata)])

    @_dispatch_transform.register
    def _(self, summary_node: CallableSummary) -> CallableSummaryTemplate:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = self.render_doctext(summary_node.docstring)

        return CallableSummaryTemplate(
            name=summary_node.name,
            docstring=docstring,
            color=summary_node.color,
            method_type=summary_node.method_type,
            is_generator=summary_node.is_generator,
            signatures=[
                self._dispatch_transform(signature)
                for signature in summary_node.signatures
                if self.should_include(signature.metadata)])

    @_dispatch_transform.register
    def _(self, summary_node: SignatureSummary) -> SignatureSummaryTemplate:
        if summary_node.docstring is None:
            docstring = []
        else:
            docstring = self.render_doctext(summary_node.docstring)

        return SignatureSummaryTemplate(
            params=[
                self._dispatch_transform(param)
                for param in summary_node.params
                if self.should_include(param.metadata)],
            retval=[
                self._dispatch_transform(summary_node.retval)],
            docstring=docstring)

    @_dispatch_transform.register
    def _(self, summary_node: ParamSummary) -> ParamSummaryTemplate:
        rendered_notes: list[HtmlTemplate] = []
        for note in summary_node.notes:
            rendered_notes.extend(self.render_doctext(note))

        rendered_default: list[ValueReprTemplate] = []
        if summary_node.default is not None:
            rendered_default.append(
                ValueReprTemplate(repr(summary_node.default)))

        return ParamSummaryTemplate(
            style=summary_node.style,
            name=summary_node.name,
            default=rendered_default,
            typespec=[self.render_typespec(summary_node.typespec)]
                if summary_node.typespec is not None
                else (),
            notes=rendered_notes)

    @_dispatch_transform.register
    def _(self, summary_node: RetvalSummary) -> RetvalSummaryTemplate:
        rendered_notes: list[HtmlTemplate] = []
        for note in summary_node.notes:
            rendered_notes.extend(self.render_doctext(note))

        return RetvalSummaryTemplate(
            typespec=[self.render_typespec(summary_node.typespec)]
                if summary_node.typespec is not None
                else (),
            notes=rendered_notes)

    def render_doctext(self, doctext: DocText) -> list[HtmlTemplate]:
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

        cst_doc = parse(doctext.value.encode('utf-8'))
        ast_doc = self.abstractifier.convert(cst_doc)
        return self.writer.write_node(ast_doc)

    def render_concrete_typespec(
            self,
            typespec: TypeSpec
            ) -> NormalizedConcreteTypeTemplate:
        """Use this to render the (concrete, ie, cannot be a union etc)
        typespec -- ie, metaclasses and base classes.
        """
        result = self.render_normalized_type(typespec.normtype)
        if not isinstance(result, NormalizedConcreteTypeTemplate):
            raise TypeError(
                'Invalid concrete type (metaclass or base)', typespec)

        return result

    def render_typespec(
            self,
            typespec: TypeSpec
            ) -> TypespecTemplate:
        tags: list[TypespecTagTemplate] = []

        for dc_field in fields(typespec):
            if dc_field.name != 'normtype':
                tags.append(TypespecTagTemplate(
                    key=dc_field.name,
                    value=getattr(typespec, dc_field.name)))

        return TypespecTemplate(
            normtype=[self.render_normalized_type(typespec.normtype)],
            typespec_tags=tags)

    @singledispatchmethod
    def render_normalized_type(
            self,
            normtype: NormalizedType
            ) -> NormalizedTypeTemplate:
        raise TypeError('Unknown normalized type!', normtype)

    @render_normalized_type.register
    def _(
            self,
            normtype: NormalizedUnionType
            ) -> NormalizedUnionTypeTemplate:
        return NormalizedUnionTypeTemplate(
            normtypes=[
                self.render_normalized_type(nested_normtype)
                for nested_normtype in normtype.normtypes])

    @render_normalized_type.register
    def _(
            self,
            normtype: NormalizedEmptyGenericType
            ) -> NormalizedEmptyGenericTypeTemplate:
        return NormalizedEmptyGenericTypeTemplate(
            params=[
                self.render_normalized_type(param_typespec.normtype)
                for param_typespec in normtype.params])

    @render_normalized_type.register
    def _(
            self,
            normtype: NormalizedConcreteType
            ) -> NormalizedConcreteTypeTemplate:
        primary_xref = normtype.primary

        if primary_xref.toplevel_name is None:
            shortname = qualname = f'<Module {primary_xref.module_name}>'
        else:
            # These are actually unknown in case of traversals...
            # TODO: that needs fixing! probably with <> brackets.
            shortname = primary_xref.toplevel_name
            qualname = (
                f'{primary_xref.module_name}:{primary_xref.toplevel_name}')

        return NormalizedConcreteTypeTemplate(
            primary=[UnlinkableCrossrefSummaryTemplate(
                qualname=qualname,
                shortname=shortname,
                traversals=
                    ''.join(_flatten_typespec_traversals(
                        normtype.primary.traversals))
                    if normtype.primary.traversals else None,)],
            params=[
                self.render_normalized_type(param_typespec.normtype)
                for param_typespec in normtype.params])

    @render_normalized_type.register
    def _(
            self,
            normtype: NormalizedSpecialType
            ) -> NormalizedSpecialTypeTemplate:
        return NormalizedSpecialTypeTemplate(
            type_=[specialform_type_factory(normtype)])

    @render_normalized_type.register
    def _(
            self,
            normtype: NormalizedLiteralType
            ) -> NormalizedLiteralTypeTemplate:
        return NormalizedLiteralTypeTemplate(
            values=[
                literal_value_factory(value)
                for value in normtype.values])


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
