# 狼人杀观战控制台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AgentScope 三国狼人杀增加可配置的观战模式，并用横幅、阶段区块、角色表和结算摘要提升控制台可读性。

**Architecture:** `GameConfig` 负责解析并保存观战开关；`GameConsole` 只负责生成和打印稳定的纯文本布局；`ThreeKingdomsWerewolfGame` 负责根据配置决定私密内容是否可见，并向昼夜阶段管理器提供统一展示入口。游戏规则、Agent 消息 metadata 和记忆投递规则保持不变。

**Tech Stack:** Python 3.12、AgentScope 1.x、pytest、pytest-asyncio、Ruff、Pyright、Mypy。

## Global Constraints

- `SPECTATOR_MODE` 默认关闭；开启时展示完整角色表及私密行动，关闭时隐藏未公开身份和私密内容。
- 游戏结束后无论观战模式是否开启，都展示最终完整身份表。
- 私密消息始终以原始内容发送给正确的 Agent；脱敏只影响控制台和主持人展示日志。
- 不改变狼人杀规则、Agent 提示词、消息 metadata、胜负判断或现有模型供应商行为。
- 不增加第三方终端 UI 或颜色依赖，日志重定向后必须可读。
- 每段关键代码使用明确中文注释，公开方法使用中文文档注释。
- 保留工作区中 `README.md`、`config.py`、`model_factory.py` 和 `tests/test_model_factory.py` 的现有 DeepSeek 改动，不覆盖、不回退、不误提交。

## File Structure

- Modify: `05-agent/framework/agentscope-v1-demo/config.py` — 解析 `SPECTATOR_MODE` 并写入不可变游戏配置。
- Modify: `05-agent/framework/agentscope-v1-demo/game_messages.py` — 提供横幅、阶段、角色表、私密脱敏和结算摘要的统一纯文本展示。
- Modify: `05-agent/framework/agentscope-v1-demo/roles.py` — 让主持人根据游戏配置打印或隐藏私密内容，同时保留原始 `Msg`。
- Modify: `05-agent/framework/agentscope-v1-demo/game.py` — 配置主持人展示策略，打印开局/结束总览，集中展示玩家消息和轮次摘要。
- Modify: `05-agent/framework/agentscope-v1-demo/day_phases.py` — 声明白天、讨论、投票和猎人阶段区块。
- Modify: `05-agent/framework/agentscope-v1-demo/night_phases.py` — 通过游戏统一入口展示私密行动，避免绕过观战模式。
- Create: `05-agent/framework/agentscope-v1-demo/tests/test_game_messages.py` — 验证所有新增文本布局和边界格式。
- Modify: `05-agent/framework/agentscope-v1-demo/tests/test_config.py` — 验证观战配置解析。
- Modify: `05-agent/framework/agentscope-v1-demo/tests/test_game.py` — 验证私密消息不影响 Agent 记忆，并验证主循环阶段与结算展示。
- Modify: `05-agent/framework/agentscope-v1-demo/README.md` — 说明开关、身份泄露风险和新的消息布局。

---

### Task 1: 观战模式配置

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/config.py:9-108`
- Test: `05-agent/framework/agentscope-v1-demo/tests/test_config.py`

**Interfaces:**
- Consumes: `build_argument_parser() -> argparse.ArgumentParser` 和 `load_config(args, environ) -> GameConfig`。
- Produces: `SPECTATOR_MODE_KEY = "SPECTATOR_MODE"`、`GameConfig.spectator_mode: bool`、`_parse_bool(value: str) -> bool`。

- [ ] **Step 1: 写入失败的配置测试**

在 `tests/test_config.py` 增加以下测试，复用完整模型环境变量：

```python
@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("true", True), ("1", True), ("yes", True), ("false", False), ("0", False), ("no", False)],
)
def test_load_config_parses_spectator_mode(raw_value: str, expected: bool) -> None:
    """观战模式接受常见的布尔环境变量写法。"""
    args = build_argument_parser().parse_args([])
    config = load_config(
        args,
        environ={
            "LLM_API_KEY": "test-key",
            "LLM_MODEL_ID": "test-model",
            "LLM_BASE_URL": "https://example.com/api",
            "SPECTATOR_MODE": raw_value,
        },
    )
    assert config.spectator_mode is expected


