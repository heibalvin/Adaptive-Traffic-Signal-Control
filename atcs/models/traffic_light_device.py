"""
Traffic Light Device - data model and state machine.

A traffic light device manages its own state and colour autonomously.
States: IDLE, ACTIVE, INACTIVE
Sequence: RED -> GREEN -> ORANGE
"""
import time
import threading
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field
import uuid


class Colour(Enum):
    RED = "RED"
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    OFF = "OFF"


class State(Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass
class TimerConfig:
    green: int = 50
    orange: int = 5
    red: int = 240


@dataclass
class TrafficLightDataModel:
    """The data model that lives in activeDataModel and nextDataModel."""
    id: str
    greenTimer: int = 50
    orangeTimer: int = 5
    redTimer: int = 240
    state: State = State.IDLE
    colour: Colour = Colour.RED
    updated_at: float = field(default_factory=time.time)


class TrafficLightDevice:
    """
    Autonomous traffic light device.
    - Reads/writes events through Kafka topics.
    - Manages state transitions: IDLE -> ACTIVE (RED->GREEN->ORANGE) -> INACTIVE (ORANGE blinking)
    """
    def __init__(self, device_id: str, timer_config: Optional[TimerConfig] = None):
        self.id = device_id
        self.timers = timer_config or TimerConfig()
        self.data_model = TrafficLightDataModel(
            id=device_id,
            greenTimer=self.timers.green,
            orangeTimer=self.timers.orange,
            redTimer=self.timers.red,
        )
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._state_change_callbacks: list[Callable] = []
        self._colour_change_callbacks: list[Callable] = []

    # ── callback registration ──────────────────────────────────────
    def on_state_change(self, callback):
        self._state_change_callbacks.append(callback)

    def on_colour_change(self, callback):
        self._colour_change_callbacks.append(callback)

    # ── inbound event handlers ─────────────────────────────────────
    def will_change_timer(self, colour: str, timer: int):
        """Inbound: update timer for a colour."""
        colour = Colour[colour.upper()] if isinstance(colour, str) else colour
        with self._lock:
            if colour == Colour.GREEN:
                self.data_model.greenTimer = timer
            elif colour == Colour.ORANGE:
                self.data_model.orangeTimer = timer
            elif colour == Colour.RED:
                self.data_model.redTimer = timer
            self.data_model.updated_at = time.time()

    def will_change_state(self, state: str):
        """Inbound: request a state change."""
        state = State[state.upper()] if isinstance(state, str) else state
        with self._lock:
            old_state = self.data_model.state
            if old_state == state:
                return
            self.data_model.state = state
            self.data_model.updated_at = time.time()
            self._notify_state_change(state)

    def will_change_colour(self, colour: str):
        """Inbound: request a colour change."""
        colour = Colour[colour.upper()] if isinstance(colour, str) else colour
        with self._lock:
            old_colour = self.data_model.colour
            if old_colour == colour:
                return
            self.data_model.colour = colour
            self.data_model.updated_at = time.time()
            self._notify_colour_change(colour)

    # ── outbound events ────────────────────────────────────────────
    def has_change_state(self, state: State) -> dict:
        """Outbound: emit a state change event."""
        return {
            "type": "hasChangeState",
            "device_id": self.id,
            "state": state.value if isinstance(state, State) else state,
            "timestamp": time.time()
        }

    def has_changed_colour(self, colour: Colour) -> dict:
        """Outbound: emit a colour change event."""
        return {
            "type": "hasChangedColour",
            "device_id": self.id,
            "colour": colour.value if isinstance(colour, Colour) else colour,
            "timestamp": time.time()
        }

    def _notify_state_change(self, state: State):
        for cb in self._state_change_callbacks:
            try:
                cb(state)
            except Exception:
                pass

    def _notify_colour_change(self, colour: Colour):
        for cb in self._colour_change_callbacks:
            try:
                cb(colour)
            except Exception:
                pass

    # ── autonomous state machine ───────────────────────────────────
    def start(self):
        """Start the autonomous state machine loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run_loop(self):
        """Main state machine loop."""
        while self._running:
            with self._lock:
                state = self.data_model.state
                colour = self.data_model.colour

            if state == State.ACTIVE:
                self._run_active_cycle()
            elif state == State.INACTIVE:
                self._run_inactive_cycle()
            else:
                # IDLE - just wait
                time.sleep(1)

    def _run_active_cycle(self):
        """RED -> GREEN -> ORANGE sequence."""
        with self._lock:
            colour = self.data_model.colour

        if colour == Colour.RED:
            self.will_change_colour(Colour.GREEN.value)
            time.sleep(self.timers.red)
        elif colour == Colour.GREEN:
            self.will_change_colour(Colour.ORANGE.value)
            time.sleep(self.timers.green)
        elif colour == Colour.ORANGE:
            # After orange, go back to red
            self.will_change_colour(Colour.RED.value)
            time.sleep(self.timers.orange)

    def _run_inactive_cycle(self):
        """ORANGE blinking."""
        with self._lock:
            current = self.data_model.colour

        if current == Colour.ORANGE:
            self.will_change_colour(Colour.OFF.value)
        else:
            self.will_change_colour(Colour.ORANGE.value)
        time.sleep(1)  # blink every second

    # ── getters ────────────────────────────────────────────────────
    def get_state(self) -> State:
        with self._lock:
            return self.data_model.state

    def get_colour(self) -> Colour:
        with self._lock:
            return self.data_model.colour

    def get_timers(self) -> TimerConfig:
        with self._lock:
            return TimerConfig(
                green=self.data_model.greenTimer,
                orange=self.data_model.orangeTimer,
                red=self.data_model.redTimer
            )

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "id": self.data_model.id,
                "greenTimer": self.data_model.greenTimer,
                "orangeTimer": self.data_model.orangeTimer,
                "redTimer": self.data_model.redTimer,
                "state": self.data_model.state.value,
                "colour": self.data_model.colour.value,
                "updated_at": self.data_model.updated_at
            }