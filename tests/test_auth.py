"""Auth endpoint tests."""from tests.conftest import authdef test_register_and_login(client):    r = client.post("/api/v1/auth/register", json={        "email": "new@test.com", "username": "newuser",        "full_name": "New User", "password": "test1234",    })    assert r.status_code == 201, r.text    assert r.json()["email"] == "new@test.com"    r = client.post("/api/v1/auth/login", json={        "email": "new@test.com", "password": "test1234",    })    assert r.status_code == 200    assert "access_token" in r.json()def test_login_wrong_password(client, user_a):    r = client.post("/api/v1/auth/login", json={        "email": "alice@test.com", "password": "wrong",    })    assert r.status_code == 401def test_me_returns_org_id(client, user_a, token_a):    r = client.get("/api/v1/auth/me", headers=auth(token_a))    assert r.status_code == 200, r.text    data = r.json()    assert data["email"] == "alice@test.com"    assert data["organization_id"] == user_a.org_id    assert data["organization_name"] is not Nonedef test_me_no_token(client):    r = client.get("/api/v1/auth/me")    assert r.status_code == 401def test_duplicate_email_register(client, user_a):    r = client.post("/api/v1/auth/register", json={        "email": "alice@test.com", "username": "alice2",        "full_name": "Alice 2", "password": "test1234",    })    assert r.status_code == 400    assert "already registered" in r.json()["detail"]

# --- Password Reset Tests ---

def test_forgot_password_existing_email(client, user_a):
    """forgot-password returns a reset token for registered emails."""
    r = client.post("/api/v1/auth/forgot-password", json={"email": "alice@test.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["reset_token"] is not None
    assert "Reset token" in data["message"]


def test_forgot_password_unknown_email(client):
    """forgot-password does NOT reveal whether email exists."""
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@test.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["reset_token"] is None


def test_reset_password_success(client, user_a):
    """Full forgot -> reset -> login-with-new-password flow."""
    # 1. get token
    r = client.post("/api/v1/auth/forgot-password", json={"email": "alice@test.com"})
    token = r.json()["reset_token"]
    # 2. reset
    r = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "newpass123",
    })
    assert r.status_code == 200
    assert "successful" in r.json()["message"]
    # 3. login with new password
    r = client.post("/api/v1/auth/login", json={
        "email": "alice@test.com", "password": "newpass123",
    })
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_reset_password_short_password(client, user_a):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "alice@test.com"})
    token = r.json()["reset_token"]
    r = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "ab",
    })
    assert r.status_code == 400
    assert "at least 6" in r.json()["detail"]


def test_reset_password_invalid_token(client):
    r = client.post("/api/v1/auth/reset-password", json={
        "token": "bad.token.here", "new_password": "newpass123",
    })
    assert r.status_code == 400