def test_load_config_disables_spectator_mode_by_default() -> None:
    """未配置时必须保护隐藏身份。"""
    args = build_argument_parser().parse_args([])
    config = load_config(
        args,
        environ={
            "LLM_API_KEY": "test-key",
            "LLM_MODEL_ID": "test-model",
            "LLM_BASE_URL": "https://example.com/api",
        },
    )
    assert config.spectator_mode is False


def test_load_config_rejects_invalid_spectator_mode() -> None:
    """非法布尔值必须在游戏启动前报告。"""
    args = build_argument_parser().parse_args([])
    with pytest.raises(ConfigError, match="SPECTATOR_MODE"):
        load_config(
            args,
            environ={
                "LLM_API_KEY": "test-key",
                "LLM_MODEL_ID": "test-model",
                "LLM_BASE_URL": "https://example.com/api",
                "SPECTATOR_MODE": "sometimes",
            },
        )
```

- [ ] **Step 2: 运行配置测试并确认失败**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_config.py`

Expected: FAIL，错误指向 `GameConfig` 缺少 `spectator_mode` 或非法值未抛出 `ConfigError`。

- [ ] **Step 3: 实现严格的布尔配置解析**

在 `config.py` 增加常量、字段和解析函数，并在 `load_config()` 中读取环境变量：

```python
SPECTATOR_MODE_KEY = "SPECTATOR_MODE"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _parse_bool(value: str) -> bool:
    """解析环境变量布尔值，非法值直接阻止游戏启动。"""
    normalized_value = value.strip().lower()
    if normalized_value in TRUE_VALUES:
        return True
    if normalized_value in FALSE_VALUES:
        return False
    raise ConfigError(
        f"{SPECTATOR_MODE_KEY} 仅支持：true/false、1/0、yes/no、on/off"
    )
```

`GameConfig` 增加：

```python
spectator_mode: bool = False
```

`load_config()` 的返回值增加：

```python
spectator_mode=_parse_bool(environment.get(SPECTATOR_MODE_KEY, "false")),
```

- [ ] **Step 4: 运行配置测试并确认通过**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_config.py`

Expected: PASS，包含新增参数化用例。

### Task 2: 统一控制台视觉组件

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/game_messages.py:1-106`
- Create: `05-agent/framework/agentscope-v1-demo/tests/test_game_messages.py`

**Interfaces:**
- Consumes: 玩家名字符串序列、`roles: Mapping[str, str]`、死亡玩家名序列。
- Produces: `GameConsole.banner(title: str) -> None`、`GameConsole.section(title: str, subtitle: str | None = None) -> None`、`GameConsole.role_table(player_names: Sequence[str], roles: Mapping[str, str], reveal_roles: bool, title: str = "角色总览") -> None`、`GameConsole.round_summary(title: str, dead_players: Sequence[str], alive_players: Sequence[str]) -> None`、`GameConsole.visible_content(content: str, reveal_private: bool) -> str`。

- [ ] **Step 1: 写入失败的控制台格式测试**

创建 `tests/test_game_messages.py`：

```python
"""游戏控制台布局测试。"""

from game_messages import GameConsole


def test_banner_and_section_add_visual_boundaries(capsys) -> None:
    """横幅和阶段必须通过边框及空行与普通消息区分。"""
    GameConsole.banner("三国狼人杀 · 游戏开始")
    GameConsole.section("第 1 夜", "夜间行动")
    output = capsys.readouterr().out
    assert "════════" in output
    assert "三国狼人杀 · 游戏开始" in output
    assert "第 1 夜 · 夜间行动" in output
    assert "┌" in output and "└" in output
    assert "\n\n" in output


def test_role_table_hides_roles_outside_spectator_mode(capsys) -> None:
    """非观战模式的开局角色表不得泄露真实身份。"""
    GameConsole.role_table(
        ["刘备", "曹操"],
        {"刘备": "村民", "曹操": "狼人"},
        reveal_roles=False,
    )
    output = capsys.readouterr().out
    assert "01. 刘备" in output
    assert "02. 曹操" in output
    assert output.count("未公开") == 2
    assert "狼人" not in output


def test_role_table_reveals_roles_for_spectators(capsys) -> None:
    """观战模式必须展示完整身份。"""
    GameConsole.role_table(
        ["刘备", "曹操"],
        {"刘备": "村民", "曹操": "狼人"},
        reveal_roles=True,
    )
    output = capsys.readouterr().out
    assert "刘备" in output and "村民" in output
    assert "曹操" in output and "狼人" in output


def test_visible_content_redacts_private_information() -> None:
    """关闭观战模式时私密内容统一脱敏。"""
    assert GameConsole.visible_content("毒杀刘备", reveal_private=False) == "内容已隐藏"
    assert GameConsole.visible_content("毒杀刘备", reveal_private=True) == "毒杀刘备"


def test_round_summary_handles_no_deaths(capsys) -> None:
    """无人死亡时结算仍必须明确可读。"""
    GameConsole.round_summary("第 1 夜结算", [], ["刘备", "曹操"])
    output = capsys.readouterr().out
    assert "第 1 夜结算" in output
    assert "死亡玩家：无人死亡" in output
    assert "存活玩家：刘备、曹操" in output
    assert "当前人数：2" in output
```

