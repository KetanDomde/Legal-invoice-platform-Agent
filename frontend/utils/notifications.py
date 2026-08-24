from __future__ import annotations

import time

import streamlit as st


FLASH_QUEUE_KEY = "_flash_notifications"
FLASH_ALREADY_SHOWN_KEY = "_flash_notifications_shown"


def flash(message: str, level: str = "info") -> None:
    """
    Queue a temporary floating notification.

    The notification survives one st.rerun() so that a page can:
    1. perform an action,
    2. queue the message,
    3. rerun,
    4. display the message on the SAME page.
    """

    queue = st.session_state.setdefault(FLASH_QUEUE_KEY, [])

    queue.append(
        {
            "message": str(message),
            "level": str(level or "info").lower(),
        }
    )

    # A new message means the next page execution should display the queue.
    st.session_state.pop(FLASH_ALREADY_SHOWN_KEY, None)


def show_flash_messages() -> None:
    """
    Display queued notifications as floating Streamlit toasts.

    Behaviour:
    - Toasts do not consume page layout space.
    - The first notification appears immediately.
    - Additional notifications appear with a 1-second gap.
    - The queue is removed immediately after being consumed, so old
      notifications cannot appear later on another page.
    - No unsupported `duration` argument is passed to st.toast().
    """

    # Prevent accidental duplicate display during the same execution cycle.
    if st.session_state.get(FLASH_ALREADY_SHOWN_KEY):
        return

    queue = st.session_state.pop(FLASH_QUEUE_KEY, [])

    if not queue:
        return

    st.session_state[FLASH_ALREADY_SHOWN_KEY] = True

    icon_map = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    }

    for index, item in enumerate(queue):
        if index > 0:
            time.sleep(1)

        level = item.get("level", "info")

        st.toast(
            item.get("message", ""),
            icon=icon_map.get(level, "ℹ️"),
        )