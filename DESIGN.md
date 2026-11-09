# **Software Design & Delivery Document: Adaptive Traffic Controller System**

# **1\. System Description**

* **Executive Summary & Core Purpose:** Macro/mesoscopic urban traffic flow simulation and dynamic signal optimization platform split across four distinct application repositories/branches. Instead of modeling individual vehicle agents, the system simulates macroscopic traffic flow through generators, absorbers, road segments, and detectors grouped across intersections and districts.  
* **Modular Architecture & Repository Split:**  
  * **App 1: ATCS Topology Generation (feature/atcs-topology-generator / app-topology):** Extracts spatial networks via atcs\_extract.py to output spatial JSON and layout image maps. Includes atcs\_topology\_viewer (Viewer Layer), an interactive graphical UI rendering overlay canvas sprites for roads, lights, intersections, and districts over the background layout image map based on PostgreSQL state query updates.  
  * **App 2: ATCS Traffic Generation (feature/atcs-traffic-generator / app-traffic-gen):** Generates edge boundary stubs via atcs\_stubs.py, models dynamic 24-hour demand via atcs\_traffic\_generator.py to produce a 1,440-minute probability profile, provides a natural language Stub AI Agent for Controller REST commands, and runs a profile-driven time-series state execution engine.  
  * **App 3: ATCS Traffic Simulation (feature/atcs-traffic-simulation / app-simulator):** Executes minute-by-minute simulations via atcs\_simulator.py integrating Device MQTT state machines, Controller PostgreSQL state tables, live parameter control, and autonomous LangGraph AI Agent control loops based on spatial topology and live stub profiles.  
  * **App 4: ATCS Multi-Day Analytics & Optimization Dashboard (feature/atcs-analytics-dashboard / app-analytics):** Executes multi-day multi-month continuous simulation runs with daily stochastic seed modulation, compares dynamic LangGraph Agentic System signal optimizations against static baselines, and presents key performance metrics via an analytical dashboard.

---

# **2\. Domain & Entity Model**

* **Generator:** Source entity generating vehicle volume rates into the network.  
* **Absorber:** Sink entity removing traffic volume from the system.  
* **Road:** Edge connecting nodes, defining capacity, speed thresholds, and current flow volume.  
* **Light:** Traffic signal device executing local phase state machines (Green/Yellow/Red).  
* **Detector:** Sensor device measuring flow rates and queue densities.  
* **Intersection:** Physical node joining roads, managing light groups and detector feeds.  
* **District:** Hierarchical group of interconnected intersections for macro-level optimization.  
* **Urban Topology Extraction (atcs\_extract.py) \[App 1 / feature/atcs-topology-generator\]:** Takes district and country inputs to generate a spatial JSON topology file and produces a layout image map for visual rendering.  
* **Dynamic Traffic Pattern Profiling & Stub Creation (atcs\_stubs.py & atcs\_traffic\_generator.py) \[App 2 / feature/atcs-traffic-generator\]:** Automatically/manually creates edge boundary stubs (Generators/Absorbers), assigns 24-hour minute-by-minute (1,440-minute daily cycle) traffic probability profiles (0%-100%), and executes a time-series state controller engine driven by text-to-API stub agent commands.  
* **Core Simulation Execution Engine & Autonomous Agent Control (atcs\_simulator.py) \[App 3 / feature/atcs-traffic-simulation\]:** Ingests JSON topology, layout image, and daily traffic profiles to execute minute-by-minute macroscopic simulation, supporting real-time live parameter adjustments and autonomous LangGraph AI Agent control loops.

---

# **3\. Multi-Layer Architecture & Data Pipeline**

* **Device Layer:**  
  * Edge devices (Lights, Detectors, Generators, Absorbers) executing deterministic state machines.  
  * Sends real-time telemetry and state updates over MQTT to Controllers; subscribes to incoming control commands.  
  * Lightweight, bug-free execution decoupled from central view rendering.  
