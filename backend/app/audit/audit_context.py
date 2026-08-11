def build_status_change_note(
    old_status: str,
    new_status: str,
    reason: str | None = None,
):
    note = (
        f"Status changed from "
        f"'{old_status}' to '{new_status}'."
    )

    if reason:
        note += f" Reason: {reason}"

    return note