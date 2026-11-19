# Anaaj Mitra — Project Report
### Engineering Project in Community Services (EPICS)

---

## 1. Project Overview

**Anaaj Mitra** (Hindi: *Grain Friend*) is a browser-based prototype of a Smart Village Agricultural Resource Coordination System. The project simulates a multi-agent AI framework designed to help rural farming communities manage agricultural warehouses, monitor environmental conditions, and make data-driven crop recommendations — all within a single-page web application.

| Attribute | Detail |
|---|---|
| Project Type | EPICS (Engineering Projects in Community Services) |
| Technology Stack | HTML5, CSS3, Vanilla JavaScript |
| Architecture | Single-Page Application (SPA) |
| Target Users | Village-level agricultural coordinators, farmers, warehouse managers |
| Year | 2026 |

---

## 2. Problem Statement

Rural farming communities face three persistent challenges:
1. **Unpredictable weather** leading to poor crop selection and drought losses.
2. **Post-harvest spoilage** due to unmonitored temperature and humidity in grain storage.
3. **Warehouse mismanagement** — capacity overflows or underutilisation due to lack of real-time monitoring.

Anaaj Mitra addresses these by simulating an intelligent coordination layer that integrates IoT sensor data with an AI multi-agent decision framework.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     ANAAJ MITRA SPA                     │
│                                                         │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  index   │   │   style.css  │   │   script.js    │  │
│  │  .html   │──▶│  (UI Layer)  │   │ (Logic Layer)  │  │
│  │ (Layout) │   └──────────────┘   └────────────────┘  │
│  └──────────┘                                           │
│                                                         │
│  UI Components:                                         │
│  Header → Stats → Dashboard Grid → Simulation → Log     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
  Multi-Agent Simulation (JS)
  ┌────────────┬──────────────┬─────────────────────────┐
  │ Water Agent│  Crop Agent  │ Spoilage / Storage /    │
  │            │              │ Logistics Agents        │
  └────────────┴──────────────┴─────────────────────────┘
```

**File Responsibilities:**

| File | Role |
|---|---|
| `index.html` | Semantic layout, all UI sections, element IDs for JS binding |
| `style.css` | Full visual design — responsive grid, cards, typography, colour system |
| `script.js` | Simulation logic, agent decision engine, DOM manipulation |

---

## 4. Feature List (Detailed)

### 4.1 Dashboard Header
- Displays the **Anaaj Mitra** brand logo with a wheat 🌾 icon.
- Shows a real-time **System Online** status indicator with an animated green dot, giving the impression of a live connected system.

---

### 4.2 Hero Section
- An **eyebrow label** ("SMART VILLAGE RESOURCE COORDINATION") establishes the domain context.
- A large `h1` headline — *"Intelligent Agricultural Resource Management"* — with a highlighted accent colour on key words.
- A descriptive paragraph summarising the system's purpose: "A trusted multi-agent AI framework for village resource coordination and agricultural warehouse management."

---

### 4.3 Statistics Cards (4 KPI Cards)
Four at-a-glance metric cards displayed in a responsive 4-column grid:

| Card | Metric | Default Value | Detail |
|---|---|---|---|
| Warehouse Fill | `#fillValue` | 72% | Includes a visual progress bar |
| Temperature | `#temperatureValue` | 27.4°C | With "Normal range" label |
| Humidity | `#humidityValue` | 61% | With "Monitoring" label |
| Trust Score | `#trustValue` | 86/100 | Dynamic — updates on simulation run |

The **progress bar** under "Warehouse Fill" is CSS-rendered and fixed at 72% width (representing current static utilisation).

---

### 4.4 IoT Sensor Data Panel
A "LIVE"-badged panel simulating readings from physical IoT hardware:

| Sensor | Hardware Reference | Default Reading | Dynamic? |
|---|---|---|---|
| Warehouse Capacity | HC-SR04 Ultrasonic Sensor | 72% | No (static) |
| Temperature | DHT11 / DHT22 Sensor | 27.4°C | Yes — updated on simulation run |
| Humidity | DHT11 / DHT22 Sensor | 61% | Yes — updated on simulation run |

The sensor references (DHT11/DHT22, HC-SR04) ground the prototype in real-world hardware context, relevant for the EPICS engineering audience.

---

### 4.5 Multi-Agent Status Panel
Displays the 5 agents in the system with their live status:

| Agent | Role | Status |
|---|---|---|
| Water Agent | Monitors rainfall and classifies drought risk | ACTIVE (green dot) |
| Crop Agent | Generates crop recommendations from environment data | ACTIVE (green dot) |
| Storage Agent | Monitors warehouse capacity utilisation | ACTIVE (green dot) |
| Logistics Agent | Coordinates warehouse movement and transfers | ACTIVE (green dot) |
| Health Agent | Community nutrition prioritisation | READY (grey dot — standby) |

The **Health Agent** being in "READY" (not "ACTIVE") state is intentional — it signals a future capability planned but not yet activated.

---

### 4.6 Environmental Simulation Engine
The core interactive feature. Three sliders allow the user to set environmental parameters, and a "▶ Run Simulation" button triggers the multi-agent decision pipeline.

**Input Controls:**

| Parameter | Range | Default | Unit |
|---|---|---|---|
| Rainfall | 0–150 | 42 | mm |
| Temperature | 10–50 | 27 | °C |
| Humidity | 20–100 | 61 | % |

- Sliders update their displayed value **live** (`oninput` → `updateValues()`).
- The "Run Simulation" button triggers `runSimulation()` which executes the full agent decision chain.

---

