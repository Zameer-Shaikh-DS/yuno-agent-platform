import { useCallback, useEffect, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { agentsApi, workflowsApi, runsApi, type Agent, type Workflow } from '../api';

const nodeTypes = ['agent', 'condition', 'end'];

function toFlowNodes(defNodes: unknown[], agents: Agent[]): Node[] {
  return (defNodes as { id: string; type: string; position: { x: number; y: number }; data: Record<string, unknown> }[]).map((n) => ({
    id: n.id,
    type: 'default',
    position: n.position || { x: 0, y: 0 },
    data: {
      label: n.type === 'agent'
        ? `${n.data?.label || 'Agent'}: ${agents.find((a) => a.id === n.data?.agentId)?.name || n.data?.agentId || '?'}`
        : `${n.type}: ${n.data?.label || n.id}`,
      ...n.data,
      nodeType: n.type,
    },
  }));
}

function toFlowEdges(defEdges: unknown[]): Edge[] {
  return (defEdges as { id: string; source: string; target: string; label?: string }[]).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
  }));
}

function fromFlow(nodes: Node[], edges: Edge[]) {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: (n.data as { nodeType?: string }).nodeType || 'agent',
      position: n.position,
      data: n.data,
    })),
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, label: e.label })),
  };
}

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [runInput, setRunInput] = useState('');
  const [runResult, setRunResult] = useState('');

  const load = () => workflowsApi.list().then(setWorkflows);
  useEffect(() => {
    load();
    agentsApi.list().then(setAgents);
  }, []);

  const selectWorkflow = (wf: Workflow) => {
    setSelected(wf);
    setNodes(toFlowNodes(wf.definition.nodes, agents));
    setEdges(toFlowEdges(wf.definition.edges));
    setRunResult('');
  };

  const onConnect = useCallback((c: Connection) => setEdges((eds) => addEdge(c, eds)), [setEdges]);

  const save = async () => {
    if (!selected) return;
    const definition = fromFlow(nodes, edges);
    await workflowsApi.update(selected.id, { definition });
    load();
    alert('Workflow saved');
  };

  const addNode = (type: string) => {
    const id = `n${Date.now()}`;
    const agentId = agents[0]?.id;
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: 'default',
        position: { x: 100 + nds.length * 50, y: 100 },
        data: {
          label: type,
          nodeType: type,
          agentId: type === 'agent' ? agentId : undefined,
        },
      },
    ]);
  };

  const run = async () => {
    if (!selected) return;
    setRunResult('Running...');
    try {
      const run = await runsApi.execute(selected.id, runInput);
      setRunResult(run.output_text || run.status);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: string } }; message?: string };
      const detail = ax.response?.data?.detail || ax.message || String(e);
      setRunResult(`Error: ${detail}`);
    }
  };

  return (
    <div>
      <h2>Workflows</h2>
      <div className="grid-2">
        <div className="card">
          <h3>Templates & Workflows</h3>
          {workflows.map((wf) => (
            <div key={wf.id} style={{ marginBottom: '0.5rem' }}>
              <button className="btn btn-secondary" style={{ width: '100%', textAlign: 'left' }} onClick={() => selectWorkflow(wf)}>
                {wf.name} {wf.is_template && <span className="badge">template</span>}
              </button>
            </div>
          ))}
        </div>

        <div className="card">
          {selected ? (
            <>
              <h3>{selected.name}</h3>
              <p style={{ color: 'var(--muted)' }}>{selected.description}</p>
              <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {nodeTypes.map((t) => (
                  <button key={t} className="btn btn-secondary" onClick={() => addNode(t)}>+ {t}</button>
                ))}
                <button className="btn" onClick={save}>Save</button>
              </div>
              <div className="workflow-canvas">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={(_evt, node) => setSelectedNode(node)}
                  fitView
                >
                  <Background />
                  <Controls />
                  <MiniMap />
                </ReactFlow>
              </div>
              {selectedNode && selectedNode.data.nodeType === 'condition' && (
                <div className="card" style={{ marginTop: '1rem' }}>
                  <h4>Condition: {String(selectedNode.data.label || selectedNode.id)}</h4>
                  <label>Condition expression</label>
                  <input
                    value={String((selectedNode.data as Record<string, unknown>).condition || 'always')}
                    onChange={(e) => {
                      const val = e.target.value;
                      setSelectedNode((n) => n ? { ...n, data: { ...n.data, condition: val } } : n);
                      setNodes((nds) =>
                        nds.map((n) =>
                          n.id === selectedNode.id ? { ...n, data: { ...n.data, condition: val } } : n
                        )
                      );
                    }}
                    placeholder="always | never | contains:urgent"
                  />
                  <p style={{ fontSize: '12px', color: 'var(--text-muted, #888)', margin: '4px 0 0' }}>
                    Examples: always · never · contains:urgent · contains:approved
                  </p>
                </div>
              )}
              <label style={{ marginTop: '1rem' }}>Run input</label>
              <textarea rows={2} value={runInput} onChange={(e) => setRunInput(e.target.value)} placeholder="Enter task for workflow..." />
              <button className="btn" onClick={run}>Run Workflow</button>
              {runResult && <pre style={{ marginTop: '1rem', whiteSpace: 'pre-wrap' }}>{runResult}</pre>}
            </>
          ) : (
            <p>Select a workflow to edit and run.</p>
          )}
        </div>
      </div>
    </div>
  );
}
