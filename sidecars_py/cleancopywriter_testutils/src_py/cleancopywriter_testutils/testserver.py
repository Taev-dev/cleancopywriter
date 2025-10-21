from __future__ import annotations

from inspect import cleandoc
from pathlib import Path

import anyio
import uvicorn
from cleancopy import Abstractifier
from cleancopy import parse
from docnote_extract import gather as gather_docnotes
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.responses import Response
from templatey.environments import RenderEnvironment
from templatey.prebaked.loaders import InlineStringTemplateLoader

from cleancopywriter.html.documents import HtmlDocumentCollection
from cleancopywriter.html.templates import ModuleSummaryTemplate

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
CSS_ROOT = REPO_ROOT / 'src_css'
APP_HOST = 'localhost'
APP_PORT = 7887
ANYIO_BACKEND = 'asyncio'
app = FastAPI()
finnr_docnotes = gather_docnotes(['finnr'])


@app.get('/cleancopywriter.css')
async def get_css():
    path = anyio.Path(CSS_ROOT) / 'cleancopywriter.css'
    text = await path.read_text('utf-8')
    return Response(content=text, media_type='text/css')


@app.get('/docs/iso')
async def doc_iso():
    return await _quickrender('finnr.iso')


@app.get('/docs/money')
async def doc_money():
    return await _quickrender('finnr.money')


@app.get('/docs/currency')
async def doc_currency():
    return await _quickrender('finnr.currency')


async def _quickrender(fullname: str) -> HTMLResponse:
    doccol = HtmlDocumentCollection()
    package_summary_tree = finnr_docnotes.summaries['finnr']
    target_module_summary = package_summary_tree.find(fullname).module_summary

    templatified = ModuleSummaryTemplate.from_summary(
        target_module_summary,
        doccol)

    render_env = RenderEnvironment(InlineStringTemplateLoader(), strict_interpolation_validation=False)
    rendered = await render_env.render_async(templatified)

    # cst_doc = parse(clc_text.encode('utf-8'))
    # ast_doc = Abstractifier().convert(cst_doc)
    # templates = HtmlWriter().write_node(ast_doc)
    # root_template = templates[0]
    # await render_env.render_async(root_template)

    return HTMLResponse(cleandoc(f'''
        <!doctype html>
        <html>
        <head>
            <title>cleancopywriter ({fullname})</title>
            <link rel="stylesheet" href="/cleancopywriter.css">
        </head>
        <body>
            {rendered}
        </body>
        </html>
        '''))


def entrypoint():
    anyio.run(main, backend=ANYIO_BACKEND)


async def main():
    config = uvicorn.Config(
        app, host=APP_HOST, port=APP_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == '__main__':
    entrypoint()
