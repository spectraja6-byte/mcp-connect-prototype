
import type {
  StatusResponse,
  ToolsResponse,
  InvokeResponse,
} from './types';

const TOKEN_KEY = 'mcp-connect-token';

/** Thrown when the backend answers 401: a (valid) access token is required. */
export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthError';
  }
}
function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage unavailable: token then lives in memory only
  }
}

let token: string | null = readStoredToken();

export function hasToken(): boolean {
  return token !== null;
}
/**
 * Remember the access token for this browser tab only (sessionStorage, cleared
 * when the tab closes). Pass an empty value to forget it.
 */
export function setToken(value: string): void {
  const cleaned = value.trim();
  token = cleaned === '' ? null : cleaned;
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: keep in memory only */
  }
}
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(url, { ...init, headers });

  if (res.status === 401) {
    throw new AuthError(
      token
        ? 'The access token was rejected. Enter the correct token.'
        : 'An access token is required.',
    );
  }

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

