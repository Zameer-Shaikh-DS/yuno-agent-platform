import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export interface Agent {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string[];
  channels: Record<string, unknown>;
  schedule: Record<string, unknown>;
  memory: Record<string, unknown>;
  skills: string[];
  interaction_rules: Record<string, unknown>;
  guardrails: Record<string, unknown>;
  is_gateway: boolean;
  created_at: string;
  updated_at: string;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  definition: { nodes: unknown[]; edges: unknown[] };
  is_template: boolean;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: string;
  input_text: string;
  output_text: string;
}

export const agentsApi = {
  list: () => api.get<Agent[]>('/agents').then((r) => r.data),
  get: (id: string) => api.get<Agent>(`/agents/${id}`).then((r) => r.data),
  create: (data: Partial<Agent>) => api.post<Agent>('/agents', data).then((r) => r.data),
  update: (id: string, data: Partial<Agent>) => api.put<Agent>(`/agents/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/agents/${id}`),
};

export const workflowsApi = {
  list: (templatesOnly = false) =>
    api.get<Workflow[]>('/workflows', { params: { templates_only: templatesOnly } }).then((r) => r.data),
  get: (id: string) => api.get<Workflow>(`/workflows/${id}`).then((r) => r.data),
  create: (data: Partial<Workflow>) => api.post<Workflow>('/workflows', data).then((r) => r.data),
  update: (id: string, data: Partial<Workflow>) => api.put<Workflow>(`/workflows/${id}`, data).then((r) => r.data),
  delete: (id: string) => api.delete(`/workflows/${id}`),
};

export const runsApi = {
  list: () => api.get<WorkflowRun[]>('/runs').then((r) => r.data),
  execute: (workflowId: string, input_text: string) =>
    api.post<WorkflowRun>(`/runs/workflow/${workflowId}/execute`, { input_text }).then((r) => r.data),
  events: (runId: string) => api.get(`/runs/${runId}/events`).then((r) => r.data),
  messages: (runId: string) => api.get(`/runs/${runId}/messages`).then((r) => r.data),
  tokens: (runId: string) => api.get(`/runs/${runId}/tokens`).then((r) => r.data),
};

export const toolsApi = {
  list: () => api.get<{ tools: string[] }>('/tools').then((r) => r.data.tools),
};
