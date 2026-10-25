"""
Unit tests for TrafficLightDevice state machine.
"""
import time
import unittest
from atcs.models.traffic_light_device import (
    TrafficLightDevice, Colour, State, TimerConfig
)


class TestTrafficLightDevice(unittest.TestCase):

    def setUp(self):
        self.device = TrafficLightDevice("test-001")
        self.events = []
        self.device.on_state_change(self._record_state)
        self.device.on_colour_change(self._record_colour)

    def _record_state(self, state):
        self.events.append(("state", state))

    def _record_colour(self, colour):
        self.events.append(("colour", colour))

    def test_initial_state(self):
        self.assertEqual(self.device.get_state(), State.IDLE)
        self.assertEqual(self.device.get_colour(), Colour.RED)

    def test_default_timers(self):
        timers = self.device.get_timers()
        self.assertEqual(timers.green, 50)
        self.assertEqual(timers.orange, 5)
        self.assertEqual(timers.red, 240)

    def test_will_change_timer_green(self):
        self.device.will_change_timer("GREEN", 30)
        self.assertEqual(self.device.get_timers().green, 30)

    def test_will_change_timer_orange(self):
        self.device.will_change_timer("ORANGE", 10)
        self.assertEqual(self.device.get_timers().orange, 10)

    def test_will_change_timer_red(self):
        self.device.will_change_timer("RED", 120)
        self.assertEqual(self.device.get_timers().red, 120)

    def test_will_change_state(self):
        self.device.will_change_state("ACTIVE")
        self.assertEqual(self.device.get_state(), State.ACTIVE)
        self.assertIn(("state", State.ACTIVE), self.events)

    def test_will_change_colour(self):
        self.device.will_change_colour("GREEN")
        self.assertEqual(self.device.get_colour(), Colour.GREEN)
        self.assertIn(("colour", Colour.GREEN), self.events)

    def test_has_change_state_event(self):
        event = self.device.has_change_state(State.ACTIVE)
        self.assertEqual(event["type"], "hasChangeState")
        self.assertEqual(event["device_id"], "test-001")
        self.assertEqual(event["state"], "ACTIVE")
        self.assertIn("timestamp", event)

    def test_has_changed_colour_event(self):
        event = self.device.has_changed_colour(Colour.GREEN)
        self.assertEqual(event["type"], "hasChangedColour")
        self.assertEqual(event["device_id"], "test-001")
        self.assertEqual(event["colour"], "GREEN")
        self.assertIn("timestamp", event)

    def test_to_dict(self):
        d = self.device.to_dict()
        self.assertEqual(d["id"], "test-001")
        self.assertEqual(d["state"], "IDLE")
        self.assertEqual(d["colour"], "RED")
        self.assertEqual(d["greenTimer"], 50)
        self.assertEqual(d["orangeTimer"], 5)
        self.assertEqual(d["redTimer"], 240)
        self.assertIn("updated_at", d)

    def test_custom_timer_config(self):
        device = TrafficLightDevice("test-002", TimerConfig(green=10, orange=2, red=30))
        timers = device.get_timers()
        self.assertEqual(timers.green, 10)
        self.assertEqual(timers.orange, 2)
        self.assertEqual(timers.red, 30)

    def test_start_stop(self):
        self.device.start()
        time.sleep(0.1)
        self.assertTrue(self.device._running)
        self.device.stop()
        self.assertFalse(self.device._running)


if __name__ == "__main__":
    unittest.main()