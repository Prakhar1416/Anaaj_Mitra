function updateValues() {

    const rainfall =
        document.getElementById("rainfall").value;

    const temperature =
        document.getElementById("temperature").value;

    const humidity =
        document.getElementById("humidity").value;


    document.getElementById("rainValue").innerText =
        rainfall + " mm";

    document.getElementById("tempControlValue").innerText =
        temperature + "°C";

    document.getElementById("humidityControlValue").innerText =
        humidity + "%";
}



async function runSimulation() {

    const note = document.getElementById("pipelineNote");

    if (note) {

        note.textContent = "Running water, crop, storage, spoilage, logistics, trust, and loan…";

    }

    try {

        const response = await fetch(healthApiBase() + "/api/pipeline/run", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                soil_type: document.getElementById("soilType").value,
                scenario: document.getElementById("storageScenario").value,
                temperature_c: Number(document.getElementById("temperature").value),
                humidity_pct: Number(document.getElementById("humidity").value),
                rainfall_mm: Number(document.getElementById("rainfall").value)
            })
        });

        if (!response.ok) {

            throw new Error("pipeline");

        }

        renderPipeline(await response.json());

        refreshHealthDashboard();

    } catch (error) {

        if (note) {

            note.textContent = "The coordination API is not reachable, so this run used the in-browser simulation only.";

        }

        runLocalSimulation();

    }
}


function renderPipeline(result) {

    const fill = Math.round(result.storage.fill_pct);

    document.getElementById("fillValue").innerText = fill + "%";

    document.getElementById("fillBar").style.width = fill + "%";

    document.getElementById("sensorFill").innerText = fill + "%";

    document.getElementById("temperatureValue").innerText = result.sensor.temperature_c + "°C";

    document.getElementById("sensorTemp").innerText = result.sensor.temperature_c + "°C";

    document.getElementById("humidityValue").innerText = result.sensor.humidity_pct + "%";

    document.getElementById("sensorHumidity").innerText = result.sensor.humidity_pct + "%";

    document.getElementById("trustValue").innerText =
        Math.round(result.trust.trust_score * 100) + "/100";

    markStreamAgent("water", result.water.groundwater_category);

    markStreamAgent("crop", result.crop.selected_crop);

    markStreamAgent("storage", result.storage.status);

    markStreamAgent("spoilage", result.spoilage.risk_level);

    markStreamAgent(
        "logistics",
        result.logistics.selected_warehouse || result.logistics.status || "HOLD"
    );

    markStreamAgent(
        "finance",
        result.loan.decision === "receipt" ? "RECEIPT" : "REVIEW"
    );

    const conversation = document.getElementById("conversation");

    conversation.innerHTML = "";

    result.conversation.forEach(function (entry) {

        addMessage(entry.agent.toUpperCase(), entry.message);

    });

    const cards = [
        [
            "Water",
            result.water.village + ", " + result.water.district
            + ". Groundwater " + result.water.groundwater_category
            + ". 30-day drought: " + result.water.drought_risk_30d + "."
        ],
        [
            "Crop",
            "Recommended " + result.crop.recommended_crops.join(", ")
            + ". Storage check: " + result.crop.storage_check.status + "."
        ],
        [
            "Storage",
            result.storage.status + ". Fill " + result.storage.fill_pct
            + "%. Free capacity " + result.storage.available_capacity_kg + " kg."
        ],
        [
            "Spoilage",
            result.spoilage.risk_level + " (score " + result.spoilage.spoilage_risk_score
            + "). " + result.spoilage.actuator.message
        ],
        [
            "Logistics",
            result.logistics.selected_warehouse
                ? "Neighbour warehouse " + result.logistics.selected_warehouse + " selected."
                : "Primary warehouse has enough capacity."
        ],
        [
            "Finance",
            "Trust " + result.trust.trust_score
            + ". Loan decision: " + result.loan.decision
            + (result.loan.receipt_id ? " (" + result.loan.receipt_id + ")." : ".")
        ]
    ];

    const host = document.getElementById("pipelineResults");

    host.innerHTML = "";

    cards.forEach(function (card) {

        const node = document.createElement("div");

        node.className = "pipeline-card";

        node.innerHTML = "<strong>" + card[0] + "</strong><p></p>";

        node.querySelector("p").textContent = card[1];

        host.appendChild(node);

    });

    const validation = document.createElement("div");

    validation.className = "pipeline-card";

    const validationText = document.createElement("p");

    validation.innerHTML = "<strong>Validation</strong>";

    validationText.textContent = result.validation.map(function (item) {

        return item.component + ": " + item.status;

    }).join(". ") + ".";

    validation.appendChild(validationText);

    host.appendChild(validation);

    if (noteExists()) {

        document.getElementById("pipelineNote").textContent = result.notes[0];

    }

    const stockNote = document.getElementById("healthStockNote");

    if (stockNote && result.warehouse) {

        stockNote.textContent =
            "Warehouse " + result.warehouse.warehouse_id
            + " now has " + result.warehouse.available_stock_kg
            + " kg of " + result.warehouse.grain_type
            + " from the storage agent. Submit a health report to reassess nutrition priority.";

    }
}