### 4.7 Multi-Agent Decision Engine (script.js)
The JavaScript simulation models a sequential inter-agent conversation. Here is the full logic:

#### Water Agent — Drought Risk Classification
```
Rainfall < 30 mm   → Drought Risk: HIGH
Rainfall 30–59 mm  → Drought Risk: MEDIUM
Rainfall ≥ 60 mm   → Drought Risk: LOW
```

#### Crop Agent — Crop Recommendation
Derived directly from drought risk:
```
HIGH   → Millet (drought-resistant)
MEDIUM → Millet / Sorghum
LOW    → Wheat / Rice
```

#### Spoilage Agent — Spoilage Risk Classification
Uses temperature AND humidity:
```
Temperature > 35°C  OR  Humidity > 80%  → Spoilage Risk: HIGH
Temperature > 30°C  OR  Humidity > 70%  → Spoilage Risk: MEDIUM
Otherwise                                → Spoilage Risk: LOW
```

#### Storage Agent
- Reports warehouse capacity (static: 72% verified).

#### Logistics Agent — Movement Recommendation
```
Spoilage Risk = HIGH → "Early movement recommended"
Otherwise            → "No urgent warehouse transfer required"
```

#### Trust Score — Dynamic Credibility Metric
```
Default:                      86/100
If Spoilage Risk = HIGH:      78/100
If Drought Risk = HIGH:       81/100
```
The trust score models system confidence — lower when risk conditions are severe.

---

### 4.8 Agent Conversation Log
A real-time coordination log that renders each agent's output as a styled message card after the simulation runs. Each message displays:
- The **agent name** (bold label with accent colour)
- The **agent's decision or observation** (readable plain text)

The log **clears and rewrites** on every new simulation run, keeping it current.

---

### 4.9 Responsive Design
The layout adapts for mobile/tablet via CSS media queries:
- At ≤800px viewport: all grids (stats, dashboard, controls) collapse to a single column.
- Font sizes and container widths scale down appropriately.

---

### 4.10 Footer
- Displays copyright: *"Anaaj Mitra © 2026 · Engineering Project in Community Services"*
- Anchors the project's academic context.

---

## 5. Design System

### Colour Palette
| Role | Colour |
|---|---|
| Background | `#f4f7f2` (light sage green) |
| Primary Text | `#172018` (near black) |
| Accent / Primary | `#628b57` (forest green) |
| Secondary Text | `#667267` / `#7a8579` |
| Active Status | `#55a864` / `#42a85f` |
| Card Background | `#ffffff` |
| Progress/Tag Fill | `#729866` |

The colour system is entirely green-toned — consistent with agriculture, nature, and sustainability.

### Typography
- Font family: `Arial, sans-serif`
- H1: 46px, line-height 1.05
- Stat cards: 30px H2, 11px uppercase labels
- Sensor values: 16px bold
- Messages: 13px body, 10px agent label

### Component System
- **Cards**: `border-radius: 16px`, soft `box-shadow`, 1px border
- **Badges/Tags**: Pill-shaped with `border-radius: 20px`
- **Progress Bar**: Full-width track with a filled green `div`
- **Range Inputs**: Styled with `accent-color: #668e5d`

---

## 6. Technical Stack

| Layer | Technology |
|---|---|
| Markup | HTML5 (semantic tags: `header`, `main`, `section`, `footer`) |
| Styling | CSS3 (Grid, Flexbox, custom properties, media queries) |
| Logic | Vanilla JavaScript (DOM manipulation, conditional logic) |
| Hosting | Static — no backend, no dependencies, no build step |

**Dependencies:** None. Zero external libraries, frameworks, or APIs. Fully self-contained.

---

## 7. Agents Summary Table

| Agent | Input | Output | Status |
|---|---|---|---|
| Water Agent | Rainfall (mm) | Drought risk level | Active |
| Crop Agent | Drought risk | Crop recommendation | Active |
| Spoilage Agent | Temperature + Humidity | Spoilage risk level | Active |
| Storage Agent | (Internal) | Capacity report | Active |
| Logistics Agent | Spoilage risk | Movement recommendation | Active |
| Health Agent | (Not yet implemented) | Nutrition priority | Ready |

---

## 8. Limitations & Future Scope

### Current Limitations
1. **No real IoT integration** — sensor values are simulated via sliders, not actual hardware data.
2. **Static warehouse data** — the 72% fill level is hardcoded and does not change with simulation runs.
3. **No data persistence** — all state is lost on page refresh.
4. **Single-variable trust score** — the trust model is simplistic and does not reflect real agent agreement protocols.
5. **Health Agent not functional** — it appears in the UI but has no logic wired up.
6. **No authentication** — open access, no user roles.

### Suggested Future Enhancements
- Connect real DHT11/DHT22 and HC-SR04 sensors via a Raspberry Pi / Arduino + WebSocket bridge.
- Add a backend (Node.js / Python Flask) for data persistence and historical trend charts.
- Implement the Health Agent logic (malnutrition risk scoring based on crop yield and rainfall data).
- Integrate weather API (e.g., OpenWeatherMap) for real rainfall data.
- Add a map view showing multiple village warehouses.
- Replace the trust score with a proper multi-agent consensus algorithm.
- Add multilingual support (Hindi, regional languages) for village-level accessibility.

---

## 9. Project Context

This project was developed as part of **EPICS (Engineering Projects in Community Services)**, a program where engineering students apply their technical skills to real-world community problems. Anaaj Mitra targets the underserved problem of agricultural resource mismanagement in rural Indian villages, aligning with themes of food security, smart agriculture, and sustainable development.

---

*Anaaj Mitra © 2026 — Engineering Project in Community Services*
