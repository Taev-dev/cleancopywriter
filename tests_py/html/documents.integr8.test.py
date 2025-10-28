from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from cleancopywriter.html.documents import quickrender

tvec_dir = Path(__file__).parent / '_documents.integr8.test'


@dataclass
class _PartialTvec:
    clc_text: str | None = None
    expected_render_result: str | None = None


@dataclass
class _Tvec:
    name: str
    clc_text: str
    expected_render_result: str

    @classmethod
    def parameter_idfunc(cls, val: _Tvec) -> str:
        return val.name


def _load_tvecs() -> list[_Tvec]:
    tvecs: dict[str, _PartialTvec] = defaultdict(_PartialTvec)
    for path in tvec_dir.iterdir():
        if path.is_file():
            if path.suffix == '.clc':
                tvecs[path.stem].clc_text = path.read_text('utf-8')
            elif path.suffix == '.html':
                tvecs[path.stem].expected_render_result = path.read_text(
                    'utf-8')
            else:
                raise ValueError(
                    'Improper tvec suffix for documents integr8 test')

    results: list[_Tvec] = []
    for name, tvec in tvecs.items():
        if (
            tvec.clc_text is None
            or tvec.expected_render_result is None
        ):
            raise ValueError(
                'Improper (partial) tvec pair for documents integr8 test',
                name)

        results.append(_Tvec(name, tvec.clc_text, tvec.expected_render_result))

    return results


@contextmanager
def write_mismatch_to_file(tvec_name: str, result: str):
    """This is a quick debugging helper (useful during interactive
    debugging of tests; deliberately not included unless you temporarily
    modify the test case to use it) that catches and re-raises any
    assertion error, writing out the actual result to a file on disk
    for comparison.
    """
    try:
        yield
    except AssertionError:
        (tvec_dir / f'{tvec_name}.result.html').write_text(result, 'utf-8')
        raise


class TestHtmlWriter:

    @pytest.mark.parametrize(
        'tvec',
        _load_tvecs(),
        ids=_Tvec.parameter_idfunc)
    def test_quickrenders(self, tvec: _Tvec):
        """Tests a number of small snippets and ensure the results match
        the expected value.
        """
        result = quickrender(tvec.clc_text)

        assert result == tvec.expected_render_result