function noteExists() {

    return document.getElementById("pipelineNote");
}


function markStreamAgent(name, label) {

    const dot = document.getElementById(name + "AgentDot");

    const badge = document.getElementById(name + "Badge");

    if (dot) {

        dot.className = "agent-status active";

    }

    if (badge) {

        badge.textContent = String(label).toUpperCase();

    }
}


function runLocalSimulation() {

    const rainfall =
        document.getElementById("rainfall").value;

    const temperature =
        document.getElementById("temperature").value;

    const humidity =
        document.getElementById("humidity").value;


    let droughtRisk;

    if (rainfall < 30) {

        droughtRisk = "HIGH";

    } else if (rainfall < 60) {

        droughtRisk = "MEDIUM";

    } else {

        droughtRisk = "LOW";

    }


    let spoilageRisk;

    if (temperature > 35 || humidity > 80) {

        spoilageRisk = "HIGH";

    } else if (temperature > 30 || humidity > 70) {

        spoilageRisk = "MEDIUM";

    } else {

        spoilageRisk = "LOW";

    }


    document.getElementById("sensorTemp").innerText =
        temperature + "°C";

    document.getElementById("sensorHumidity").innerText =
        humidity + "%";


    const conversation =
        document.getElementById("conversation");


    conversation.innerHTML = "";


    addMessage(
        "WATER AGENT",
        "Rainfall received: " +
        rainfall +
        " mm. Drought risk: " +
        droughtRisk
    );


    let crop;

    if (droughtRisk === "HIGH") {

        crop = "Millet";

    } else if (droughtRisk === "MEDIUM") {

        crop = "Millet / Sorghum";

    } else {

        crop = "Wheat / Rice";

    }


    addMessage(
        "CROP AGENT",
        "Recommended crop: " +
        crop +
        ". Recommendation generated from environmental conditions."
    );


    addMessage(
        "SPOILAGE AGENT",
        "Temperature: " +
        temperature +
        "°C, Humidity: " +
        humidity +
        "%. Spoilage risk: " +
        spoilageRisk
    );


    addMessage(
        "STORAGE AGENT",
        "Warehouse capacity currently verified at 72%."
    );


    if (spoilageRisk === "HIGH") {

        addMessage(
            "LOGISTICS AGENT",
            "High spoilage risk detected. Early movement recommended."
        );

    } else {

        addMessage(
            "LOGISTICS AGENT",
            "No urgent warehouse transfer required."
        );

    }


    let trust =
        86;

    if (spoilageRisk === "HIGH") {

        trust = 78;

    }

    if (droughtRisk === "HIGH") {

        trust = 81;

    }


    document.getElementById("trustValue").innerText =
        trust + "/100";
}



function addMessage(agent, text) {

    const conversation =
        document.getElementById("conversation");


    const message =
        document.createElement("div");

    message.className = "message";


    message.innerHTML = `
        <span>${agent}</span>
        <p>${text}</p>
    `;


    conversation.appendChild(message);
}


function healthApiBase() {

    if (window.location.protocol === "file:") {

        return "http://127.0.0.1:8001";

    }

    if (window.location.port === "8000") {

        return "http://127.0.0.1:8001";

    }

    return "";
}


function markHealthAgent(online) {

    const dot = document.getElementById("healthAgentDot");

    const badge = document.getElementById("healthAgentBadge");

    if (!dot || !badge) {

        return;

    }

    dot.classList.toggle("active", online);

    badge.textContent = online ? "ACTIVE" : "READY";
}


function appendHealthMessage(parent, title, text) {

    const message = document.createElement("div");

    message.className = "message";

    const label = document.createElement("span");

    label.textContent = title;

    const body = document.createElement("p");

    body.textContent = text;

    message.appendChild(label);

    message.appendChild(body);

    parent.appendChild(message);
}


