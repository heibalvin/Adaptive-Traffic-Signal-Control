import json
import threading
import time
from flask import Flask, request, jsonify
from kafka_utils.producer import KafkaProducerClient
from kafka_utils.consumer import KafkaConsumerClient
from kafka_utils.config import TOPIC_DEVICE_OUTBOUND, TOPIC_GROUP_INBOUND
from models.traffic_light import TrafficLightGroupModel, TrafficLightDeviceModel, TrafficLightState, TrafficLightColour
from messages.trafficLight.inbound import RegisterACK, UnregisterACK, WillChangeTimer, WillChangeColour, WillChangeState

app = Flask(__name__)
group = TrafficLightGroupModel()
producer = KafkaProducerClient()
consumer = KafkaConsumerClient([TOPIC_DEVICE_OUTBOUND], group_id="traffic_group")


def handle_device_messages():
    while True:
        try:
            messages = consumer.poll_messages(timeout_ms=1000)
            for msg in messages:
                msg_type = msg.get('message_type')
                
                if msg_type == 'registerREQ':
                    device_id = msg['device_id']
                    # Check if device already exists
                    existing = next((d for d in group.devices if d.device_id == device_id), None)
                    if not existing:
                        device = TrafficLightDeviceModel(device_id=device_id)
                        group.devices.append(device)
                        print(f"[GROUP] Device {device_id} registered")
                    else:
                        print(f"[GROUP] Device {device_id} re-registered")
                    
                    ack = RegisterACK(device_id=device_id, success=True).model_dump()
                    producer.send_message(TOPIC_GROUP_INBOUND, ack)
                
                elif msg_type == 'unregisterREQ':
                    device_id = msg['device_id']
                    group.devices = [d for d in group.devices if d.device_id != device_id]
                    print(f"[GROUP] Device {device_id} unregistered")
                    ack = UnregisterACK(device_id=device_id, success=True).model_dump()
                    producer.send_message(TOPIC_GROUP_INBOUND, ack)
                
                elif msg_type == 'didChangeTimer':
                    device_id = msg['device_id']
                    timer = msg['timer']
                    for d in group.devices:
                        if d.device_id == device_id:
                            d.timer = timer
                            break
                    print(f"[GROUP] {device_id} timer changed to {timer}")
                
                elif msg_type == 'didChangeColour':
                    device_id = msg['device_id']
                    colour = msg['colour']
                    for d in group.devices:
                        if d.device_id == device_id:
                            d.colour = colour
                            break
                    print(f"[GROUP] {device_id} colour changed to {colour}")
                
                elif msg_type == 'didChangeState':
                    device_id = msg['device_id']
                    state = msg['state']
                    for d in group.devices:
                        if d.device_id == device_id:
                            d.state = state
                            break
                    print(f"[GROUP] {device_id} state changed to {state}")
        except Exception as e:
            print(f"[GROUP] Error: {e}")
            time.sleep(1)


@app.route('/devices', methods=['GET'])
def get_devices():
    return jsonify([d.model_dump() for d in group.devices])


@app.route('/devices/<device_id>', methods=['GET'])
def get_device(device_id):
    device = next((d for d in group.devices if d.device_id == device_id), None)
    if not device:
        return jsonify({'error': 'Device not found'}), 404
    return jsonify(device.model_dump())


@app.route('/devices/<device_id>/command', methods=['POST'])
def send_command(device_id):
    data = request.get_json()
    command = data.get('command')
    
    if command == 'willChangeTimer':
        timer = data.get('timer')
        msg = WillChangeTimer(device_id=device_id, timer=timer).model_dump()
        producer.send_message(TOPIC_GROUP_INBOUND, msg)
        return jsonify({'status': 'sent', 'command': command})
    
    elif command == 'willChangeColour':
        colour = data.get('colour')
        msg = WillChangeColour(device_id=device_id, colour=colour).model_dump()
        producer.send_message(TOPIC_GROUP_INBOUND, msg)
        return jsonify({'status': 'sent', 'command': command})
    
    elif command == 'willChangeState':
        state = data.get('state')
        msg = WillChangeState(device_id=device_id, state=state).model_dump()
        producer.send_message(TOPIC_GROUP_INBOUND, msg)
        return jsonify({'status': 'sent', 'command': command})
    
    return jsonify({'error': 'Invalid command'}), 400


if __name__ == '__main__':
    t = threading.Thread(target=handle_device_messages, daemon=True)
    t.start()
    print("[GROUP] Traffic Light Group starting on port 9000...")
    app.run(host='0.0.0.0', port=9000, debug=False)
