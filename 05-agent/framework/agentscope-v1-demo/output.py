# -*- coding: utf-8 -*-
"""三国狼人杀游戏的结构化输出模型。"""

from typing import Self, Sequence

from agentscope.agent import ReActAgent
from pydantic import BaseModel, Field, field_validator, model_validator


def _player_names(agents: Sequence[ReActAgent]) -> set[str]:
    """提取 Agent 列表中的玩家姓名。"""
    return {agent.name for agent in agents}


class DiscussionModel(BaseModel):
    """讨论阶段的结构化输出。"""

    reach_agreement: bool = Field(description="是否已达成一致意见")
    confidence_level: int = Field(description="对当前推理的信心程度(1-10)", ge=1, le=10)
    key_evidence: str | None = Field(description="支持观点的关键证据", default=None)


def _werewolf_target_names(
    agents: Sequence[ReActAgent],
    werewolf_names: set[str],
) -> set[str]:
    """返回当前存活且不属于狼人阵营的玩家姓名。"""
    return _player_names(agents) - werewolf_names


def get_werewolf_discussion_model(
    agents: Sequence[ReActAgent],
    werewolf_names: set[str],
) -> type[BaseModel]:
    """生成只允许狼人提议击杀存活非狼人玩家的讨论模型。"""
    target_names = _werewolf_target_names(agents, werewolf_names)
    target_names_text = ",".join(sorted(target_names)) or "无可用目标"

    class WerewolfDiscussionModel(DiscussionModel):
        """狼人阵营夜间讨论输出。"""

        proposed_target: str = Field(
            description=f"建议的击杀目标，只能从 {target_names_text} 中选择"
        )

        @field_validator("proposed_target")
        @classmethod
        def validate_proposed_target(cls, value: str) -> str:
            """校验讨论目标必须是存活的非狼人玩家。"""
            if value not in target_names:
                raise ValueError(f"不可提议击杀玩家：{value}")
            return value

    return WerewolfDiscussionModel


def get_vote_model_cn(
    agents: Sequence[ReActAgent],
    voter_name: str,
) -> type[BaseModel]:
    """生成排除投票者本人的白天投票模型。"""
    allowed_names = _player_names(agents) - {voter_name}
    allowed_names_text = ",".join(sorted(allowed_names)) or "无可用目标"

    class VoteModelCN(BaseModel):
        """白天放逐投票输出。"""

        vote: str = Field(
            description=f"要投票淘汰的玩家，只能从 {allowed_names_text} 中选择"
        )
        reason: str = Field(description="投票理由")
        suspicion_level: int = Field(description="对目标的怀疑程度(1-10)", ge=1, le=10)

        @field_validator("vote")
        @classmethod
        def validate_vote(cls, value: str) -> str:
            """校验投票目标必须合法且不能是自己。"""
            if value not in allowed_names:
                raise ValueError(f"不可投票给玩家：{value}")
            return value

    return VoteModelCN


def get_witch_action_model(
    agents: Sequence[ReActAgent],
    witch_name: str,
    can_use_antidote: bool,
    can_use_poison: bool,
) -> type[BaseModel]:
    """根据存活玩家和药品状态生成女巫行动模型。"""
    poison_names = _player_names(agents) - {witch_name}
    poison_names_text = ",".join(sorted(poison_names)) or "无可用目标"

    class WitchActionModel(BaseModel):
        """女巫行动输出。"""

        use_antidote: bool = Field(
            description="是否使用解药救活当晚被狼人击杀的玩家",
            default=False,
        )
        use_poison: bool = Field(description="是否使用毒药", default=False)
        poison_target: str | None = Field(
            description=f"毒药目标，只能从 {poison_names_text} 中选择",
            default=None,
        )
        action_reason: str | None = Field(description="行动理由", default=None)

        @field_validator("poison_target")
        @classmethod
        def validate_poison_target(cls, value: str | None) -> str | None:
            """校验毒药目标必须存活且不能是女巫自己。"""
            if value is None:
                return value
            if value == witch_name:
                raise ValueError("女巫不能对自己使用毒药")
            if value not in poison_names:
                raise ValueError(f"毒药目标不存在或已经死亡：{value}")
            return value

        @model_validator(mode="after")
        def validate_action(self) -> Self:
            """校验一晚一瓶药以及药品和目标之间的关系。"""
            if self.use_antidote and self.use_poison:
                raise ValueError("女巫一晚最多只能使用一瓶药")
            if self.use_antidote and not can_use_antidote:
                raise ValueError("当前无法使用解药")
            if self.use_poison and not can_use_poison:
                raise ValueError("毒药已经使用或当前不可用")
            if self.use_poison and self.poison_target is None:
                raise ValueError("使用毒药时必须指定毒药目标")
            if not self.use_poison and self.poison_target is not None:
                raise ValueError("未使用毒药时不能指定毒药目标")
            return self

    return WitchActionModel


