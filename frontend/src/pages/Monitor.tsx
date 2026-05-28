import { useEffect, useState, useRef } from 'react';
import { runsApi } from '../api';

interface MonitorEvent {
  run_id?: string;
  event_type: string;
  agent_id?: string;
  payload?: Record<string, unknown>;
  created_at?: string;
}

export default function MonitorPage() {
  const [runs, setRuns] = useState<{ id: string; status: string; workflow_id: string; output_text: string }[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [events, setEvents] = useState<unknown[]>([]);
  const [messages, setMessages] = useState<unknown[]>([]);
  const [tokens, setTokens] = useState<unknown[]>([]);
  const [liveLog, setLiveLog] = useState<MonitorEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    runsApi.list().then(setRuns);
  }, []);

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/monitor`);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data) as MonitorEvent;
      setLiveLog((prev) => [data, ...prev].slice(0, 200));
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!selectedRun) return;
    runsApi.events(selectedRun).then(setEvents);
    runsApi.messages(selectedRun).then(setMessages);
    runsApi.tokens(selectedRun).then(setTokens);
  }, [selectedRun]);

  return (
    <div>
      <h2>Live Monitor</h2>
      <div className="grid-2">
        <div className="card">
          <h3>Workflow Runs</h3>
          {runs.map((r) => (
            <div key={r.id} style={{ marginBottom: '0.5rem' }}>
              <button
                className={`btn btn-secondary ${selectedRun === r.id ? 'active' : ''}`}
                style={{ width: '100%', textAlign: 'left' }}
                onClick={() => setSelectedRun(r.id)}
              >
                {r.id.slice(0, 8)}... — {r.status}
              </button>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>Real-time feed</h3>
          <div className="log-feed">
            {liveLog.map((e, i) => (
              <div key={i} className="log-item">
                <strong>{e.event_type}</strong> {e.agent_id && `agent=${e.agent_id.slice(0, 8)}`}
                <pre style={{ margin: 0 }}>{JSON.stringify(e.payload)}</pre>
              </div>
            ))}
            {liveLog.length === 0 && <p style={{ color: 'var(--muted)' }}>Waiting for events... Run a workflow to see live updates.</p>}
          </div>
        </div>
      </div>

      {selectedRun && (
        <>
          <div className="card">
            <h3>Run Events — {selectedRun.slice(0, 8)}</h3>
            <div className="log-feed">
              {(events as { event_type: string; payload: unknown; created_at: string }[]).map((e, i) => (
                <div key={i} className="log-item">
                  [{e.created_at}] <strong>{e.event_type}</strong> {JSON.stringify(e.payload)}
                </div>
              ))}
            </div>
          </div>
          <div className="grid-2">
            <div className="card">
              <h3>Inter-agent messages</h3>
              {(messages as { sender_agent_id: string; receiver_agent_id: string; payload: string }[]).map((m, i) => (
                <div key={i} className="log-item">
                  {m.sender_agent_id.slice(0, 8)} → {m.receiver_agent_id.slice(0, 8)}: {m.payload.slice(0, 200)}
                </div>
              ))}
            </div>
            <div className="card">
              <h3>Token usage</h3>
              <table>
                <thead><tr><th>Agent</th><th>In</th><th>Out</th><th>Total</th><th>Est. $</th></tr></thead>
                <tbody>
                  {(tokens as { agent_id: string; input_tokens: number; output_tokens: number; total_tokens: number; estimated_cost_usd: number }[]).map((t, i) => (
                    <tr key={i}>
                      <td>{t.agent_id?.slice(0, 8) || '-'}</td>
                      <td>{t.input_tokens}</td>
                      <td>{t.output_tokens}</td>
                      <td>{t.total_tokens}</td>
                      <td>${t.estimated_cost_usd.toFixed(6)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
