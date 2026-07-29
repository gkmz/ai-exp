# -*- coding: utf-8 -*-
"""三国狼人杀游戏的结构化输出模型"""

from typing import Sequence

from agentscope.agent import ReActAgent
from pydantic import BaseModel, Field, field_validator


class DiscussionModel(BaseModel):
    """中文版讨论输出格式"""

    reach_agreement: bool = Field(
        description="是否已达成一致意见",
    )
    confidence_level: int = Field(description="对当前推理的信心程度(1-10)", ge=1, le=10)
    key_evidence: str | None = Field(description="支持你观点的关键证据", default=None)


def get_vote_model_cn(agents: list[ReActAgent]) -> type[BaseModel]:
    """获取中文版投票模型"""

    allowed_names = {agent.name for agent in agents}
    allowed_names_txt = ",".join(allowed_names)

    class VoteModelCN(BaseModel):
        """中文版投票输出格式"""

        vote: str = Field(
            description=f"你要投票淘汰的玩家姓名, 只能从 {allowed_names_txt} 选择一个",
        )
        reason: str = Field(
            description="投票理由，简要说明为什么选择此人",
        )
        suspicion_level: int = Field(
            description="对被投票者的怀疑程度(1-10)", ge=1, le=10
        )

        # 使用 pydantic校验器校验 vote的玩家是否存在
        @field_validator("vote")
        @classmethod
        def validate_vote(cls, value: str) -> str:
            if value not in allowed_names:
                raise ValueError(f"玩家不存在：{value}")
            return value

    return VoteModelCN


class WitchActionModel(BaseModel):
    """中文版女巫行动模型"""

    use_antidote: bool = Field(description="是否使用解药救人", default=False)
    use_poison: bool = Field(description="是否使用毒药杀人", default=False)
    target_name: str | None = Field(
        description="目标玩家姓名（救人或毒杀的对象）", default=None
    )
    action_reason: str | None = Field(description="行动理由", default=None)


def get_seer_model(agents: Sequence[ReActAgent]) -> type[BaseModel]:
    """获取预言家模型"""

    check_names = {agent.name for agent in agents}

    class SeerModel(BaseModel):
        """预言家查验格式"""

        target: str = Field(
            description="要查验的玩家姓名",
        )
        check_reason: str = Field(
            description="查验此人的原因",
        )
        priority_level: int = Field(description="查验优先级(1-10)", ge=1, le=10)

        @field_validator("target")
        @classmethod
        def validate_target(cls, value: str) -> str:
            if value not in check_names:
                raise ValueError(f"玩家 {value} 不存在")
            return value

    return SeerModel


def get_hunter_model_cn(agents: list[ReActAgent]) -> type[BaseModel]:
    """获取中文版猎人模型"""

    shoot_names = {agent.name for agent in agents}

    class HunterModelCN(BaseModel):
        """中文版猎人开枪格式"""

        shoot: bool = Field(
            description="是否使用开枪技能",
        )
        target: str | None = Field(description="开枪目标玩家姓名", default=None)
        shoot_reason: str | None = Field(description="开枪理由", default=None)

        @field_validator("shoot")
        @classmethod
        def validate_shoot_name(cls, value: str) -> str:
            if value not in shoot_names:
                raise ValueError(f"玩家 {value} 不存在")
            return value

    return HunterModelCN


class WerewolfKillModel(BaseModel):
    """中文版狼人击杀模型"""

    target: str = Field(
        description="要击杀的玩家姓名",
    )
    kill_strategy: str = Field(
        description="击杀策略说明",
    )
    team_coordination: str | None = Field(
        description="与狼队友的配合计划", default=None
    )


class GameAnalysisModelCN(BaseModel):
    """中文版游戏分析模型"""

    suspected_werewolves: list[str] = Field(
        description="怀疑的狼人名单", default_factory=list
    )
    trusted_players: list[str] = Field(
        description="信任的玩家名单", default_factory=list
    )
    key_clues: list[str] = Field(description="关键线索列表", default_factory=list)
    next_strategy: str = Field(
        description="下一步策略",
    )
