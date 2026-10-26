import os
import time
import threading
from kafka_utils.producer import KafkaProducerClient
from kafka_utils.consumer import KafkaConsumerClient
from kafka_utils.config import TOPIC_GROUP_INBOUND, TOPIC_DEVICE_OUTBOUND
from models.traffic_light import TrafficLightDeviceModel, TrafficLightState, TrafficLightColour
from messages.trafficLight.outbound import RegisterREQ, UnregisterREQ, DidChangeTimer, DidChangeColour, DidChangeState

DEVICE_ID = os.getenv('DEVICE_ID', f'TL-{os.getpid()}')

device = TrafficLightDeviceModel(device_id=DEVICE_ID)
producer = KafkaProducerClient()
consumer = KafkaConsumerClient([TOPIC_GROUP_INBOUND], group_id=f"traffic_device_{DEVICE_ID}")


def send_message(msg):
    producer.send_message(TOPIC_DEVICE_OUTBOUND, msg.model_dump() if hasattr(msg, 'model_dump') else msg)


def register():
    print(f"[{DEVICE_ID}] Registering with group...")
    reg = RegisterREQ(device_id=DEVICE_ID)
    send_message(reg)


def unregister():
    print(f"[{DEVICE_ID}] Unregistering from group...")
    unreg = UnregisterREQ(device_id=DEVICE_ID)
    send_message(unreg)


def handle_group_messages():
    while True:
        try:
            messages = consumer.poll_messages(timeout_ms=1000)
            for msg in messages:
                msg_type = msg.get('message_type')
                target = msg.get('device_id')
                
                if target != DEVICE_ID and msg_type not in ['registerACK']:
                    continue
                
                if msg_type == 'registerACK':
                    if msg.get('success'):
                        print(f"[{DEVICE_ID}] Registration acknowledged")
                    continue
                
                if msg_type == 'unregisterACK':
                    if msg.get('success'):
                        print(f"[{DEVICE_ID}] Unregistration acknowledged")
                    continue
                
                if msg_type == 'willChangeTimer':
                    new_timer = msg['timer']
                    print(f"[{DEVICE_ID}] Will change timer to {new_timer}")
                    device.timer = new_timer
                    did_change = DidChangeTimer(device_id=DEVICE_ID, timer=new_timer)
                    send_message(did_change)
                    print(f"[{DEVICE_ID}] Timer changed to {new_timer}")
                
                elif msg_type == 'willChangeColour':
                    new_colour = msg['colour']
                    print(f"[{DEVICE_ID}] Will change colour to {new_colour}")
                    device.colour = new_colour
                    did_change = DidChangeColour(device_id=DEVICE_ID, colour=new_colour)
                    send_message(did_change)
                    print(f"[{DEVICE_ID}] Colour changed to {new_colour}")
                
                elif msg_type == 'willChangeState':
                    new_state = msg['state']
                    print(f"[{DEVICE_ID}] Will change state to {new_state}")
                    device.state = new_state
                    did_change = DidChangeState(device_id=DEVICE_ID, state=new_state)
                    send_message(did_change)
                    print(f"[{DEVICE_ID}] State changed to {new_state}")
        except Exception as e:
            print(f"[{DEVICE_ID}] Error: {e}")
            time.sleep(1)


def autonomous_control():
    """Autonomous traffic light cycle"""
    while True:
        try:
            if device.state == TrafficLightState.ACTIVE:
                # Simple cycle: RED -> GREEN -> ORANGE -> RED
                if device.colour == TrafficLightColour.RED:
                    print(f"[{DEVICE_ID}] Autonomous: RED, waiting {device.red_timer}s")
                    time.sleep(device.red_timer)
                    device.colour = TrafficLightColour.GREEN
                    did_change = DidChangeColour(device_id=DEVICE_ID, colour=device.colour)
                    send_message(did_change)
                    print(f"[{DEVICE_ID}] Autonomous: Changed to GREEN")
                
                elif device.colour == TrafficLightColour.GREEN:
                    print(f"[{DEVICE_ID}] Autonomous: GREEN, waiting {device.green_timer}s")
                    time.sleep(device.green_timer)
                    device.colour = TrafficLightColour.ORANGE
                    did_change = DidChangeColour(device_id=DEVICE_ID, colour=device.colour)
                    send_message(did_change)
                    print(f"[{DEVICE_ID}] Autonomous: Changed to ORANGE")
                
                elif device.colour == TrafficLightColour.ORANGE:
                    print(f"[{DEVICE_ID}] Autonomous: ORANGE, waiting {device.orange_timer}s")
                    time.sleep(device.orange_timer)
                    device.colour = TrafficLightColour.RED
                    did_change = DidChangeColour(device_id=DEVICE_ID, colour=device.colour)
                    send_message(did_change)
                    print(f"[{DEVICE_ID}] Autonomous: Changed to RED")
                else:
                    time.sleep(1)
            else:
                if device.state == TrafficLightState.IDLE:
                    device.colour = TrafficLightColour.RED
                elif device.state == TrafficLightState.INACTIVE:
                    device.colour = TrafficLightColour.BLINKING
                time.sleep(1)
        except Exception as e:
            print(f"[{DEVICE_ID}] Error in autonomous control: {e}")
            time.sleep(1)


if __name__ == '__main__':
    print(f"[{DEVICE_ID}] Traffic Light Device starting...")
    print(f"[{DEVICE_ID}] State: {device.state}, Colour: {device.colour}")
    
    # Start threads
    t1 = threading.Thread(target=handle_group_messages, daemon=True)
    t1.start()
    
    t2 = threading.Thread(target=autonomous_control, daemon=True)
    t2.start()
    
    # Register
    time.sleep(2)
    register()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        unregister()
        time.sleep(1)
        print(f"[{DEVICE_ID}] Stopped")