* **Controller Layer:**  
  * Receives MQTT messages from edge devices, processes updates, and orchestrates events.  
  * Persists device states, metric snapshots, and event logs into PostgreSQL state tables (maintaining fast O(1) current state updates).  
  * Exposes REST API endpoints for management, data queries, and Agent interactions.  
* **Viewer Layer (ATCS Topology Viewer):**  
  * Queries PostgreSQL state tables (or receives state updates) from the Controller Layer.  
  * Renders and updates graphical UI outputs using overlay canvas sprites for roads, lights, intersections, districts, and stubs positioned over the layout background image.  
* **Agent Layer:**  
  * Built using Python and LangGraph autonomous graph workflows.  
  * Interacts with Controller Layer via REST API.  
  * Queries system state and volume metrics as tools, and issues dynamic signal timing commands (adjusting light timing variables and phase states across districts).

---

# **4\. Tech Stack & Repository Structure**

* **Application & Git Branch Split:**  
  * **App 1 (feature/atcs-topology-generator):** Contains atcs\_extract.py and atcs\_topology\_viewer. Focuses on spatial network JSON extraction and visual topology layout rendering.  
  * **App 2 (feature/atcs-traffic-generator):** Contains atcs\_stubs.py and atcs\_traffic\_generator.py. Produces stubs, 1,440-minute traffic probability profiles, text-to-API stub agent, and profile-driven time-series execution engine.  
  * **App 3 (feature/atcs-traffic-simulation):** Contains atcs\_simulator.py. Executes runtime simulation across Device (MQTT) and Controller (PostgreSQL/REST) layers with autonomous LangGraph AI Agent control and live parameter management.  
  * **App 4 (feature/atcs-analytics-dashboard):** Supports multi-day continuous simulation execution, daily stochastic seed modulation, dynamic agentic optimization comparison against static baselines, and the agentic optimization analytical dashboard.  
* **Core Languages & Frameworks:** Python, GeoPandas (spatial topology and road network modeling), LangGraph (agent orchestration), FastAPI/Flask (Controller REST API).  
* **Messaging & Protocols:** MQTT (Mosquitto / EMQX) for edge device messaging; REST APIs (JSON/HTTP) for Agent-Controller control plane.  
* **Data Persistence:** PostgreSQL (spatial topology, state history, event logs).

---

# **5\. Communication & Data Flow Model**

* **MQTT Topics (Device Layer \<-\> Controller):**  
  * `devices/{district_id}/{intersection_id}/{device_type}/{device_id}/telemetry` (Publish)  
  * `devices/{district_id}/{intersection_id}/{device_type}/{device_id}/command` (Subscribe)  
* **REST API Endpoints (Agent Layer \<-\> Controller):**  
  * `GET /api/v1/districts/{id}/topology`: GeoPandas network spatial layout.  
  * `GET /api/v1/intersections/{id}/metrics`: Query detector data and light states (Tool Endpoint).  
  * `POST /api/v1/intersections/{id}/lights/command`: Update signal timing variables and state overrides.  
* **Viewer Layer Data Pipeline (Controller / PostgreSQL \-\> Viewer):**  
  * `GET /api/v1/state/snapshot`: Continuous or polled query against PostgreSQL state tables to refresh overlay sprite states on the ATCS Topology Viewer canvas.

---

# **6\. Phased Delivery Model (Scrum & Sprint Plan)**

