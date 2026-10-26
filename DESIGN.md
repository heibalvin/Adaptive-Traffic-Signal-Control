Adaptive Traffic Signal Control (ATCS) is an agentic AI system for intelligent, optimized, and self-healing traffic signal control based on LangGraph/LangChain.

Environment:
 * python 3.12.13 (using pyenv local 3.12.13)
 * virtual python environment venv (python -m venv .venv)
 * Cloud Data systems running in docker project aicd accessible through .env environemnt variables: apache/kafka:4.3.1. Do not need to deploy, are available.

Architecture:
  * devices (ex traffic light device) will run autonomously. And communicate to other devices, group or agent through Kafka topcis messages (producer). It will also be able to change state, variable, behaviours based on Kafka topics messages too (consumer).
  * group (ex: traffic light group) will be managing the flee of devices through registration / unregistration. Be able to keep track of all devices data models state (update Postgres database). And able to send messages on Kafka topics (producer) and also keep track of traffic light device messages (consumer). It shall have a REST API so that we could send specific messages to traffic lights or get states.
  * kafka broker that will serve as communication between all traffic light devices and the uniquer traffic light group.

Devices Components:
 * traffic light device: autonomously running from IDLE / ACTIVE / INACTIVE states (IDLE by default), and will move from RED / GREEN / ORANGE / BLINKING colour lights (red default), based on red / orange / green timers (240 sec, 5 sec, 50 sec default).

Group Components:
 * traffic light group: will keep a list of traffic light devices. Ability to register / deregister a traffic light. Set specific traffic light state, colour, timer changes. Captures all traffic light state, colour, timer changes.

 
PHASES I:
 1. define traffic light device data model (state, colour, timer).
 2. define traffic light group data model (list of traffic light device model)
 3. define traffic outbound kafka messages (registerREQ, unregisterREQ, didChangeTimer, didChangeColour, didChangeState).
 4. define traffic light inbound kafka messages (registerACK, unregisterACK, willChangeTimer, willChangeColour, willChangeState).
 5. provide traffic light group code; registration procedure, traffic light device event listening, rest api (port 9000) to send kafka messages.
 6. provide traffic light device code; registration procedure, traffic light group event listening, autonomous changes;
 7. document in README.md how to install and test traffic light group and traffic light devices.
 
 