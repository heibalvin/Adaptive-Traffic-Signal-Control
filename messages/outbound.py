from pydantic import BaseModel
from typing import Optional
from models.traffic_light import TrafficLightState, TrafficLightColour


class RegisterREQ(BaseModel):
    message_type: str = "registerREQ"
    device_id: str


class UnregisterREQ(BaseModel):
    message_type: str = "unregisterREQ"
    device_id: str


class DidChangeTimer(BaseModel):
    message_type: str = "didChangeTimer"
    device_id: str
    timer: int


class DidChangeColour(BaseModel):
    message_type: str = "didChangeColour"
    device_id: str
    colour: TrafficLightColour


class DidChangeState(BaseModel):
    message_type: str = "didChangeState"
    device_id: str
    state: TrafficLightState
