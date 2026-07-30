# -*- coding: utf-8 -*-
"""三国狼人杀游戏的结构化输出模型"""

from typing import Self, Sequence

from agentscope.agent import ReActAgent
from pydantic import BaseModel, Field, field_validator, model_validator


class DiscussionModel(BaseModel):
    """ ""讨论输出格式"""

    reach_agreement: bool = Field(
        description="是否已达成一致意见",
    )
    confidence_level: int = Field(description="对当前推理的信心程度(1-10)", ge=1, le=10)
    key_evidence: str | None = Field(description="支持你观点的关键证据", default=None)


def get_vote_model_cn(agents: list[ReActAgent]) -> type[BaseModel]:
    """获取""投票模型"""

    allowed_names = {agent.name for agent in agents}
    allowed_names_txt = ",".join(allowed_names)

    class VoteModelCN(BaseModel):
        """ ""投票输出格式"""

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


def get_witch_action_model(
    agents: Sequence[ReActAgent],
    witch_name: str,
    can_use_antidote: bool,
    can_use_poison: bool,
) -> type[BaseModel]:
    """根据存活玩家和药品状态生成女巫行动模型。"""

    poison_names = {agent.name for agent in agents if agent.name != witch_name}
    poison_names_txt = ",".join(sorted(poison_names)) or "无可用目标"

    class WitchActionModel(BaseModel):
        """ ""女巫行动模型。"""

        use_antidote: bool = Field(
            description="是否使用解药救活当晚被狼人击杀的玩家",
            default=False,
        )
        use_poison: bool = Field(description="是否使用毒药杀人", default=False)
        poison_target: str | None = Field(
            description=f"毒药目标，只能从 {poison_names_txt} 中选择",
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


def get_hunter_model_cn(
    agents: Sequence[ReActAgent], hunter_name: str
) -> type[BaseModel]:
    """根据当前存活玩家生成猎人遗言和开枪模型。"""

    shoot_names = {agent.name for agent in agents if agent.name != hunter_name}
    shoot_names_txt = ",".join(sorted(shoot_names)) or "无可用目标"

    class HunterModelCN(BaseModel):
        """猎人开枪格式"""

        last_words: str = Field(description="猎人死亡前的最后遗言", min_length=1)
        shoot: bool = Field(
            description="是否使用开枪技能",
        )
        target: str | None = Field(
            description=f"开枪目标，只能从 {shoot_names_txt} 中选择",
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
                raise ValueError(f"玩家 {value} 不存在")
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


class WerewolfKillModel(BaseModel):
    """ ""狼人击杀模型"""

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
    """ ""游戏分析模型"""

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
