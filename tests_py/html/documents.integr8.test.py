from __future__ import annotations

from inspect import cleandoc

import pytest

from cleancopywriter.html.documents import quickrender


class TestHtmlWriter:

    @pytest.mark.parametrize(
        'clc_text,expected_render_result',
        [
            ('[[^^link^^](https://www.test.example)]',
                '<clc-doc role="article"><clc-p><p><a href="https://www.test.example"><em>link</em></a></p></clc-p></clc-doc>'),  # noqa: E501, RUF100
            ('**foo**',
                '<clc-doc role="article"><clc-p><p><strong>foo</strong></p></clc-p></clc-doc>'),  # noqa: E501
            ('**^^bar^^**',
                '<clc-doc role="article"><clc-p><p><strong><em>bar</em></strong></p></clc-p></clc-doc>'),  # noqa: E501
            ('test',
                '<clc-doc role="article"><clc-p><p>test</p></clc-p></clc-doc>'),  # noqa: E501
            (cleandoc('''
                > Some titles
                    aren't even worth writing
                oh well'''),
                '<clc-doc role="article"><clc-block><h2>Some titles</h2><clc-p><p>aren&#x27;t even worth writing</p></clc-p></clc-block><clc-p><p>oh well</p></clc-p></clc-doc>'),  # noqa: E501
            (cleandoc('''
                > Docs can have titles too
                __doc_meta__: true
                <

                fly you fools'''),
                '<clc-doc role="article"><h1>Docs can have titles too</h1><clc-p><p>fly you fools</p></clc-p></clc-doc>'),  # noqa: E501
            (cleandoc('''
                ++  one
                ++  two
                help I'm stuck in a shoe

                3.. three
                4.. four
                and the shoe's stuck in a door'''),
                '<clc-doc role="article"><clc-p><ul><li><clc-p><p>one</p></clc-p></li><li><clc-p><p>two</p></clc-p></li></ul><p>help I&#x27;m stuck in a shoe</p></clc-p><clc-p><ol><li value="3"><clc-p><p>three</p></clc-p></li><li value="4"><clc-p><p>four</p></clc-p></li></ol><p>and the shoe&#x27;s stuck in a door</p></clc-p></clc-doc>'),  # noqa: E501
            ])
    def test_quickrenders(self, clc_text: str, expected_render_result: str):
        """Tests a number of small snippets and ensure the results match
        the expected value.
        """
        result = quickrender(clc_text)

        print(repr(result))
        assert result == expected_render_result
