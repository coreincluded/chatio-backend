"""E2E smoke tests — simulates a real user flow.

Registers, logs in, creates org channel, lists it, verifies isolation.
This is the test the QA agent runs before any deploy.
"""
from tests.conftest import auth


def test_full_user_journey(client):
    """Register → Login → /me (get org_id) → Create channel → List → Verify."""
    # 1. Register
    r = client.post("/api/v1/auth/register", json={
        "email": "smoke@test.com", "username": "smokeuser",
        "full_name": "Smoke Tester", "password": "smoke1234",
    })
    assert r.status_code == 201

    # 2. Login
    r = client.post("/api/v1/auth/login", json={
        "email": "smoke@test.com", "password": "smoke1234",
    })
    assert r.status_code == 200
    token = r.json()["access_token"]

    # 3. Get /me — must return organization_id
    r = client.get("/api/v1/auth/me", headers=auth(token))
    assert r.status_code == 200
    me = r.json()
    assert me["email"] == "smoke@test.com"
    assert me["organization_id"] is not None, "/me must return organization_id"
    org_id = me["organization_id"]

    # 4. Create a LINE channel
    r = client.post("/api/v1/channels", params={"org_id": org_id},
                    headers=auth(token), json={
                        "name": "Smoke LINE", "channel_type": "line_oa",
                        "external_channel_id": "smoke_line_123",
                        "access_token": "smoke-token",
                    })
    assert r.status_code == 201, f"Channel create failed: {r.text}"
    ch = r.json()
    assert ch["is_active"] is True

    # 5. List channels — should see exactly 1
    r = client.get("/api/v1/channels", params={"org_id": org_id}, headers=auth(token))
    assert r.status_code == 200
    channels = r.json()
    assert len(channels) == 1
    assert channels[0]["name"] == "Smoke LINE"


def test_two_users_fully_isolated(client):
    """Two users register, each creates a channel, neither can see the other's."""
    users = []
    for i, name in enumerate(["userA", "userB"]):
        # Register
        r = client.post("/api/v1/auth/register", json={
            "email": f"{name}@test.com", "username": name,
            "full_name": name.title(), "password": "pass1234",
        })
        assert r.status_code == 201

        # Login
        r = client.post("/api/v1/auth/login", json={
            "email": f"{name}@test.com", "password": "pass1234",
        })
        token = r.json()["access_token"]

        # Get org
        r = client.get("/api/v1/auth/me", headers=auth(token))
        org_id = r.json()["organization_id"]

        # Create channel
        r = client.post("/api/v1/channels", params={"org_id": org_id},
                        headers=auth(token), json={
                            "name": f"{name}'s Channel", "channel_type": "line_oa",
                            "external_channel_id": f"ext_{name}",
                            "access_token": f"tok_{name}",
                        })
        assert r.status_code == 201
        users.append({"token": token, "org_id": org_id, "name": name})

    # User A cannot see User B's org
    r = client.get("/api/v1/channels", params={"org_id": users[1]["org_id"]},
                   headers=auth(users[0]["token"]))
    assert r.status_code == 403, "User A should not access User B's org"

    # User B cannot see User A's org
    r = client.get("/api/v1/channels", params={"org_id": users[0]["org_id"]},
                   headers=auth(users[1]["token"]))
    assert r.status_code == 403, "User B should not access User A's org"


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
