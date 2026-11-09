# Adaptive-Traffic-Signal-Control

Adaptive Traffic Signal Control (ATCS) — district and crossing slice.

## Components

- **MQTT**: `eclipse-mosquitto:2.1.2-alpine` (`mqtt/config/mosquitto.conf`).
- **District manager**: `managers/district/district_manager.py` (FastAPI, `:8000`). REST CRUD + activate/deactivate; initiates manager→device MQTT commands; logs MQTT events.
- **District device**: `devices/district/district_device.py`. Manager-driven (no auto-register), state `IDLE|READY|ACTIVE`.
- **Crossing manager**: `managers/crossing/crossing_manager.py` (FastAPI, `:8001`). REST CRUD + activate/deactivate; initiates manager→device MQTT commands; logs MQTT events.
- **Crossing device**: `devices/crossing/crossing_device.py`. Manager-driven, has `crossing_id`, `district_id`, `light_ids`, state `IDLE|READY|ACTIVE`.
- **Protocol**: `common/messages.py`, `common/mqtt_topics.py`.

## MQTT protocol (manager-initiated)

- District: manager `district/<name>/command` → `DISTRICT_REGISTER_REQ/UPDATE_REQ/ACTIVATE_REQ/DEACTIVATE_REQ/UNREGISTER_REQ`; device `district/events` → `*_ACK/*_NAK/STATE_ACK`.
- Crossing: manager `crossing/<name>/command` → `CROSSING_REGISTER_REQ/UPDATE_REQ/ACTIVATE_REQ/DEACTIVATE_REQ/UNREGISTER_REQ`; device `crossing/events` → `*_ACK/*_NAK/STATE_ACK`.
- Register ACK makes device `IDLE` (registered); update ACK with light/crossing data makes it `READY`; activate requires `READY` → `ACTIVE`; deactivate → `READY`.

## District REST API (`:8000`)

- `GET/POST /districts`, `GET/PUT/DELETE /districts/{district_id}`
- `POST /districts/{district_id}/activate` / `deactivate`
- Payload: `{district_id,name,state,crossing_ids,registered,updated}`

## Crossing REST API (`:8001`)

- `GET /crossings[?district_id=...]` — list crossings (optionally by district).
- `POST /crossings` `{name,district_id?,light_ids?[]}` — register/create (assigns `crossing_id`, sends `CROSSING_REGISTER_REQ`).
- `GET /crossings/{crossing_id}` — get one crossing.
- `PUT /crossings/{crossing_id}` `{light_ids,district_id?}` — update lights (sends `CROSSING_UPDATE_REQ`).
- `DELETE /crossings/{crossing_id}` — unregister/delete.
- `POST /crossings/{crossing_id}/activate` / `deactivate` (activate requires `READY`).
- Payload: `{crossing_id,name,district_id,state,light_ids,registered,updated}`

## Run

Deploy order: `mqtt` → managers → devices.

```bash
docker compose up --build
```

Compose starts 5 district devices and 5 `downtown-dubai` crossing devices. Downtown Dubai crossings: `downtown-dubai-burj-khalifa-blvd`, `downtown-dubai-financial-centre-rd`, `downtown-dubai-mohammed-bin-rashid-blvd`, `downtown-dubai-al-safa-st`, `downtown-dubai-sheikh-zayed-rd-ramp`.

## Test

```bash
docker compose up --build

# District
curl -s -X POST http://localhost:8000/districts -H 'Content-Type: application/json' \
  -d '{"name":"downtown-dubai","crossing_ids":["downtown-dubai-burj-khalifa-blvd","downtown-dubai-financial-centre-rd","downtown-dubai-mohammed-bin-rashid-blvd","downtown-dubai-al-safa-st","downtown-dubai-sheikh-zayed-rd-ramp"]}'
curl -s http://localhost:8000/districts

# Crossings (register each device by name; manager assigns crossing_id)
curl -s -X POST http://localhost:8001/crossings -H 'Content-Type: application/json' -d '{"name":"downtown-dubai-burj-khalifa-blvd","district_id":"<district_id>","light_ids":["l1","l2"]}'
curl -s -X POST http://localhost:8001/crossings -H 'Content-Type: application/json' -d '{"name":"downtown-dubai-financial-centre-rd","district_id":"<district_id>","light_ids":["l3","l4"]}'
curl -s -X POST http://localhost:8001/crossings -H 'Content-Type: application/json' -d '{"name":"downtown-dubai-mohammed-bin-rashid-blvd","district_id":"<district_id>","light_ids":["l5","l6"]}'
curl -s -X POST http://localhost:8001/crossings -H 'Content-Type: application/json' -d '{"name":"downtown-dubai-al-safa-st","district_id":"<district_id>","light_ids":["l7","l8"]}'
curl -s -X POST http://localhost:8001/crossings -H 'Content-Type: application/json' -d '{"name":"downtown-dubai-sheikh-zayed-rd-ramp","district_id":"<district_id>","light_ids":["l9","l10"]}'

curl -s http://localhost:8001/crossings
curl -s http://localhost:8001/crossings/<crossing_id>
curl -s -X PUT http://localhost:8001/crossings/<crossing_id> -H 'Content-Type: application/json' -d '{"light_ids":["l1","l2","l3"]}'
curl -s -X POST http://localhost:8001/crossings/<crossing_id>/activate   # requires READY
curl -s -X POST http://localhost:8001/crossings/<crossing_id>/deactivate
curl -s -X DELETE http://localhost:8001/crossings/<crossing_id>
```

Expected: MQTT events logged to console; crossings transition `IDLE` → `READY` → `ACTIVE` → `READY`.
