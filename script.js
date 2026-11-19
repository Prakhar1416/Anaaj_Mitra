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



function runSimulation() {

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