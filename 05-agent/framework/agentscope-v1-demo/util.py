import random
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Dict, List, Optional

from agentscope.agent import ReActAgent
from agentscope.message import Msg

CHINESE_NAMES = [
    "刘备",
    "关羽",
    "张飞",
    "诸葛亮",
    "赵云",
    "曹操",
    "司马懿",
    "典韦",
    "许褚",
    "夏侯惇",
    "孙权",
    "周瑜",
    "陆逊",
    "甘宁",
    "太史慈",
    "吕布",
    "貂蝉",
    "董卓",
    "袁绍",
    "袁术",
]


def get_chinese_name(character: str) -> str:
    """获取中文角色名"""
    if character and character in CHINESE_NAMES:
        return character
    return random.choice(CHINESE_NAMES)


def format_player_list(players: list[ReActAgent], show_roles: bool = False) -> str:
    """格式化玩家列表为中文显示"""
    if not players:
        return "无玩家"

    if show_roles:
        return "、".join([f"{p.name}({getattr(p, 'role', '未知')})" for p in players])
    else:
        return "、".join([p.name for p in players])


def majority_vote_cn(
    votes: Mapping[str, str | None],
) -> tuple[str | None, int]:
    """统计有效票；平票或无人获得有效票时返回无人出局。"""
    valid_targets = [target for target in votes.values() if target is not None]
    if not valid_targets:
        return None, 0

    vote_counts = Counter(valid_targets)
    highest_count = max(vote_counts.values())
    highest_targets = [
        target for target, count in vote_counts.items() if count == highest_count
    ]
    if len(highest_targets) != 1:
        return None, highest_count

    return highest_targets[0], highest_count


def check_winning_cn(
    alive_players: Sequence[ReActAgent], roles: Mapping[str, str]
) -> Optional[str]:
    """按照屠边规则检查游戏胜利条件。"""
    missing_players = [
        player.name for player in alive_players if player.name not in roles
    ]
    if missing_players:
        raise ValueError(f"缺少玩家角色信息：{', '.join(missing_players)}")

    alive_roles = [roles[player.name] for player in alive_players]
    werewolf_count = alive_roles.count("狼人")
    villager_count = alive_roles.count("村民")
    god_count = sum(role not in {"狼人", "村民"} for role in alive_roles)

    if werewolf_count == 0:
        return "好人阵营胜利！所有狼人已被淘汰！"
    if villager_count == 0:
        return "狼人阵营胜利！所有村民已被淘汰！"
    if god_count == 0:
        return "狼人阵营胜利！所有神职已被淘汰！"

    return None


def analyze_speech_pattern(speech: str) -> Dict[str, Any]:
    """分析发言模式（中文优化）"""
    analysis = {
        "word_count": len(speech),
        "confidence_keywords": 0,
        "doubt_keywords": 0,
        "emotion_score": 0,
    }

    # 中文关键词分析
    confidence_words = ["确定", "肯定", "一定", "绝对", "必须", "显然"]
    doubt_words = ["可能", "也许", "或许", "怀疑", "不确定", "感觉"]

    for word in confidence_words:
        analysis["confidence_keywords"] += speech.count(word)

    for word in doubt_words:
        analysis["doubt_keywords"] += speech.count(word)

    # 简单情感分析
    positive_words = ["好", "棒", "赞", "支持", "同意"]
    negative_words = ["坏", "差", "反对", "不行", "错误"]

    for word in positive_words:
        analysis["emotion_score"] += speech.count(word)

    for word in negative_words:
        analysis["emotion_score"] -= speech.count(word)

    return analysis


def format_player_list_str(players: Sequence[str]) -> str:
    """格式化玩家姓名列表"""
    if not players:
        return "无人"
    return "、".join(players)


def calculate_suspicion_score(player_name: str, game_history: List[Dict]) -> float:
    """计算玩家可疑度分数"""
    score = 0.0

    for event in game_history:
        if event.get("type") == "vote" and event.get("target") == player_name:
            score += 0.3
        elif event.get("type") == "accusation" and event.get("target") == player_name:
            score += 0.2
        elif event.get("type") == "defense" and event.get("player") == player_name:
            score -= 0.1

    return min(max(score, 0.0), 1.0)


async def handle_interrupt(*args: Any, **kwargs: Any) -> Msg:
    """处理游戏中断"""
    return Msg(name="系统", content="游戏被中断", role="system")
