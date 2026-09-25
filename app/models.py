"""API 请求 / 响应模型（Pydantic v2）。"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Segment(BaseModel):
    """一段馈线：父节点 -> 子节点，含电阻与额定电流。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="线段唯一标识")
    parent: str = Field(min_length=1, description="父节点名")
    child: str = Field(min_length=1, description="子节点名")
    resistance: float = Field(ge=0, description="线段电阻（欧姆），不允许为负")
    rated_current: float = Field(ge=0, description="额定电流（安培），不允许为负")


class Load(BaseModel):
    """节点恒定负载电流，可选节点级最低允许电压覆盖。"""

    model_config = ConfigDict(extra="forbid")

    node: str = Field(min_length=1, description="节点名")
    current: float = Field(ge=0, description="恒定负载电流（安培），不允许为负")
    min_voltage: Optional[float] = Field(
        default=None, description="该节点最低允许电压（伏），缺省用全局值"
    )


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_voltage: float = Field(gt=0, description="电源电压（伏），必须为正")
    min_voltage: float = Field(description="全局最低允许电压（伏）")
    segments: List[Segment] = Field(default_factory=list)
    loads: List[Load] = Field(default_factory=list)


class SegmentResult(BaseModel):
    id: str
    parent: str
    child: str
    current: float = Field(description="该段承载的全部下游电流（安培）")
    rated_current: float
    voltage_drop: float = Field(description="该段压降（伏）")
    over_rated: bool = Field(description="是否超过额定电流")


class NodeResult(BaseModel):
    node: str
    voltage: float = Field(description="节点电压（伏）")
    min_voltage: float = Field(description="该节点采用的最低允许电压（伏）")
    under_voltage: bool = Field(description="是否欠压")


class Violations(BaseModel):
    over_rated_segments: List[SegmentResult]
    under_voltage_nodes: List[NodeResult]


class EvaluateResponse(BaseModel):
    ok: bool = Field(description="无超额定且无欠压时为 true")
    source_voltage: float
    min_voltage: float
    segments: List[SegmentResult]
    nodes: List[NodeResult]
    violations: Violations
