from pathlib import Path
import os
import subprocess
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def deployment():
    project = "mesa-pickup-test-" + uuid4().hex[:10]
    env = {**os.environ, "MESA_HTTP_PORT": "0", "MESA_SECURE_COOKIES": "0"}
    passwords = {"admin": "AdminTestPassword", "operator": "OperatorTestPassword"}
    env.update({f"MESA_DEMO_{user.upper()}_PASSWORD": password for user, password in passwords.items()})

    def compose(*args):
        result = subprocess.run(
            ["docker", "compose", "-p", project, "--env-file", ".env.example", *args],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"Compose {args[0]} falhou:\n{result.stderr[-4000:]}")
        return result.stdout.strip()

    try:
        compose("up", "-d", "--build", "--wait", "--wait-timeout", "180", "gateway")
        for service in ("configuration", "catalog"):
            compose("exec", "-T", service, "python", "-m", "mesa_platform.seed", service)
        for service in ("configuration", "catalog", "orders"):
            compose("exec", "-T", service, "python", "-c", (ROOT / "tests/integration/database_checks.py").read_text())

        yield "http://" + compose("port", "gateway", "80"), passwords, compose
    finally:
        compose("down", "--volumes", "--remove-orphans")
