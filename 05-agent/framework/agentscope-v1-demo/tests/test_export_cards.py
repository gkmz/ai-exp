"""完整终端记录命令行入口测试。"""

from pathlib import Path

from export_cards import main


def test_main_exports_complete_terminal_record(tmp_path: Path, capsys) -> None:
    """命令行应直接把完整输入导出到指定目录。"""
    input_path = tmp_path / "game.txt"
    output_path = tmp_path / "cards"
    input_path.write_text(
        "[系统][状态] 游戏开始\n[玩家][公开发言][刘备] 先听听大家的判断。",
        encoding="utf-8",
    )

    exit_code = main([str(input_path), "--output-dir", str(output_path)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "完整记录" in output
    assert len(list(output_path.glob("*.png"))) == 1


def test_main_reports_empty_input(tmp_path: Path, capsys) -> None:
    """命令行遇到空文件时应返回非零状态和中文错误。"""
    input_path = tmp_path / "empty.txt"
    input_path.write_text("", encoding="utf-8")

    exit_code = main([str(input_path)])

    assert exit_code == 1
    assert "导出失败：输入文件为空" in capsys.readouterr().err
