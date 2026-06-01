import { useEffect, useState } from 'react';
import { agentsApi, toolsApi, type Agent } from '../api';

const TABS = ['Basics', 'Tools', 'Memory', 'Schedule', 'Guardrails', 'Channels'] as const;

const emptyAgent: Partial<Agent> = {
  name: '',
  role: 'assistant',
  system_prompt: 'You are a helpful AI agent.',
  model: 'llama-3.3-70b-versatile',
  tools: [],
  channels: { telegram: { enabled: false } },
  schedule: { cron: '', timezone: 'UTC', enabled: false },
  memory: { window: 10, summary: '' },
  skills: [],
  interaction_rules: { handoff_format: 'text' },
  guardrails: { max_iterations: 8, blocked_topics: [] },
  is_gateway: false,
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [availableTools, setAvailableTools] = useState<string[]>([]);
  const [editing, setEditing] = useState<Partial<Agent> | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>('Basics');

  const load = () => agentsApi.list().then(setAgents);
  useEffect(() => {
    load();
    toolsApi.list().then(setAvailableTools);
  }, []);

  const save = async () => {
    if (!editing?.name) return;
    if (editing.id) await agentsApi.update(editing.id, editing);
    else await agentsApi.create(editing);
    setEditing(null);
    load();
  };

  const remove = async (id: string) => {
    if (!confirm('Delete agent?')) return;
    await agentsApi.delete(id);
    load();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Agents</h2>
        <button className="btn" onClick={() => setEditing({ ...emptyAgent })}>+ New Agent</button>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Model</th>
              <th>Tools</th>
              <th>Gateway</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td>{a.role}</td>
                <td><span className="badge">{a.model}</span></td>
                <td>{(a.tools || []).join(', ')}</td>
                <td>{a.is_gateway ? 'Yes' : '-'}</td>
                <td>
                  <button className="btn btn-secondary" onClick={() => setEditing(a)}>Edit</button>{' '}
                  <button className="btn btn-danger" onClick={() => remove(a.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="card">
          <h3>{editing.id ? 'Edit Agent' : 'New Agent'}</h3>
          <div className="tabs">
            {TABS.map((t) => (
              <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>

          {tab === 'Basics' && (
            <>
              <label>Name</label>
              <input value={editing.name || ''} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              <label>Role</label>
              <input value={editing.role || ''} onChange={(e) => setEditing({ ...editing, role: e.target.value })} />
              <label>Model</label>
              <select value={editing.model || 'llama-3.3-70b-versatile'} onChange={(e) => setEditing({ ...editing, model: e.target.value })}>
                <optgroup label="Groq (free tier, gsk_ key)">
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile</option>
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant</option>
                </optgroup>
                <optgroup label="xAI Grok (xai- key)">
                  <option value="grok-3-mini">grok-3-mini</option>
                  <option value="grok-3">grok-3</option>
                </optgroup>
              </select>
              <label>System Prompt</label>
              <textarea rows={4} value={editing.system_prompt || ''} onChange={(e) => setEditing({ ...editing, system_prompt: e.target.value })} />
              <label>Skills (comma-separated)</label>
              <input value={(editing.skills || []).join(', ')} onChange={(e) => setEditing({ ...editing, skills: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
              <label><input type="checkbox" checked={!!editing.is_gateway} onChange={(e) => setEditing({ ...editing, is_gateway: e.target.checked })} /> Telegram gateway agent</label>
            </>
          )}

          {tab === 'Tools' && (
            <>
              <p style={{ color: 'var(--muted)' }}>Select tools this agent can use:</p>
              {availableTools.map((t) => (
                <label key={t} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    checked={(editing.tools || []).includes(t)}
                    onChange={(e) => {
                      const tools = editing.tools || [];
                      setEditing({
                        ...editing,
                        tools: e.target.checked ? [...tools, t] : tools.filter((x) => x !== t),
                      });
                    }}
                  />
                  {t}
                </label>
              ))}
            </>
          )}

          {tab === 'Memory' && (
            <>
              <label>Context window (messages)</label>
              <input type="number" value={(editing.memory as { window?: number })?.window ?? 10} onChange={(e) => setEditing({ ...editing, memory: { ...editing.memory, window: +e.target.value } })} />
              <label>Memory summary</label>
              <textarea rows={3} value={(editing.memory as { summary?: string })?.summary || ''} onChange={(e) => setEditing({ ...editing, memory: { ...editing.memory, summary: e.target.value } })} />
            </>
          )}

          {tab === 'Schedule' && (
            <>
              <label><input type="checkbox" checked={!!(editing.schedule as { enabled?: boolean })?.enabled} onChange={(e) => setEditing({ ...editing, schedule: { ...editing.schedule, enabled: e.target.checked } })} /> Enable schedule (backend APScheduler runs cron jobs)</label>
              <label>Cron expression</label>
              <input value={(editing.schedule as { cron?: string })?.cron || ''} onChange={(e) => setEditing({ ...editing, schedule: { ...editing.schedule, cron: e.target.value } })} placeholder="0 9 * * *" />
              <label>Timezone</label>
              <input value={(editing.schedule as { timezone?: string })?.timezone || 'UTC'} onChange={(e) => setEditing({ ...editing, schedule: { ...editing.schedule, timezone: e.target.value } })} />
              <label>Scheduled prompt</label>
              <textarea rows={2} value={(editing.schedule as { input_template?: string })?.input_template || ''} onChange={(e) => setEditing({ ...editing, schedule: { ...editing.schedule, input_template: e.target.value } })} placeholder="Message sent to agent on each scheduled run" />
              <p style={{ fontSize: '12px', color: 'var(--muted)' }}>After save, check GET /api/scheduler/jobs for next run time.</p>
            </>
          )}

          {tab === 'Guardrails' && (
            <>
              <label>Max ReAct iterations</label>
              <input type="number" value={(editing.guardrails as { max_iterations?: number })?.max_iterations ?? 8} onChange={(e) => setEditing({ ...editing, guardrails: { ...editing.guardrails, max_iterations: +e.target.value } })} />
              <label>Blocked topics (comma-separated)</label>
              <input value={((editing.guardrails as { blocked_topics?: string[] })?.blocked_topics || []).join(', ')} onChange={(e) => setEditing({ ...editing, guardrails: { ...editing.guardrails, blocked_topics: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) } })} />
            </>
          )}

          {tab === 'Channels' && (
            <>
              <label><input type="checkbox" checked={!!(editing.channels as { telegram?: { enabled?: boolean } })?.telegram?.enabled} onChange={(e) => setEditing({ ...editing, channels: { telegram: { enabled: e.target.checked } } })} /> Enable Telegram for this agent</label>
            </>
          )}

          <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
            <button className="btn" onClick={save}>Save</button>
            <button className="btn btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