- [ ] **Step 2: 运行新增测试并确认失败**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_game_messages.py`

Expected: FAIL，提示 `GameConsole` 缺少新增公开方法。

- [ ] **Step 3: 实现无依赖的纯文本展示方法**

在 `game_messages.py` 引入 `Mapping` 和 `Sequence`，定义固定宽度边框，并实现公开方法：

```python
from collections.abc import Mapping, Sequence

WIDE_DIVIDER = "═" * 40
THIN_DIVIDER = "─" * 40


@classmethod
def banner(cls, title: str) -> None:
    """打印游戏开始或结束横幅。"""
    print(f"\n{WIDE_DIVIDER}\n{title.center(32)}\n{WIDE_DIVIDER}\n")


@classmethod
def section(cls, title: str, subtitle: str | None = None) -> None:
    """打印具有明确边界的游戏阶段标题。"""
    label = f"{title} · {subtitle}" if subtitle else title
    print(f"\n┌{THIN_DIVIDER}┐\n│ {label}\n└{THIN_DIVIDER}┘\n")


@staticmethod
def visible_content(content: str, reveal_private: bool) -> str:
    """根据观战模式返回原始私密内容或统一脱敏文案。"""
    return content if reveal_private else "内容已隐藏"
```

`role_table()` 接受可选 `title`，按输入顺序打印标题、两位序号、玩家名和角色；`round_summary()` 使用 `无人死亡`、`无人存活` 处理空列表。实现时使用简单空格分列，不引入 ANSI 颜色或额外包。

- [ ] **Step 4: 运行控制台测试并确认通过**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_game_messages.py`

Expected: PASS，5 个新增测试全部通过。

### Task 3: 私密消息展示边界

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/roles.py:131-161`
- Modify: `05-agent/framework/agentscope-v1-demo/game.py:24-153`
- Modify: `05-agent/framework/agentscope-v1-demo/night_phases.py:39-284`
- Test: `05-agent/framework/agentscope-v1-demo/tests/test_game.py`

**Interfaces:**
- Consumes: `GameConfig.spectator_mode` 和 `GameConsole.visible_content(content, reveal_private)`。
- Produces: `GameModerator.set_private_content_visible(visible: bool) -> None`、`ThreeKingdomsWerewolfGame.display_player_message(...) -> None`。

- [ ] **Step 1: 写入失败的私密消息测试**

在 `tests/test_game.py` 增加：

```python
@pytest.mark.asyncio
async def test_private_notice_is_redacted_only_on_console() -> None:
    """关闭观战模式时控制台隐藏私密内容，但接收 Agent 获得原文。"""
    game = ThreeKingdomsWerewolfGame(
        GameConfig("key", "model", "https://example.com", spectator_mode=False)
    )
    witch = FakeAgent("貂蝉")
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        await game.notify_private(witch, "今晚刘备被狼人击杀")

    assert "内容已隐藏" in output.getvalue()
    assert "刘备" not in output.getvalue()
    assert witch.observed[0].get_text_content() == "今晚刘备被狼人击杀"


@pytest.mark.asyncio
async def test_spectator_mode_prints_private_notice() -> None:
    """开启观战模式时控制台展示私密行动原文。"""
    game = ThreeKingdomsWerewolfGame(
        GameConfig("key", "model", "https://example.com", spectator_mode=True)
    )
    witch = FakeAgent("貂蝉")
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        await game.notify_private(witch, "今晚刘备被狼人击杀")

    assert "今晚刘备被狼人击杀" in output.getvalue()
```

- [ ] **Step 2: 运行私密消息测试并确认失败**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_game.py -k private_notice`

Expected: FAIL，关闭观战模式时仍能在标准输出看到 `刘备`。

