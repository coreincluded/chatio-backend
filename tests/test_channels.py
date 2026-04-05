"""Channel CRUD + multi-tenant isolation tests."""
from tests.conftest import auth


def _create_channel(client, token, org_id, name="Test Channel"):
    return client.post(
        "/api/v1/channels", params={"org_id": org_id},
        headers=auth(token),
        json={
            "name": name, "channel_type": "line_oa",
            "external_channel_id": f"ext_{name.replace(' ', '_').lower()}",
            "access_token": "fake-token",
        },
    )


def test_create_channel(client, user_a, token_a):
    r = _create_channel(client, token_a, user_a.org_id, "My LINE")
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "My LINE"
    assert r.json()["is_active"] is True


def test_list_channels(client, user_a, token_a):
    _create_channel(client, token_a, user_a.org_id, "Ch1")
    _create_channel(client, token_a, user_a.org_id, "Ch2")
    r = client.get("/api/v1/channels", params={"org_id": user_a.org_id}, headers=auth(token_a))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_channel(client, user_a, token_a):
    cr = _create_channel(client, token_a, user_a.org_id, "GetMe")
    ch_id = cr.json()["id"]
    r = client.get(f"/api/v1/channels/{ch_id}", params={"org_id": user_a.org_id}, headers=auth(token_a))
    assert r.status_code == 200
    assert r.json()["name"] == "GetMe"


def test_update_channel(client, user_a, token_a):
    cr = _create_channel(client, token_a, user_a.org_id, "Old Name")
    ch_id = cr.json()["id"]
    r = client.patch(f"/api/v1/channels/{ch_id}", params={"org_id": user_a.org_id},
                     headers=auth(token_a), json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_delete_channel(client, user_a, token_a):
    cr = _create_channel(client, token_a, user_a.org_id, "DeleteMe")
    ch_id = cr.json()["id"]
    r = client.delete(f"/api/v1/channels/{ch_id}", params={"org_id": user_a.org_id}, headers=auth(token_a))
    assert r.status_code == 204


def test_user_b_cannot_list_user_a_channels(client, user_a, user_b, token_a, token_b):
    _create_channel(client, token_a, user_a.org_id, "Alice Only")
    r = client.get("/api/v1/channels", params={"org_id": user_a.org_id}, headers=auth(token_b))
    assert r.status_code == 403, f"Expected 403, got {r.status_code}"


def test_user_b_cannot_modify_user_a_channel(client, user_a, user_b, token_a, token_b):
    cr = _create_channel(client, token_a, user_a.org_id, "Private")
    ch_id = cr.json()["id"]
    assert client.get(f"/api/v1/channels/{ch_id}", params={"org_id": user_a.org_id}, headers=auth(token_b)).status_code == 403
    assert client.patch(f"/api/v1/channels/{ch_id}", params={"org_id": user_a.org_id},
                        headers=auth(token_b), json={"name": "Hacked"}).status_code == 403
    assert client.delete(f"/api/v1/channels/{ch_id}", params={"org_id": user_a.org_id},
                         headers=auth(token_b)).status_code == 403


def test_duplicate_channel_per_org(client, user_a, token_a):
    _create_channel(client, token_a, user_a.org_id, "Dup")
    r = client.post("/api/v1/channels", params={"org_id": user_a.org_id},
                    headers=auth(token_a), json={
                        "name": "Dup2", "channel_type": "line_oa",
                        "external_channel_id": "ext_dup", "access_token": "t2",
                    })
    assert r.status_code == 400


def test_no_auth_returns_401(client, user_a):
    r = client.get("/api/v1/channels", params={"org_id": user_a.org_id})
    assert r.status_code == 401
