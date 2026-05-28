def test_create_and_update_agent(client):
    r = client.post("/api/agents", json={
        "name": "TestAgent",
        "role": "test",
        "system_prompt": "Test prompt",
        "model": "grok-4.1-fast",
        "tools": ["calculator"],
        "skills": ["testing"],
    })
    assert r.status_code == 201
    agent = r.json()
    assert agent["name"] == "TestAgent"
    assert "calculator" in agent["tools"]

    r2 = client.put(f"/api/agents/{agent['id']}", json={"name": "UpdatedAgent"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "UpdatedAgent"

    r3 = client.get(f"/api/agents/{agent['id']}")
    assert r3.status_code == 200

    r4 = client.delete(f"/api/agents/{agent['id']}")
    assert r4.status_code == 204


def test_list_agents_includes_seed(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "Researcher" in names
