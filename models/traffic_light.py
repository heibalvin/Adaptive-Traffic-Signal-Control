from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class TrafficLightState(str, Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TrafficLightColour(str, Enum):
    RED = "RED"
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    BLINKING = "BLINKING"


class TrafficLightDeviceModel(BaseModel):
    device_id: str
    state: TrafficLightState = TrafficLightState.IDLE
    colour: TrafficLightColour = TrafficLightColour.RED
    timer: int = 240  # seconds
    red_timer: int = 240
    orange_timer: int = 5
    green_timer: int = 50


class TrafficLightGroupModel(BaseModel):
    devices: List[TrafficLightDeviceModel] = Field(default_factory=list)
