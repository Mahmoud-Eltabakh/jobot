"""Run focused tests with disposable paths established before application imports."""

import os
import socket
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(tempfile.mkdtemp(prefix="jobot-17-04-tests-"))
    os.environ.update(
        DATABASE_URL=f"sqlite:///{(root / 'test.db').as_posix()}",
        CHROMA_DIR=str(root / "chroma"),
        ENCRYPTION_KEY_FILE=str(root / "key"),
        JOBOT_TESTING="1", ENV="testing", ANONYMIZED_TELEMETRY="False",
    )
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    original_connect = socket.socket.connect

    def guarded_connect(connection, address):
        import inspect
        if any(frame.function == "_fallback_socketpair" for frame in inspect.stack()):
            return original_connect(connection, address)
        raise AssertionError(f"Unmocked network connection blocked: {address}")

    socket.socket.connect = guarded_connect
    import pytest
    print(f"Disposable storage: {root}")
    return pytest.main(sys.argv[1:] + ["-o", "addopts="])


if __name__ == "__main__":
    raise SystemExit(main())