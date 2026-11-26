
class StorageCapacityAgent:

    def run(self, state):

        sensor = state["sensor"]
        crop = state["crop"]
        config = state["config"]

        distance = sensor["distance_cm"]

        empty_distance = config["empty_distance_cm"]
        full_distance = config["full_distance_cm"]

        # Calculate warehouse fill percentage.
        fill_pct = (
            (empty_distance - distance)
            / (empty_distance - full_distance)
        ) * 100

        fill_pct = max(0, min(100, fill_pct))

        capacity = config["capacity_kg"]

        available_capacity = capacity * (1 - fill_pct / 100)

        incoming_quantity = config["incoming_quantity_kg"]

        required_type = crop["storage_type_required"]
        warehouse_type = config["warehouse_storage_type"]

        type_match = required_type == warehouse_type

        capacity_match = available_capacity >= incoming_quantity

        compatible = type_match and capacity_match

        if compatible:
            status = "COMPATIBLE"
        elif not type_match:
            status = "STORAGE TYPE MISMATCH"
        else:
            status = "INSUFFICIENT CAPACITY"

        state["storage"] = {
            "warehouse_id": config["warehouse_id"],
            "fill_pct": round(fill_pct, 2),
            "capacity_kg": capacity,
            "available_capacity_kg": round(
                available_capacity, 2
            ),
            "incoming_quantity_kg": incoming_quantity,
            "required_storage_type": required_type,
            "warehouse_storage_type": warehouse_type,
            "compatible": compatible,
            "status": status
        }

        return state
