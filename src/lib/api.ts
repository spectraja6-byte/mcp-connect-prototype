import type {
  StatusResponse,
  ToolsResponse,
  InvokeResponse,
} from './types';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const contentType = res.headers.get('content-type') ?? '';

  if (!contentType.includes('application/json')) {
    if (!res.ok) {
      throw new Error(`Backend unreachable (HTTP ${res.status}). The MCP Connect backend is not running.`);
    }
    throw new Error('Backend returned a non-JSON response. The MCP Connect backend is not running.');
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.error) detail = body.error;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export function fetchStatus(): Promise<StatusResponse> {
  return request<StatusResponse>('/api/status');
}

export function fetchTools(): Promise<ToolsResponse> {
  return request<ToolsResponse>('/api/tools');
}

export function invokeTool(
  name: string,
  args: Record<string, unknown>,
): Promise<InvokeResponse> {
  return request<InvokeResponse>('/api/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, arguments: args }),
  });
}

export async function fetchHealth(): Promise<boolean> {
  try {
    const res = await fetch('/health');
    return res.ok;
  } catch {
    return false;
  }
}
