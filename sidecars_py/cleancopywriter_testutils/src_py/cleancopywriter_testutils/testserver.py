from __future__ import annotations

from contextvars import ContextVar
from inspect import cleandoc
from pathlib import Path

import anyio
import uvicorn
from docnote_extract import gather as gather_docnotes
from docnote_extract.summaries import ModuleSummary
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import Response
from templatey.environments import RenderEnvironment
from templatey.prebaked.loaders import InlineStringTemplateLoader

from cleancopywriter.html.documents import HtmlDocumentCollection
from cleancopywriter.html.generic_templates import HtmlAttr
from cleancopywriter.html.generic_templates import HtmlGenericElement
from cleancopywriter.html.generic_templates import PlaintextTemplate

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
CSS_ROOT = REPO_ROOT / 'src_css'
APP_HOST = 'localhost'
APP_PORT = 7887
ANYIO_BACKEND = 'asyncio'
app = FastAPI()

_DOC_COLL: ContextVar[HtmlDocumentCollection] = ContextVar('_DOC_COLL')


@app.get('/cleancopywriter.css')
async def get_css():
    path = anyio.Path(CSS_ROOT) / 'cleancopywriter.css'
    text = await path.read_text('utf-8')
    return Response(content=text, media_type='text/css')


@app.get('/ccw_docs')
async def list_docs():
    doc_coll = _DOC_COLL.get()

    items = []
    for id_ in sorted(doc_coll):
        items.append(HtmlGenericElement(
            tag='li',
            body=[HtmlGenericElement(
                tag='a',
                attrs=[HtmlAttr(key='href', value=f'/ccw_docs/{id_}')],
                body=[PlaintextTemplate(text=id_)])]))
    body = HtmlGenericElement(
        tag='ul',
        body=items)

    render_env = RenderEnvironment(
        InlineStringTemplateLoader(),
        strict_interpolation_validation=False)

    return _html_quickfmt(
        'list docs',
        await render_env.render_async(body))


@app.get('/ccw_docs/{doc_id}')
async def get_doc(doc_id: str):
    doc_coll = _DOC_COLL.get()

    doc = doc_coll.get(doc_id)
    if doc is None:
        return HTMLResponse('Not found', 404)

    render_env = RenderEnvironment(
        InlineStringTemplateLoader(),
        strict_interpolation_validation=False)

    return _html_quickfmt(
        doc_id,
        await render_env.render_async(doc.intermediate_representation))


def _html_quickfmt(title: str, rendered_body: str) -> HTMLResponse:
    """This is an extremely quick and dirty convenience function to wrap
    a rendered body in an extremely basic HTML page as suitable for
    fastAPI.
    """
    return HTMLResponse(cleandoc(f'''
        <!doctype html>
        <html>
        <head>
            <title>cleancopywriter | {title}</title>
            <link rel="stylesheet" href="/cleancopywriter.css">
        </head>
        <body>
            {rendered_body}
        </body>
        </html>
        '''))


def _make_id(summary: ModuleSummary) -> str:
    """This is a temporary stand-in for a proper mechanism for making
    IDs for documents.
    """
    return f'docnote({summary.name})'


def entrypoint():
    doc_coll = HtmlDocumentCollection(
        target_resolver=lambda *args, **kwargs: '#')
    finnr_docnotes = gather_docnotes(['finnr'])
    package_summary_tree = finnr_docnotes.summaries['finnr']
    for summary_tree_node in package_summary_tree.flatten():
        if summary_tree_node.to_document:
            doc_coll.add(
                _make_id(summary_tree_node.module_summary),
                docnote_src=summary_tree_node)

    anyio.run(main, doc_coll, backend=ANYIO_BACKEND)


async def main(doc_coll: HtmlDocumentCollection):
    config = uvicorn.Config(
        app, host=APP_HOST, port=APP_PORT, log_level="info")
    server = uvicorn.Server(config)

    ctx_token = _DOC_COLL.set(doc_coll)
    try:
        await server.serve()
    finally:
        _DOC_COLL.reset(ctx_token)


if __name__ == '__main__':
    entrypoint()