* **Sprint 1 (App 1 \- Topology Extraction & Visual Viewer):** Establish git branch feature/atcs-topology-generator focusing on urban spatial network extraction and visual topology rendering. Deliverables include: 1\) atcs\_extract.py to extract spatial road network geometry from district/country inputs to JSON format and generate the background layout image map; 2\) atcs\_topology\_viewer as a visual viewer rendering overlay canvas sprites (roads, lights, intersections, districts) aligned directly over the background layout image map based on PostgreSQL topology state.  
* **Sprint 2 (App 2 \- Stub Creation, Traffic Profiling & Flow Activation):** Establish git branch feature/atcs-traffic-generator focusing on edge boundary stubs creation, manual traffic profiling, text-to-API stub agent, and profile-driven time-series state execution engine. Deliverables include: 1\) Automated/manual Stub Creation (atcs\_stubs.py) generating boundary Generator and Absorber edge stubs along district endpoints; 2\) Manual Generation & Easy Profiling (0-100% Probability Weights) to manually assign 0% to 100% output/attraction weights across the 1,440-minute daily cycle; 3\) Stub AI Agent Implementation converting text/natural language commands into Controller REST API calls to mutate device and stub states; 4\) Time-Series Profile-Driven State Controller Execution Engine dynamically applying daily profiles from atcs\_traffic\_generator.py based on simulation date/time to push parameter updates to Controllers/Stubs, activating and shifting network traffic flow in real time over the 24-hour cycle.  
* **Sprint 3 (App 3 \- Simulation Engine, AI Agent Control & Live Demo):** Establish git branch feature/atcs-traffic-simulation focusing on autonomous agent orchestration based on stubs traffic profiles and device spatial information, simulation engine execution, live parameters adjustment, and demo execution strategy. Deliverables include: 1\) Core Simulation Engine (atcs\_simulator.py) ingesting spatial JSON topology, layout image, and daily traffic profiles to execute minute-by-minute macroscopic simulation across Device Layer (MQTT state machines) and Controller Layer (PostgreSQL state tables & REST API); 2\) Agent Layer (LangGraph) with autonomous AI Agents utilizing spatial topology and live stub traffic profiles to issue dynamic signal timing commands (adjusting light timing variables and phase states across districts); 3\) Live Parameter Control & Demo Execution Strategy enabling interactive live parameter adjustment during simulation runtime, featuring the Single-Source Single-Sink Flow Routing Demo with dynamic intersection path selection (stochastic routing towards active absorbers).  
* **Sprint 4 (App 4 \- Multi-Day Analytics & Agentic Optimization Dashboard):** Establish git branch feature/atcs-analytics-dashboard focusing on long-term continuous multi-day evaluation, stochastic variance modeling, and comparative analytics dashboards. Deliverables include: 1\) Multi-Day Simulation Execution (e.g., 1-Month Runs) extending atcs\_simulator.py to execute long-term continuous multi-day simulation cycles (30-day runs); 2\) Daily Stochastic Seed Modulation applying a unique random seed per simulated day to introduce natural daily variance in vehicle routing and flow while retaining baseline profile guidance; 3\) Dynamic Agentic Optimization vs. Static Baselines re-running simulation comparisons where fixed/static controller variables are evaluated against the autonomous LangGraph Agentic System continuously optimizing signal timings and road networks; 4\) Agentic Optimization Analytical Dashboard providing an interactive interface visualizing waiting time reductions, queue density improvements, throughput gains, and agent action logs over the 1-month evaluation period.  
* **First Demo Execution Strategy (App 3 / atcs\_simulator.py):**  
  * **Single-Source Single-Sink Flow Routing Demo:** Only 1 primary Generator stub is set to active flow generation (e.g., 100% / 1.0 probability); all other Generators are initialized to 0%. Only 1 target Absorber stub is set to active absorption (e.g., 100% / 1.0 demand capacity); all other Absorbers are set to 0%.  
  * **Dynamic Intersection Path Selection:** At each multi-way intersection node, outgoing road selection is determined dynamically using destination Absorber preference weights combined with a configurable stochastic factor ("pinch of randomness", e.g., 85% deterministic target path weighting \+ 15% random distribution).  
  * **Generation & Absorption Profile Guidance:** The simulation engine dynamically ingests time-series demand profiles (from atcs\_traffic\_generator.py) to modulate generator output rates and absorber attraction weights over the simulation timeline.