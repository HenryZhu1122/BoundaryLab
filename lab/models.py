from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Device(BaseModel):
    name: str = "BL-01 / 通用低功耗模型"
    gbw_hz: float = Field(default=800_000, ge=50_000, le=50_000_000)
    slew_v_us: float = Field(default=0.3, ge=0.02, le=50)
    swing_v: float = Field(default=4, ge=1, le=15)
    open_loop_gain: float = Field(default=100_000, ge=10_000, le=1_000_000)
    output_resistance_ohm: float = Field(default=30, ge=1, le=500)


class Circuit(BaseModel):
    kind: Literal["amplifier", "lowpass"] = "amplifier"
    gain: float = Field(default=10, ge=2, le=100)
    cutoff_hz: float = Field(default=20_000, ge=100, le=200_000)
    load_ohm: float = Field(default=10_000, ge=500, le=1_000_000)
    device: Device = Field(default_factory=Device)


class Contract(BaseModel):
    frequency_min_hz: float = Field(default=500, ge=50, le=500_000)
    frequency_max_hz: float = Field(default=200_000, ge=100, le=1_000_000)
    amplitude_min_v: float = Field(default=0.005, ge=0.001, le=1)
    amplitude_max_v: float = Field(default=0.8, ge=0.002, le=2)
    gain_error_limit: float = Field(default=0.05, ge=0.005, le=0.5)
    distortion_limit: float = Field(default=0.03, ge=0.002, le=0.3)

    @model_validator(mode="after")
    def ascending(self):
        if self.frequency_max_hz <= self.frequency_min_hz:
            raise ValueError("频率上限必须大于下限")
        if self.amplitude_max_v <= self.amplitude_min_v:
            raise ValueError("幅值上限必须大于下限")
        return self


class Experiment(BaseModel):
    frequency_hz: float = Field(ge=50, le=1_000_000)
    amplitude_v: float = Field(ge=0.001, le=2)
    purpose: str = Field(default="手动实验", max_length=300)


class InvestigationRequest(BaseModel):
    purpose: Literal["research", "benchmark"] = "research"
    circuit: Circuit = Field(default_factory=Circuit)
    contract: Contract = Field(default_factory=Contract)
    mode: Literal["deepseek", "local"] = "deepseek"
    budget: int = Field(default=10, ge=4, le=24)
    question: str = Field(default="找出电路的失效边界，区分失效机制，并提出有证据的改进建议。", max_length=1500)
    auto_repair: bool = True
    build_map: bool = True


class ExperimentRequest(BaseModel):
    circuit: Circuit = Field(default_factory=Circuit)
    contract: Contract = Field(default_factory=Contract)
    experiment: Experiment
