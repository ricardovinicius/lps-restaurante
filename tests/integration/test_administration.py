"""Exercise the administration contract through an isolated Compose gateway."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import time
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = "/api/configuration/v1/configuration"
SESSION = "/api/configuration/v1/sessions"
CATALOG = "/api/catalog/v1"
ADMIN_PRODUCTS = CATALOG + "/admin/products"


@pytest.fixture(scope="module")
def deployment():
    project = "mesa-admin-test-" + uuid4().hex[:10]
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

        yield "http://" + compose("port", "gateway", "80"), passwords, compose
    finally:
        compose("down", "--volumes", "--remove-orphans")


def login(client, passwords, user):
    response = client.post(SESSION, json={"username": user, "password": passwords[user]})
    assert response.status_code == 201, response.text
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=lax" in response.headers["Set-Cookie"]
    response = client.get(SESSION + "/current")
    assert response.status_code == 200
    assert response.json()["role"] == user
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def test_staff_permissions_revocation_and_expiry(deployment):
    base, passwords, compose = deployment
    with httpx.Client(base_url=base) as client:
        assert client.get(ADMIN_PRODUCTS).status_code == 401
        assert client.get(CONFIG + "/export").status_code == 401
        failed = client.post(SESSION, json={"username": "admin", "password": "incorrect-test-secret"})
        assert failed.status_code == 401
        assert "incorrect-test-secret" not in failed.text

        login(client, passwords, "operator")
        current = client.get(CONFIG).json()
        payload = {"expected_revision": current["revision"], "features": current["features"]}
        assert client.put(CONFIG, json=payload).status_code == 403
        assert client.get(ADMIN_PRODUCTS).status_code == 403

        login(client, passwords, "admin")
        assert client.get(ADMIN_PRODUCTS).status_code == 200
        assert client.put(CONFIG, json=payload, headers={"X-CSRF-Token": "invalid"}).status_code == 403
        assert client.delete(SESSION + "/current", headers={"X-CSRF-Token": ""}).status_code == 403
        token = client.cookies["mesa_staff"]
        assert client.delete(SESSION + "/current").status_code == 204
        client.cookies.set("mesa_staff", token)
        assert client.get(ADMIN_PRODUCTS).status_code == 401
        client.cookies.clear()

        login(client, passwords, "admin")
        compose(
            "exec", "-T", "configuration", "python", "-c",
            "from mesa_platform.database import create_database_engine; "
            "from mesa_platform.settings import Settings; "
            "engine = create_database_engine(Settings()); "
            "connection = engine.connect(); "
            "connection.exec_driver_sql(\"UPDATE staff_sessions SET expires_at=now() - interval '1 hour'\"); "
            "connection.commit(); connection.close()",
        )
        assert client.get(SESSION + "/current").status_code == 401
        assert client.get(ADMIN_PRODUCTS).status_code == 401


def test_configuration_validation_concurrency_and_persistence(deployment):
    base, passwords, compose = deployment
    with httpx.Client(base_url=base) as admin, httpx.Client(base_url=base) as other:
        login(admin, passwords, "admin")
        login(other, passwords, "admin")
        current = admin.get(CONFIG).json()
        presets = admin.get(CONFIG + "/presets").json()
        assert len(presets) == 3
        assert admin.get(CONFIG).json() == current

        for overrides in [
            {"pickup": False, "delivery": False, "tables": False},
            {"tablet": True, "tables": False},
            {"catalog": False},
            {"orders": 1},
        ]:
            response = admin.put(CONFIG, json={
                "expected_revision": current["revision"],
                "features": {**current["features"], **overrides},
            })
            assert response.status_code == 422
            assert response.json()["error"]["details"]

        assert admin.get(CONFIG).json() == current

        def save(client, options):
            return client.put(CONFIG, json={
                "expected_revision": current["revision"],
                "features": {**current["features"], **options},
            })

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(save, admin, {"delivery": True})
            two = pool.submit(save, other, {"tables": True})
            responses = [one.result(), two.result()]
        assert sorted(response.status_code for response in responses) == [200, 409]
        saved = next(response.json() for response in responses if response.status_code == 200)
        assert saved["revision"] == current["revision"] + 1
        export = admin.get(CONFIG + "/export").json()
        assert export["name"] == "personalizado"
        assert export["features"] == saved["features"]
        assert ("deliveries" in export["services"]) == saved["features"]["delivery"]
        assert ("tables" in export["services"]) == saved["features"]["tables"]

        compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "configuration")
        deadline = time.monotonic() + 15
        while (response := admin.get(CONFIG)).status_code != 200 and time.monotonic() < deadline:
            time.sleep(0.5)

        assert response.json() == saved
        assert admin.get(CONFIG + "/export").json() == export


def test_catalog_filter_updates_and_concurrency(deployment):
    base, passwords, compose = deployment
    with httpx.Client(base_url=base) as admin, httpx.Client(base_url=base) as other:
        login(admin, passwords, "admin")
        login(other, passwords, "admin")
        page = admin.get(ADMIN_PRODUCTS).json()
        item = page["items"][0]
        path = CATALOG + "/products/" + item["id"]
        assert admin.get(CATALOG + "/products", params={"cursor": "invalid"}).status_code == 422
        filtered = admin.get(CATALOG + "/products", params={
            "q": item["name"], "category_id": item["category_id"],
        }).json()
        assert item in filtered["items"]

        public = admin.get(CATALOG + "/products", params={"limit": 1}).json()
        next_page = admin.get(CATALOG + "/products", params={"limit": 1, "cursor": public["next_cursor"]}).json()
        assert public["items"][0]["id"] != next_page["items"][0]["id"]

        assert admin.patch(path, json={"expected_revision": page["revision"], "price_cents": 0}).status_code == 422
        change = {"expected_revision": page["revision"], "available": False}
        assert admin.patch(path, json=change, headers={"X-CSRF-Token": "incorrect"}).status_code == 403
        assert admin.patch(CATALOG + "/products/" + str(uuid4()), json=change).status_code == 404

        def save(client, price):
            return client.patch(path, json={**change, "price_cents": price})

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(save, admin, 1234)
            two = pool.submit(save, other, 4321)
            responses = [one.result(), two.result()]

        assert sorted(response.status_code for response in responses) == [200, 409]
        updated = next(response.json() for response in responses if response.status_code == 200)
        assert updated["revision"] == page["revision"] + 1

        compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "catalog")
        deadline = time.monotonic() + 15
        while (response := admin.get(ADMIN_PRODUCTS)).status_code != 200 and time.monotonic() < deadline:
            time.sleep(0.5)

        assert response.json()["revision"] == updated["revision"]
        assert updated["product"] in response.json()["items"]
        public = admin.get(CATALOG + "/products", params={
            "q": item["name"], "category_id": item["category_id"],
        }).json()
        assert public["revision"] == updated["revision"]
        assert item["id"] not in [product["id"] for product in public["items"]]
