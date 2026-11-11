"""End-to-end infrastructure check using an isolated, disposable Compose project.

Never targets the development project or removes its volumes. Docker required.
"""

import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ["configuration", "catalog", "orders", "deliveries", "tables"]


def main():
    project = "mesa-verify-" + uuid4().hex[:10]
    environment = dict(os.environ)
    # An ephemeral host port avoids conflicts with the development gateway.
    environment["MESA_HTTP_PORT"] = "0"
    compose = ["docker", "compose", "--project-name", project,
               "--env-file", str(ROOT / ".env.example"), "-f", str(ROOT / "compose.yaml")]

    def run(*args, source=None):
        result = subprocess.run(compose + list(args), cwd=ROOT, env=environment,
                                input=source, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"Compose command failed: {' '.join(args[:3])}\n{result.stderr[-3000:]}")
        return result.stdout.strip()

    def python(service, source):
        return run("exec", "-T", service, "python", "-", source=source)

    try:
        print(f"Starting isolated project {project}", flush=True)
        run("up", "-d", "--build", "--wait", "--wait-timeout", "180")
        address = run("port", "gateway", "80")
        base = f"http://{address}"

        for service in SERVICES:
            run("exec", "-T", service, "python", "-m", "mesa_platform.seed", service)
            # Migrations and seeding are both repeatable.
            run("exec", "-T", service, "python", "-m", "mesa_platform.migrations", service)
            run("exec", "-T", service, "python", "-m", "mesa_platform.seed", service)
            print(python(service, (ROOT / "tests/integration/database_checks.py").read_text()), flush=True)

        # Preserve real changes across re-seeding and container recreation.
        python("catalog", '''
from sqlalchemy import text
from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings
engine = create_database_engine(Settings())
with engine.begin() as c:
    c.execute(text("UPDATE products SET price_cents=7777, available=false"))
engine.dispose()
''')
        run("exec", "-T", "catalog", "python", "-m", "mesa_platform.seed", "catalog")
        assert python("catalog", '''
from sqlalchemy import text
from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings
engine = create_database_engine(Settings())
with engine.connect() as c:
    assert c.scalar(text("SELECT count(*) FROM products WHERE price_cents=7777 AND NOT available")) == 8
engine.dispose()
print("preserved")
''') == "preserved"

        # A committed sample order verifies storage, not the unimplemented checkout.
        python("orders", '''
from sqlalchemy import text
from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings
engine = create_database_engine(Settings())
with engine.begin() as c:
    c.execute(text("""INSERT INTO orders (id, origin, fulfillment, customer_name, state,
      version, configuration_revision, catalog_revision, fee_cents, total_cents)
      VALUES ('00000000-0000-0000-0000-000000000042','client','pickup','Demonstração',
      'received',1,1,1,0,3290)"""))
    c.execute(text("""INSERT INTO order_items (order_id,product_id,name,unit_price_cents,quantity,subtotal_cents)
      VALUES ('00000000-0000-0000-0000-000000000042','00000000-0000-0000-0000-000000000043',
      'Produto demonstrativo',3290,1,3290)"""))
engine.dispose()
''')
        snapshot_script = '''
import importlib, json, os
from sqlalchemy import select
from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings
engine = create_database_engine(Settings())
metadata = importlib.import_module("services."+os.environ["MESA_SERVICE"]+".models").Base.metadata
with engine.connect() as c:
    result = {t.name: sorted([dict(r._mapping) for r in c.execute(select(t))], key=lambda row: str(row)) for t in metadata.sorted_tables}
print(json.dumps(result, default=str, sort_keys=True))
engine.dispose()
'''
        before = {s: python(s, snapshot_script) for s in SERVICES}
        run("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180")
        # The ephemeral port can change after gateway recreation.
        base = "http://" + run("port", "gateway", "80")
        after = {s: python(s, snapshot_script) for s in SERVICES}
        assert before == after, "Data changed across container recreation"
        print("Persisted configuration, catalog, tables and sample order survived recreation", flush=True)

        # Recreate only backends, keeping the existing gateway and its DNS cache.
        run("up", "-d", "--force-recreate", "--no-deps", "--wait", *SERVICES)
        deadline = time.monotonic() + 20
        while True:
            try:
                for service in SERVICES:
                    with urllib.request.urlopen(f"{base}/api/{service}/health/ready", timeout=5) as response:
                        assert json.load(response) == {"service": service, "status": "ok"}
                break
            except (urllib.error.URLError, AssertionError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        print("Gateway re-resolves service addresses after backend-only recreation", flush=True)

        for service in SERVICES:
            with urllib.request.urlopen(f"{base}/api/{service}/health/ready", timeout=10) as response:
                assert response.status == 200
                assert json.load(response) == {"service": service, "status": "ok"}
                assert response.headers["X-Request-ID"]
        with urllib.request.urlopen(base, timeout=10) as response:
            assert response.status == 200
        for path in ["/internal/v1/test", "/api/configuration/internal/v1/test", "/api/deliveries/v1/test"]:
            try:
                urllib.request.urlopen(base + path, timeout=10)
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
            else:
                raise AssertionError(f"Internal path exposed: {path}")
        print("Gateway serves the React application, exposes health and blocks internal routes", flush=True)
    finally:
        run("down", "--volumes", "--remove-orphans")
        print(f"Removed only disposable project {project}", flush=True)


if __name__ == "__main__":
    main()
