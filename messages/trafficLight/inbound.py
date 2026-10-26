from pydantic import BaseModel
from typing import Optional
from models.traffic_light import TrafficLightState, TrafficLightColour


class RegisterACK(BaseModel):
    message_type: str = "registerACK"
    device_id: str
    success: bool


class UnregisterACK(BaseModel):
    message_type: str = "unregisterACK"
    device_id: str
    success: bool


class WillChangeTimer(BaseModel):
    message_type: str = "willChangeTimer"
    device_id: str
    timer: int


class WillChangeColour(BaseModel):
    message_type: str = "willChangeColour"
    device_id: str
    colour: TrafficLightColour


class WillChangeState(BaseModel):
    message_type: str = "willChangeState"
    device_id: str
    state: TrafficLightState