- [ ] **Step 3: 让主持人只脱敏展示副本**

在 `GameModerator` 中增加实例字段和公开设置方法：

```python
self._private_content_visible = False


def set_private_content_visible(self, visible: bool) -> None:
    """设置主持人私密消息是否在控制台显示原文。"""
    self._private_content_visible = visible
```

`announce()` 创建的 `Msg.content` 始终保留原始 `content`；仅当 `visibility is MessageVisibility.PRIVATE` 时，为控制台和 `game_log` 计算：

```python
display_content = GameConsole.visible_content(
    content,
    reveal_private=self._private_content_visible,
)
```

公开消息继续直接显示原文。

- [ ] **Step 4: 集中玩家消息的隐私判断**

在 `ThreeKingdomsWerewolfGame.__init__()` 中调用：

```python
self.moderator.set_private_content_visible(config.spectator_mode)
```

新增统一入口：

```python
def display_player_message(
    self,
    agent: AgentBase,
    message_type: MessageType,
    content: str,
    recipient: str | None = None,
) -> None:
    """按照消息可见范围打印玩家发言或行动。"""
    private_types = {
        MessageType.PRIVATE_SPEECH,
        MessageType.PRIVATE_ACTION,
    }
    display_content = (
        GameConsole.visible_content(content, self.config.spectator_mode)
        if message_type in private_types
        else content
    )
    GameConsole.player(agent.name, message_type, display_content, recipient)
```

让 `display_agent_reply()` 调用该入口；将 `night_phases.py` 中狼人投票、守护、预言家查验和女巫用药的直接 `GameConsole.player(...)` 替换为 `self.game.display_player_message(...)`。公开发言与系统警告不变。

- [ ] **Step 5: 运行私密边界及昼夜阶段测试**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_game.py tests/test_night_phases.py tests/test_day_phases.py`

Expected: PASS；既有 Agent 行为和技能规则测试不受影响。

### Task 4: 游戏阶段、角色总览与轮次结算

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/game.py:195-340`
- Modify: `05-agent/framework/agentscope-v1-demo/day_phases.py:22-166`
- Test: `05-agent/framework/agentscope-v1-demo/tests/test_game.py`

**Interfaces:**
- Consumes: Task 2 的 `GameConsole.banner()`、`section()`、`role_table()` 和 `round_summary()`。
- Produces: `ThreeKingdomsWerewolfGame.display_game_over(winner: str) -> None`，以及完整的阶段展示调用顺序。

- [ ] **Step 1: 扩展主循环输出测试**

修改现有 `test_game_announces_draw_after_max_rounds()`，保留输出文本并增加断言：

```python
output = io.StringIO()
with contextlib.redirect_stdout(output):
    result = await game.run_game()

console_output = output.getvalue()
assert result == "平局"
assert "第 1 夜 · 夜间行动" in console_output
assert "第 1 夜结算" in console_output
assert "第 1 天" in console_output
assert "第 1 天结算" in console_output
assert "三国狼人杀 · 游戏结束" in console_output
assert "最终身份" in console_output
```

增加一个开局角色展示测试。通过 monkeypatch `create_player()` 返回 `FakeAgent`，并 monkeypatch `random.sample()` 返回固定角色名，分别断言 `spectator_mode=False` 时输出 `未公开`、`spectator_mode=True` 时输出 `狼人` 和 `村民`。

- [ ] **Step 2: 运行游戏测试并确认失败**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_game.py`

Expected: FAIL，输出中尚不存在结构化阶段、结算和最终身份标题。

- [ ] **Step 3: 接入开局和结束展示**

在 `setup_game()` 开始时打印：

```python
GameConsole.banner("三国狼人杀 · 游戏开始")
GameConsole.system(
    MessageType.STATE,
    f"观战模式：{'开启' if self.config.spectator_mode else '关闭'}",
)
```

玩家创建完成后调用：

```python
GameConsole.role_table(
    [player.name for player in self.alive_players],
    self.roles,
    reveal_roles=self.config.spectator_mode,
    title="角色总览",
)
```

增加结束展示方法，在胜负或平局公告广播后调用：

```python
def display_game_over(self, winner: str) -> None:
    """打印游戏结果和所有玩家的最终身份。"""
    GameConsole.banner("三国狼人杀 · 游戏结束")
    GameConsole.system(MessageType.RESULT, f"胜负结果：{winner}")
    GameConsole.role_table(
        list(self.roles),
        self.roles,
        reveal_roles=True,
        title="最终身份",
    )
