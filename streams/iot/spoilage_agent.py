
from datetime import datetime


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def calculate_slope(values):
    """
    Calculate a simple linear trend per simulated day.
    """

    if len(values) < 2:
        return 0.0

    x_values = list(range(len(values)))

    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(values) / len(values)

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(x_values, values)
    )

    denominator = sum(
        (x - x_mean) ** 2
        for x in x_values
    )

    if denominator == 0:
        return 0.0

    return numerator / denominator


class SpoilageRiskAgent:

    def run(self, state):

        sensor = state["sensor"]
        spoilage = state["spoilage"]

        temperature = sensor["temperature_c"]
        humidity = sensor["humidity_pct"]

        history = spoilage.setdefault("history", [])

        history.append({
            "timestamp": sensor["timestamp"],
            "temperature_c": temperature,
            "humidity_pct": humidity
        })

        # Keep the latest 30 readings.
        history[:] = history[-30:]

        temperatures = [
            item["temperature_c"] for item in history
        ]

        humidities = [
            item["humidity_pct"] for item in history
        ]

        temp_slope = calculate_slope(temperatures)
        humidity_slope = calculate_slope(humidities)

        # Illustrative prototype thresholds.
        # These must be calibrated for the actual crop.
        TEMP_LIMIT = 30
        HUMIDITY_LIMIT = 75

        temp_score = (
            clamp((temperature - 20) / 10, 0, 1) * 50
        )

        humidity_score = (
            clamp((humidity - 50) / 25, 0, 1) * 50
        )

        trend_bonus = (
            max(0, temp_slope) * 2
            + max(0, humidity_slope) * 0.5
        )

        risk_score = clamp(
            temp_score + humidity_score + trend_bonus,
            0,
            100
        )

        # Estimate time remaining before threshold crossing.
        eta_values = []

        if temperature >= TEMP_LIMIT:
            eta_values.append(0)

        elif temp_slope > 0:
            eta_values.append(
                (TEMP_LIMIT - temperature) / temp_slope
            )

        if humidity >= HUMIDITY_LIMIT:
            eta_values.append(0)

        elif humidity_slope > 0:
            eta_values.append(
                (HUMIDITY_LIMIT - humidity) / humidity_slope
            )

        eta_days = (
            round(min(eta_values), 2)
            if eta_values else None
        )

        if risk_score >= 75 or (
            eta_days is not None and eta_days <= 3
        ):
            risk_level = "CRITICAL"

        elif risk_score >= 50:
            risk_level = "HIGH"

        elif risk_score >= 25:
            risk_level = "MODERATE"

        else:
            risk_level = "LOW"

        state["spoilage"].update({
            "temperature_c": temperature,
            "humidity_pct": humidity,
            "temperature_trend_per_day": round(temp_slope, 2),
            "humidity_trend_per_day": round(humidity_slope, 2),
            "spoilage_risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "eta_days": eta_days
        })

        return state