def get_seer_model(
    agents: Sequence[ReActAgent],
    seer_name: str,
) -> type[BaseModel]:
    """生成排除预言家本人的查验模型。"""
    check_names = _player_names(agents) - {seer_name}
    check_names_text = ",".join(sorted(check_names)) or "无可用目标"

    class SeerModel(BaseModel):
        """预言家查验输出。"""

        target: str = Field(
            description=f"要查验的玩家，只能从 {check_names_text} 中选择"
        )
        check_reason: str = Field(description="查验此人的原因")
        priority_level: int = Field(description="查验优先级(1-10)", ge=1, le=10)

        @field_validator("target")
        @classmethod
        def validate_target(cls, value: str) -> str:
            """校验查验目标必须合法且不能是自己。"""
            if value not in check_names:
                raise ValueError(f"不可查验玩家：{value}")
            return value

    return SeerModel


def get_guardian_model(
    agents: Sequence[ReActAgent],
    guardian_name: str,
    last_guarded_player: str | None,
) -> type[BaseModel]:
    """生成允许自守但禁止连续守同一人的守护者模型。"""
    guard_names = _player_names(agents)
    if last_guarded_player is not None:
        guard_names.discard(last_guarded_player)
    guard_names_text = ",".join(sorted(guard_names)) or "无可用目标"

    class GuardianModel(BaseModel):
        """守护者行动输出。"""

        target: str = Field(
            description=f"今晚守护的玩家，只能从 {guard_names_text} 中选择"
        )
        guard_reason: str = Field(description="选择该守护目标的原因")

        @field_validator("target")
        @classmethod
        def validate_target(cls, value: str) -> str:
            """校验守护目标存活且未连续守护。"""
            if value not in guard_names:
                if value == last_guarded_player:
                    raise ValueError("不能连续两晚守护同一名玩家")
                raise ValueError(f"不可守护玩家：{value}")
            return value

    return GuardianModel


def get_hunter_model_cn(
    agents: Sequence[ReActAgent], hunter_name: str
) -> type[BaseModel]:
    """根据当前存活玩家生成猎人遗言和开枪模型。"""
    shoot_names = _player_names(agents) - {hunter_name}
    shoot_names_text = ",".join(sorted(shoot_names)) or "无可用目标"

    class HunterModelCN(BaseModel):
        """猎人遗言和开枪输出。"""

        last_words: str = Field(description="猎人死亡前的最后遗言", min_length=1)
        shoot: bool = Field(description="是否使用开枪技能")
        target: str | None = Field(
            description=f"开枪目标，只能从 {shoot_names_text} 中选择",
            default=None,
        )
        shoot_reason: str | None = Field(description="开枪理由", default=None)

        @field_validator("target")
        @classmethod
        def validate_shoot_name(cls, value: str | None) -> str | None:
            """校验开枪目标必须是除猎人外的存活玩家。"""
            if value is None:
                return value
            if value not in shoot_names:
                raise ValueError(f"不可开枪带走玩家：{value}")
            return value

        @model_validator(mode="after")
        def validate_action(self) -> Self:
            """校验开枪选择、目标和理由必须保持一致。"""
            if not self.last_words.strip():
                raise ValueError("猎人必须发表最后遗言")
            if self.shoot and self.target is None:
                raise ValueError("猎人开枪时必须指定目标")
            if self.shoot and not (self.shoot_reason or "").strip():
                raise ValueError("猎人开枪时必须说明理由")
            if not self.shoot and self.target is not None:
                raise ValueError("猎人放弃开枪时不能指定目标")
            return self

    return HunterModelCN


def get_werewolf_kill_model(
    agents: Sequence[ReActAgent],
    werewolf_names: set[str],
) -> type[BaseModel]:
    """生成只允许选择存活非狼人玩家的击杀模型。"""
    target_names = _werewolf_target_names(agents, werewolf_names)
    target_names_text = ",".join(sorted(target_names)) or "无可用目标"

    class WerewolfKillModel(BaseModel):
        """狼人击杀输出。"""

        target: str = Field(
            description=f"今晚击杀目标，只能从 {target_names_text} 中选择"
        )
        kill_strategy: str = Field(description="击杀策略说明")
        team_coordination: str | None = Field(
            description="与狼队友的配合计划", default=None
        )

        @field_validator("target")
        @classmethod
        def validate_target(cls, value: str) -> str:
            """校验击杀目标必须是存活的非狼人玩家。"""
            if value not in target_names:
                raise ValueError(f"不可击杀玩家：{value}")
            return value

    return WerewolfKillModel
