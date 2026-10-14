"""Regression coverage for startup, authentication, persistence and pipeline APIs."""


def test_startup_and_authentication(client):
    assert client.get("/health").json()["status"] == "healthy"
    assert "/api/v1/deals" in client.get("/openapi.json").json()["paths"]
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", data={
        "username": "admin@example.com", "password": "wrong",
    }).status_code == 401


def test_authenticated_reads(authenticated):
    for path in [
        "auth/me", "leads", "deals", "deals/pipeline", "deals/stats",
        "deals/lists", "outreach/templates", "outreach/sequences",
        "outreach/campaigns", "scraping/jobs", "scraping/stats", "analytics/dashboard",
    ]:
        response = authenticated.get("/api/v1/" + path)
        assert response.status_code == 200, (path, response.text)


def test_lead_deal_and_activity_roundtrip(authenticated):
    client = authenticated
    response = client.post("/api/v1/leads", json={
        "company_name": "Regression Company", "source": "manual",
    })
    assert response.status_code == 201, response.text
    lead_id = response.json()["id"]
    response = client.post("/api/v1/deals", json={
        "name": "Regression Deal", "lead_id": lead_id, "value": 1500,
    })
    assert response.status_code == 201, response.text
    deal_id = response.json()["id"]
    assert "hashed_password" not in response.text
    response = client.patch(f"/api/v1/deals/{deal_id}/stage", json={"stage": "qualified"})
    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "qualified"
    response = client.post(f"/api/v1/deals/{deal_id}/activities", json={
        "deal_id": deal_id, "type": "note", "metadata": {"source": "regression"},
    })
    assert response.status_code == 201, response.text
    assert response.json()["metadata"] == {"source": "regression"}
    activity_id = response.json()["id"]
    response = client.patch(f"/api/v1/deals/activities/{activity_id}", json={
        "metadata": {"updated": True},
    })
    assert response.status_code == 200, response.text
    assert response.json()["metadata"] == {"updated": True}
    response = client.get(f"/api/v1/deals/{deal_id}/activities")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    for path in [f"deals/{deal_id}", "deals", "deals/pipeline"]:
        response = client.get("/api/v1/" + path)
        assert response.status_code == 200, response.text
    response = client.patch(f"/api/v1/leads/{lead_id}", json={"company_name": "Updated Company"})
    assert response.status_code == 200, response.text
    response = client.patch(f"/api/v1/deals/{deal_id}", json={"value": 2000})
    assert response.status_code == 200, response.text
    response = client.get("/api/v1/deals/stats")
    assert response.json()["total_deals"] == 1
    assert response.json()["total_value"] == 2000
    assert response.json()["by_stage"]["qualified"]["count"] == 1
    assert client.get("/api/v1/deals?stage=won").json()["total"] == 0
    assert client.get(f"/api/v1/deals?lead_id={lead_id}").json()["total"] == 1
    response = client.patch(f"/api/v1/deals/{deal_id}/stage", json={"stage": "won"})
    assert response.json()["probability"] == 100
    assert response.json()["actual_close_date"] is not None


def test_create_first_admin(client):
    import asyncio
    import pytest
    from app.cli import create_admin

    asyncio.run(create_admin("second@example.com", "Second Admin", "Second-Password-2026"))
    response = client.post("/api/v1/auth/login", data={
        "username": "second@example.com", "password": "Second-Password-2026",
    })
    assert response.status_code == 200, response.text
    with pytest.raises(ValueError, match="already exists"):
        asyncio.run(create_admin("second@example.com", "Changed", "Changed-Password-2026"))


def test_outreach_configuration_and_lead_lists(authenticated):
    client = authenticated
    response = client.post("/api/v1/outreach/templates", json={
        "name": "Test Email", "channel": "email", "body": "Hello {{company}}",
    })
    assert response.status_code == 201, response.text
    template_id = response.json()["id"]
    response = client.post("/api/v1/outreach/sequences", json={
        "name": "Test Sequence", "steps": [{
            "step_number": 1, "channel": "email", "template_id": template_id,
        }],
    })
    assert response.status_code == 201, response.text
    assert response.json()["steps"][0]["template_id"] == template_id
    response = client.get("/api/v1/outreach/sequences/" + response.json()["id"])
    assert response.status_code == 200, response.text

    response = client.post("/api/v1/deals/lists", json={"name": "Test List"})
    assert response.status_code == 201, response.text
    response = client.get("/api/v1/deals/lists/" + response.json()["id"])
    assert response.status_code == 200, response.text


def test_sales_permissions(authenticated):
    client = authenticated
    lead = client.post("/api/v1/leads", json={"company_name": "Private Company"}).json()
    deal = client.post("/api/v1/deals", json={"name": "Private Deal", "lead_id": lead["id"]}).json()
    response = client.post("/api/v1/auth/register", json={
        "email": "sales@example.com", "full_name": "Sales Rep", "password": "Sales-Password-2026", "role": "sales_rep",
    })
    assert response.status_code == 200, response.text
    response = client.post("/api/v1/auth/login", data={"username": "sales@example.com", "password": "Sales-Password-2026"})
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    response = client.patch("/api/v1/auth/me", json={"role": "admin", "is_superuser": True})
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "sales_rep"
    assert response.json()["is_superuser"] is False
    assert client.get("/api/v1/users").status_code == 403
    assert client.get(f"/api/v1/deals/{deal['id']}/activities").status_code == 403
    assert client.post(f"/api/v1/deals/{deal['id']}/activities", json={
        "deal_id": deal["id"], "type": "note", "description": "Unauthorized note",
    }).status_code == 403
