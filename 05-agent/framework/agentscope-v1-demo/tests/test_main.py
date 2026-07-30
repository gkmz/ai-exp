"""命令行入口测试。"""

import contextlib
import io

import pytest

import main as main_module
from main import main, run


@pytest.mark.asyncio
async def test_missing_environment_returns_nonzero_exit_code() -> None:
    """配置缺失时入口必须返回非零状态码。"""
    with contextlib.redirect_stdout(io.StringIO()):
        exit_code = await run([], environ={})

    assert exit_code == 2


def test_keyboard_interrupt_exits_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用户按下 Ctrl+C 时应显示退出提示并返回标准中断退出码。"""

    def interrupt(coroutine: object) -> None:
        """模拟 asyncio.run 完成协程清理后抛出键盘中断。"""
        coroutine.close()  # type: ignore[attr-defined]
        raise KeyboardInterrupt

    monkeypatch.setattr(main_module.asyncio, "run", interrupt)

    with contextlib.redirect_stdout(io.StringIO()) as output:
        with pytest.raises(SystemExit) as exit_info:
            main()

    assert exit_info.value.code == 130
    assert "[系统][状态] 游戏已退出" in output.getvalue()
