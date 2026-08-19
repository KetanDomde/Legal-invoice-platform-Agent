import logging
import uuid
from contextvars import ContextVar

# Context variable to hold request_id globally per request execution context
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="N/A")


class RequestIDLogFilter(logging.Filter):
    """Injects the request_id context variable into all log records."""

    def filter(self, record):
        record.request_id = request_id_ctx.get()
        return True


# Configure logger output format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Req-ID: %(request_id)s] %(message)s",
)

logger = logging.getLogger("app_logger")
logger.addFilter(RequestIDLogFilter())

# Also attach the same filter to the root logger and existing handlers so
# third-party/early loggers (httpx, uvicorn, etc.) gain the `request_id`
# attribute before formatting. This prevents `KeyError: 'request_id'` when
# the global format references `%(request_id)s`.
_req_filter = RequestIDLogFilter()
root_logger = logging.getLogger()
root_logger.addFilter(_req_filter)
for _h in list(root_logger.handlers):
    _h.addFilter(_req_filter)


def ensure_request_id(req_id: str | None) -> str:
    """Return a request id (generate one if None) and set it in the context."""
    if not req_id:
        req_id = str(uuid.uuid4())
    request_id_ctx.set(req_id)
    return req_id
