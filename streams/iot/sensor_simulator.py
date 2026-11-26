
from datetime import datetime, timedelta, timezone
import random

# These distances represent the empty and full warehouse levels.
EMPTY_DISTANCE_CM = 100
FULL_DISTANCE_CM = 10


def generate_sensor_reading(index, scenario="spoilage"):
    """
    Generate simulated sensor readings.

    Each generated reading represents one simulated day.
    This allows us to test temperature and humidity trends
    quickly without waiting for real days.
    """

    base_time = datetime.now(timezone.utc)
    timestamp = base_time + timedelta(days=index)

    # Simulated warehouse fill level
    fill_pct = 35 + (index * 2)
    fill_pct = min(fill_pct, 95)

    # Convert fill percentage into ultrasonic distance.
    distance_cm = (
        EMPTY_DISTANCE_CM
        - (fill_pct / 100)
        * (EMPTY_DISTANCE_CM - FULL_DISTANCE_CM)
    )

    distance_cm += random.uniform(-0.5, 0.5)

    if scenario == "spoilage":
        # Temperature and humidity gradually increase.
        temperature = 24 + (index * 0.9)
        humidity = 55 + (index * 2.4)

    elif scenario == "normal":
        # Stable storage conditions.
        temperature = 24 + random.uniform(-0.3, 0.3)
        humidity = 55 + random.uniform(-1, 1)

    else:
        raise ValueError("Scenario must be 'spoilage' or 'normal'.")

    return {
        "timestamp": timestamp.isoformat(),
        "distance_cm": round(distance_cm, 2),
        "temperature_c": round(temperature, 2),
        "humidity_pct": round(humidity, 2),
        "scenario": scenario
    }
