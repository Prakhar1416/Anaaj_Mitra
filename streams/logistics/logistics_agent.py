from warehouse_data import WAREHOUSES


class LogisticsAgent:

    def __init__(self, coordinator):
        self.coordinator = coordinator

    def detect_mismatch(self):

        state = self.coordinator.get_state()

        required = state["warehouse"]["required_capacity_kg"]
        available = state["warehouse"]["available_capacity_kg"]

        if available < required:

            self.coordinator.update_state(
                "logistics",
                "transfer_needed",
                True
            )

            self.coordinator.add_log(
                "Logistics Agent",
                "mismatch_detected",
                f"Required capacity is {required} kg but only "
                f"{available} kg is available."
            )

            return True

        return False

    def request_bids(self):

        state = self.coordinator.get_state()

        required = state["warehouse"]["required_capacity_kg"]
        crop = state["warehouse"]["crop"]

        bids = []

        for warehouse in WAREHOUSES:

            capacity_ok = (
                warehouse["available_capacity_kg"] >= required
            )

            crop_ok = (
                crop in warehouse["compatible_crops"]
            )

            if capacity_ok and crop_ok:

                bids.append(warehouse)

                self.coordinator.add_log(
                    "Logistics Agent",
                    "bid_received",
                    f"{warehouse['name']} can accept "
                    f"{required} kg of {crop}."
                )

        return bids

    def select_warehouse(self, bids):

        if not bids:
            self.coordinator.add_log(
                "Logistics Agent",
                "negotiation_failed",
                "No suitable warehouse was found."
            )

            return None

        selected = max(
            bids,
            key=lambda x: x["available_capacity_kg"]
        )

        self.coordinator.update_state(
            "logistics",
            "selected_warehouse",
            selected["id"]
        )

        self.coordinator.add_log(
            "Logistics Agent",
            "warehouse_selected",
            f"{selected['name']} selected."
        )

        return selected

    def resolve_transfer(self, selected):

        if selected is None:
            return False

        self.coordinator.update_state(
            "logistics",
            "transfer_needed",
            False
        )

        self.coordinator.update_state(
            "logistics",
            "status",
            "resolved"
        )

        self.coordinator.add_log(
            "Logistics Agent",
            "transfer_resolved",
            f"Transfer resolved using {selected['name']}."
        )

        return True

    def run(self):

        mismatch = self.detect_mismatch()

        if not mismatch:

            self.coordinator.add_log(
                "Logistics Agent",
                "no_action",
                "Primary warehouse has sufficient capacity."
            )

            return

        bids = self.request_bids()

        selected = self.select_warehouse(bids)

        self.resolve_transfer(selected)