function renderHealthState(state) {

    const priorities = document.getElementById("healthPriorities");

    const decisions = document.getElementById("healthDecisions");

    const logs = document.getElementById("healthLogs");

    const stockNote = document.getElementById("healthStockNote");

    priorities.replaceChildren();

    decisions.replaceChildren();

    logs.replaceChildren();


    const warehouses = Object.values(state.warehouses || {});

    if (warehouses.length && stockNote) {

        const warehouse = warehouses[0];

        stockNote.textContent =
            warehouse.warehouse_id +
            " has " +
            warehouse.available_stock_kg +
            " kg of " +
            warehouse.grain_type +
            " (" +
            warehouse.stock_source +
            " stock). A recommendation does not complete a delivery.";

    }


    const hamlets = Object.values(state.hamlets || {});

    const priorityHamlets = hamlets.filter(function (hamlet) {

        return hamlet.health && hamlet.health.nutrition_priority;

    });

    if (!priorityHamlets.length) {

        appendHealthMessage(
            priorities,
            "NONE",
            "No hamlet is currently marked nutrition-priority."
        );

    }

    priorityHamlets.forEach(function (hamlet) {

        const reporter = hamlet.health.reported_by
            ? " · " + hamlet.health.reported_by
            : "";

        appendHealthMessage(
            priorities,
            hamlet.hamlet_id,
            (hamlet.health.reason || "No reason recorded") + reporter
        );

    });


    const withDecisions = hamlets.filter(function (hamlet) {

        return hamlet.logistics;

    });

    if (!withDecisions.length) {

        appendHealthMessage(
            decisions,
            "WAITING",
            "No logistics reassessment has been recorded."
        );

    }

    withDecisions.forEach(function (hamlet) {

        appendHealthMessage(
            decisions,
            hamlet.logistics.decision,
            hamlet.logistics.recommendation
        );

    });


    const entries = (state.agent_logs || []).slice(0, 6);

    if (!entries.length) {

        appendHealthMessage(logs, "LOG", "No agent events yet.");

    }

    entries.forEach(function (entry) {

        appendHealthMessage(
            logs,
            entry.agent_name + " · " + entry.status,
            entry.event_type + " — " + entry.result
        );

    });
}


async function refreshHealthDashboard() {

    const status = document.getElementById("healthStatus");

    try {

        const base = healthApiBase();

        const configResponse = await fetch(base + "/api/config");

        if (!configResponse.ok) {

            throw new Error("config");

        }

        const config = await configResponse.json();

        const select = document.getElementById("healthHamlet");

        const current = select.value;

        select.replaceChildren();

        config.hamlet_ids.forEach(function (hamletId) {

            const option = document.createElement("option");

            option.value = hamletId;

            option.textContent = hamletId;

            select.appendChild(option);

        });

        if (current) {

            select.value = current;

        }

        const stateResponse = await fetch(base + "/api/state");

        if (!stateResponse.ok) {

            throw new Error("state");

        }

        renderHealthState(await stateResponse.json());

        markHealthAgent(true);

        if (status && !status.dataset.hold) {

            status.textContent = "";

        }

    } catch (error) {

        if (status) {

            status.textContent =
                "Health backend is not reachable. The environmental simulation on this page still runs on its own.";

        }

        markHealthAgent(false);

    }
}


async function submitHealthReport(event) {

    event.preventDefault();

    const status = document.getElementById("healthStatus");

    const reason = document.getElementById("healthReason").value.trim();

    const reporter = document.getElementById("healthReporter").value.trim();

    const payload = {
        hamlet_id: document.getElementById("healthHamlet").value,
        nutrition_priority: document.getElementById("healthPriority").checked
    };

    if (reason) {

        payload.reason = reason;

    }

    if (reporter) {

        payload.reported_by = reporter;

    }

    status.dataset.hold = "1";

    status.textContent = "Submitting report…";

    try {

        const response = await fetch(healthApiBase() + "/api/health/reports", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const body = await response.json();

        if (!response.ok) {

            const detail = body.detail;

            status.textContent = detail && detail.message
                ? detail.message
                : "The health report was rejected.";

            return;

        }

        status.textContent = body.message;

        await refreshHealthDashboard();

    } catch (error) {

        status.textContent =
            "The health report could not be submitted. Start the backend with python run_all.py.";

    } finally {

        delete status.dataset.hold;

    }
}


document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("healthForm");

    const refresh = document.getElementById("healthRefresh");

    if (!form) {

        return;

    }

    form.addEventListener("submit", submitHealthReport);

    if (refresh) {

        refresh.addEventListener("click", refreshHealthDashboard);

    }

    refreshHealthDashboard();

});