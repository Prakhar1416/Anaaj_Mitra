
class ServoActuatorSimulator:
    """
    Simulates a servo motor for warehouse release/rerouting.
    This is a software demonstration, not a physical motor controller.
    """

    CRITICAL_RISK_THRESHOLD = 75

    def run(self, state):
        spoilage = state.get("spoilage", {})
        risk_score = spoilage.get("spoilage_risk_score", 0)

        if risk_score >= self.CRITICAL_RISK_THRESHOLD:
            actuator_status = {
                "activated": True,
                "servo_angle": 90,
                "action": "RELEASE_OR_REROUTE",
                "message": (
                    "Critical spoilage risk detected. "
                    "Release/rerouting action recommended."
                )
            }
        else:
            actuator_status = {
                "activated": False,
                "servo_angle": 0,
                "action": "NORMAL",
                "message": "Storage is being monitored. No release action."
            }

        # Keep actuator information inside Stream 2's spoilage state.
        spoilage["actuator"] = actuator_status
        state["spoilage"] = spoilage

        return state
