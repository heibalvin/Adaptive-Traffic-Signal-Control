"""
ATCS Web Application - visual representation of traffic lights.

Uses Flask + Flask-SocketIO for real-time updates.
Monitors Kafka events and updates the UI live.
"""
import os
import json
import logging
import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

from atcs.services.kafka_comm import (
    KafkaConfig, KafkaSubscriber,
    TOPIC_EVENTS, TOPIC_COMMANDS, TOPIC_AGENT,
    bootstrap_servers_from_env
)
from atcs.services.postgres_store import PostgresConfig, PostgresStore

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "atcs-secret-key")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Global store
postgres = PostgresStore()
kafka_subscriber: KafkaSubscriber = None
kafka_thread = None
_running = False


def init_app():
    """Initialize the web app connections."""
    global postgres, kafka_subscriber, kafka_thread, _running

    # Connect Postgres
    try:
        postgres.connect()
        logger.info("Web app connected to Postgres")
    except Exception as e:
        logger.error(f"Postgres connection failed: {e}")

    # Connect Kafka subscriber for events
    try:
        kafka_config = KafkaConfig(bootstrap_servers_from_env())
        kafka_subscriber = KafkaSubscriber(kafka_config, group_id="atcs-webapp")
        kafka_subscriber.connect([TOPIC_EVENTS])
        logger.info("Web app connected to Kafka events topic")
    except Exception as e:
        logger.error(f"Kafka connection failed: {e}")

    # Start Kafka event monitor thread
    _running = True
    kafka_thread = threading.Thread(target=_kafka_monitor, daemon=True)
    kafka_thread.start()


def _kafka_monitor():
    """Continuously poll Kafka events and broadcast to web clients."""
    while _running:
        try:
            events = kafka_subscriber.poll(timeout_ms=1000)
            for event in events:
                # Persist to Postgres
                try:
                    postgres.save_event(event)
                except Exception:
                    pass
                # Broadcast to web clients
                socketio.emit("traffic_event", event)
        except Exception as e:
            logger.error(f"Kafka monitor error: {e}")
            import time as _t
            _t.sleep(1)


# ── Routes ────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/devices", methods=["GET"])
def api_list_devices():
    try:
        devices = postgres.get_all_devices()
        return jsonify(devices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/<device_id>", methods=["GET"])
def api_get_device(device_id):
    try:
        device = postgres.get_device(device_id)
        if not device:
            return jsonify({"error": "not found"}), 404
        return jsonify(device)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices", methods=["POST"])
def api_create_device():
    try:
        data = request.json
        device_id = data.get("id", f"tl-{os.urandom(4).hex()}")
        # Send command via Kafka
        from atcs.services.kafka_comm import KafkaPublisher
        publisher = KafkaPublisher(KafkaConfig(bootstrap_servers_from_env()))
        publisher.connect()
        publisher.publish(TOPIC_COMMANDS, {
            "type": "createDevice",
            "device_id": device_id,
            "greenTimer": data.get("greenTimer", 50),
            "orangeTimer": data.get("orangeTimer", 5),
            "redTimer": data.get("redTimer", 240),
        })
        publisher.close()
        return jsonify({"id": device_id, "status": "created"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/<device_id>", methods=["DELETE"])
def api_delete_device(device_id):
    try:
        from atcs.services.kafka_comm import KafkaPublisher
        publisher = KafkaPublisher(KafkaConfig(bootstrap_servers_from_env()))
        publisher.connect()
        publisher.publish(TOPIC_COMMANDS, {
            "type": "deleteDevice",
            "device_id": device_id,
        })
        publisher.close()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/devices/<device_id>/command", methods=["POST"])
def api_send_command(device_id):
    """Send a command to a specific device."""
    try:
        data = request.json
        from atcs.services.kafka_comm import KafkaPublisher
        publisher = KafkaPublisher(KafkaConfig(bootstrap_servers_from_env()))
        publisher.connect()
        cmd = {
            "device_id": device_id,
            "type": data.get("type"),
            **data
        }
        publisher.publish(TOPIC_COMMANDS, cmd)
        publisher.close()
        return jsonify({"status": "sent"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/events", methods=["GET"])
def api_get_events():
    try:
        device_id = request.args.get("device_id")
        limit = int(request.args.get("limit", 100))
        events = postgres.get_events(device_id=device_id, limit=limit)
        return jsonify(events)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── WebSocket events ──────────────────────────────────────────────
@socketio.on("connect")
def handle_connect():
    logger.info("Web client connected")
    emit("status", {"message": "connected"})


@socketio.on("subscribe")
def handle_subscribe(data):
    """Subscribe to events for a specific device."""
    device_id = data.get("device_id")
    logger.info(f"Client subscribed to device {device_id}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_app()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)