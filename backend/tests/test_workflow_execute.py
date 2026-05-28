def test_execute_research_writer_template(client):
    workflows = client.get("/api/workflows", params={"templates_only": True}).json()
    wf = next((w for w in workflows if "Research" in w["name"]), None)
    assert wf is not None

    r = client.post(
        f"/api/runs/workflow/{wf['id']}/execute",
        json={"input_text": "What are multi-agent AI systems?"},
    )
    assert r.status_code == 200
    run = r.json()
    assert run["status"] == "completed"
    assert len(run["output_text"]) > 0

    events = client.get(f"/api/runs/{run['id']}/events").json()
    assert any(e["event_type"] == "run_completed" for e in events)

    messages = client.get(f"/api/runs/{run['id']}/messages").json()
    assert len(messages) >= 1

    tokens = client.get(f"/api/runs/{run['id']}/tokens").json()
    assert len(tokens) >= 1
