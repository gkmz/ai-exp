"""命令行入口测试。"""

import contextlib
import io

import pytest

from main import run


@pytest.mark.asyncio
async def test_missing_environment_returns_nonzero_exit_code() -> None:
    """配置缺失时入口必须返回非零状态码。"""
    with contextlib.redirect_stdout(io.StringIO()):
        exit_code = await run([], environ={})

    assert exit_code == 2
