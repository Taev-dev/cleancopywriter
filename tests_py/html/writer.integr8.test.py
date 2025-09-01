from __future__ import annotations

from inspect import cleandoc

import pytest

from cleancopywriter.html.writer import HtmlWriter


class TestHtmlWriter:

    @pytest.mark.parametrize(
        'clc_text,expected_render_result',
        [
            ('[[^^link^^](https://www.test.example)]',
                '<article><p><a href="https://www.test.example"><em>link</em></a></p></article>'),
            ('**foo**',
                '<article><p><strong>foo</strong></p></article>'),
            ('**^^bar^^**',
                '<article><p><strong><em>bar</em></strong></p></article>'),
            ('test',
                '<article><p>test</p></article>'),
            (cleandoc('''
                > Some titles
                    aren't even worth writing
                oh well'''),
                '<article><section><h2>Some titles</h2><p>aren&#x27;t even worth writing</p></section><p>oh well</p></article>'),  # noqa: E501
            (cleandoc('''
                > Docs can have titles too
                __doc_meta__: true
                <

                fly you fools'''),
                '<article><h1>Docs can have titles too</h1><p>fly you fools</p></article>'),  # noqa: E501
            (cleandoc('''
                ++  one
                ++  two
                help I'm stuck in a shoe

                3.. three
                4.. four
                and the shoe's stuck in a door'''),
                '<article><p><ul><li><p>one</p></li><li><p>two</p></li></ul>help I&#x27;m stuck in a shoe</p><p><ol><li value="3"><p>three</p></li><li value="4"><p>four</p></li></ol>and the shoe&#x27;s stuck in a door</p></article>'),  # noqa: E501
            ])
    def test_quickrenders(self, clc_text: str, expected_render_result: str):
        """Tests a number of small snippets and ensure the results match
        the expected value.
        """
        writer = HtmlWriter()

        result = writer.quickrender(clc_text)

        assert result == expected_render_result
