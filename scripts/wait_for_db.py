import socket
import time

from core.config import settings


def wait_for_db(host=None, port=None, timeout=60, interval=2, connect_timeout=5):
    """Poll the configured database host and port until TCP connectivity is available."""
    if host is None:
        host = getattr(settings, "DB_HOST", None) or getattr(settings, "DATABASE_HOST", "localhost")

    if port is None:
        port = getattr(settings, "DB_PORT", None)
        if port is None:
            port = getattr(settings, "DATABASE_PORT", 5432)

    port = int(port)
    deadline = time.monotonic() + timeout
    last_error = None

    while True:
        try:
            with socket.create_connection((host, port), timeout=connect_timeout):
                return True
        except OSError as exc:
            last_error = exc

        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Database connection to {host}:{port} was not established within {timeout} seconds"
            ) from last_error

        time.sleep(interval)


if __name__ == "__main__":
    wait_for_db()