```

`_announce_winner_if_any()` 和最大轮数平局分支都必须调用该方法，保证所有退出路径展示最终身份。

- [ ] **Step 4: 接入昼夜、讨论、投票和猎人阶段**

`run_game()` 在每夜开始前调用：

```python
GameConsole.section(f"第 {round_num} 夜", "夜间行动")
```

夜间死亡玩家更新后调用：

```python
GameConsole.round_summary(
    f"第 {round_num} 夜结算",
    night_deaths,
    [player.name for player in self.alive_players],
)
```

`DayPhaseManager.day_phase()` 分别在天亮公告、自由讨论和投票前调用：

```python
GameConsole.section(f"第 {round_num} 天", "白天公布")
GameConsole.section("公开讨论")
GameConsole.section("放逐投票")
```

`hunter_phase()` 在确认死亡玩家确实是可发动技能的猎人后调用：

```python
GameConsole.section("猎人技能", "身份公开、遗言与开枪")
```

白天死亡玩家更新后调用 `round_summary(f"第 {round_num} 天结算", ...)`。删除原有单行“第 N 轮结束”状态消息，避免重复。

- [ ] **Step 5: 运行游戏与阶段测试**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_game.py tests/test_day_phases.py tests/test_night_phases.py`

Expected: PASS；阶段标题不改变 Agent 记忆条数，结算名单使用更新后的实际存活状态。

### Task 5: 文档、全量验证与聚合提交

**Files:**
- Modify: `05-agent/framework/agentscope-v1-demo/README.md:15-90`
- Verify: `05-agent/framework/agentscope-v1-demo/**`

**Interfaces:**
- Consumes: Tasks 1-4 的最终配置名和输出行为。
- Produces: 用户可直接复制的环境变量说明和已验证的完整提交。

- [ ] **Step 1: 更新 README 配置示例和观战说明**

在环境变量示例增加：

```bash
# 可选：开启后显示所有身份和私密行动，默认 false
export SPECTATOR_MODE="true"
```

在消息说明中明确：

```markdown
### 观战模式

- 默认关闭：开局身份显示为“未公开”，私密通知和私密行动在控制台显示“内容已隐藏”。
- 开启方式：设置 `SPECTATOR_MODE=true`，适合单人演示和调试。
- 风险提示：开启后会显示狼人协商、神职行动和完整身份，不适合玩家共用同一终端。
- 无论是否开启，游戏结束后都会显示最终身份表。
```

保留 README 中现有 DeepSeek provider 文档，不修改其语义。

- [ ] **Step 2: 运行针对性测试**

Run: `cd 05-agent/framework/agentscope-v1-demo && uv run pytest -q tests/test_config.py tests/test_game_messages.py tests/test_game.py tests/test_day_phases.py tests/test_night_phases.py`

Expected: PASS。

- [ ] **Step 3: 运行完整质量检查**

依次运行：

```bash
cd 05-agent/framework/agentscope-v1-demo
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run mypy
uv run python -m compileall -q .
```

Expected: 所有命令退出码为 0；`pytest` 无失败，静态检查无错误。

- [ ] **Step 4: 复查工作区和提交边界**

Run:

```bash
git diff --check
git status --short
git diff -- 05-agent/framework/agentscope-v1-demo
```

Expected: 观战功能改动符合设计；`model_factory.py` 和 `tests/test_model_factory.py` 的 DeepSeek 改动仍保持未暂存状态。对同时包含 DeepSeek 与观战修改的 `config.py`、`README.md`，生成只包含观战相关 hunks 的补丁并使用 `git apply --cached`，不得直接 `git add` 整个文件。

- [ ] **Step 5: 提交观战体验改动**

仅暂存以下内容：

- `config.py` 中 `SPECTATOR_MODE` 常量、布尔解析和配置字段。
- `README.md` 中观战模式说明。
- `game_messages.py`、`roles.py`、`game.py`、`day_phases.py`、`night_phases.py` 的观战展示改动。
- `tests/test_config.py`、`tests/test_game_messages.py`、`tests/test_game.py` 的相关测试。

Run:

```bash
git commit -m "feat: 优化狼人杀观战控制台"
```

Expected: 生成一个 Conventional Commits 提交；提交后现有 DeepSeek 改动仍在工作区，未被包含在该提交中。
