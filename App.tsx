import { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  CircleSlash,
  Loader2,
  Play,
  Plug,
  RefreshCw,
  Server,
  Terminal,
  Wrench,
  XCircle,
} from 'lucide-react';
import {
  AuthError,
  fetchStatus,
  fetchTools,
  hasToken,
  invokeTool,
  setToken,
} from '@/lib/api';
import type {
  InvokeResponse,
  McpTool,
  StatusResponse,
} from '@/lib/types';

type ConnectionState = 'connecting' | 'connected' | 'disconnected';

interface InvokeState {
  loading: boolean;
  response: InvokeResponse | null;
  error: string | null;
}

export default function App() {
  const [connState, setConnState] = useState<ConnectionState>('connecting');
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const [tools, setTools] = useState<McpTool[]>([]);
  const [toolsError, setToolsError] = useState<string | null>(null);
  const [loadingTools, setLoadingTools] = useState(false);

  const [needsToken, setNeedsToken] = useState(false);

  const [nameInput, setNameInput] = useState('world');
  const [invoke, setInvoke] = useState<InvokeState>({
    loading: false,
    response: null,
    error: null,
  });

  const refreshStatus = useCallback(async () => {
    setConnState('connecting');
    setStatusError(null);
    try {
      const data = await fetchStatus();
      setStatus(data);
      setConnState(data.status === 'connected' ? 'connected' : 'disconnected');
      if (data.status !== 'connected') {
        setStatusError(data.mcp?.error ?? 'MCP server not reachable');
      }
    } catch (err) {
      if (err instanceof AuthError) setNeedsToken(true);
      setConnState('disconnected');
      setStatusError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const refreshTools = useCallback(async () => {
    setLoadingTools(true);
    setToolsError(null);
    try {
      const data = await fetchTools();
      if (!data.ok) {
        setToolsError(data.error ?? 'Failed to discover tools');
        setTools([]);
      } else {
        setTools(data.tools);
      }
    } catch (err) {
      if (err instanceof AuthError) setNeedsToken(true);
      setToolsError(err instanceof Error ? err.message : String(err));
      setTools([]);
    } finally {
      setLoadingTools(false);
    }
  }, []);

  const submitToken = useCallback(
    (value: string) => {
      setToken(value);
      setNeedsToken(false);
      refreshStatus();
      refreshTools();
    },
    [refreshStatus, refreshTools],
  );

  useEffect(() => {
    refreshStatus();
    refreshTools();
  }, [refreshStatus, refreshTools]);

  const runInvoke = useCallback(async () => {
    setInvoke({ loading: true, response: null, error: null });
    try {
      const res = await invokeTool('hello_mcp', { name: nameInput });
      setInvoke({ loading: false, response: res, error: null });
    } catch (err) {
      if (err instanceof AuthError) setNeedsToken(true);
      setInvoke({
        loading: false,
        response: null,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }, [nameInput]);

  const connected = connState === 'connected';
  const resultText =
    invoke.response?.result?.content
      .filter((c) => c.type === 'text')
      .map((c) => c.text)
      .join('\n') ?? '';

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <Header connected={connected} onRefresh={refreshStatus} />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {needsToken && (
          <TokenPanel rejected={hasToken()} onSubmit={submitToken} />
        )}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Connection status */}
          <Section
            title="Connection Status"
            icon={<Plug className="h-5 w-5" />}
            className="lg:col-span-1"
          >
            <StatusCard
              connState={connState}
              status={status}
              error={statusError}
            />
          </Section>

          {/* Server info */}
          <Section
            title="Server Information"
            icon={<Server className="h-5 w-5" />}
            className="lg:col-span-2"
          >
            <ServerInfo status={status} />
          </Section>

          {/* Tool discovery */}
          <Section
            title="Available MCP Tools"
            icon={<Wrench className="h-5 w-5" />}
            className="lg:col-span-2"
            action={
              <button
                onClick={refreshTools}
                disabled={loadingTools}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
              >
                {loadingTools ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Refresh
              </button>
            }
          >
            <ToolList tools={tools} loading={loadingTools} error={toolsError} />
          </Section>

          {/* Execution panel */}
          <Section
            title="Tool Execution"
            icon={<Terminal className="h-5 w-5" />}
            className="lg:col-span-1"
          >
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">
                  hello_mcp
                </label>
                <p className="mb-2 text-xs text-slate-500">
                  Accepts a name and returns a greeting.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    placeholder="name"
                    className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-100"
                  />
                  <button
                    onClick={runInvoke}
                    disabled={invoke.loading || !connected}
                    className="inline-flex items-center gap-1.5 rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {invoke.loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Run
                  </button>
                </div>
                {!connected && (
                  <p className="mt-2 text-xs text-warning-600">
                    Connect to the MCP server to enable execution.
                  </p>
                )}
              </div>
            </div>
          </Section>

          {/* Response panel */}
          <Section
            title="Execution Result"
            icon={<Activity className="h-5 w-5" />}
            className="lg:col-span-3"
          >
            <ResponsePanel
              loading={invoke.loading}
              response={invoke.response}
              error={invoke.error}
              resultText={resultText}
            />
          </Section>
        </div>

        <footer className="mt-10 border-t border-slate-200 pt-6 text-center text-xs text-slate-400">
          MCP Connect — prototype. Genuine MCP connectivity via Streamable HTTP.
        </footer>
      </main>
    </div>
  );
}

function TokenPanel({
  rejected,
  onSubmit,
}: {
  rejected: boolean;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState('');
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSubmit(value);
      }}
      className="mb-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-slate-800">
        Access token required
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        This backend requires an access token. It is kept for this browser tab
        only and is sent as a bearer token with each request.
      </p>
      {rejected && (
        <p className="mt-2 rounded-md bg-error-50 px-3 py-2 text-xs text-error-700">
          The token was rejected. Check it and try again.
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="access token"
          autoComplete="off"
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-primary-500 focus:ring-2 focus:ring-primary-100"
        />
        <button
          type="submit"
          disabled={!value.trim()}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Unlock
        </button>
      </div>
    </form>
  );
}

function Header({
  connected,
  onRefresh,
}: {
  connected: boolean;
  onRefresh: () => void;
}) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white">
            <Plug className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-slate-900">
              MCP Connect
            </h1>
            <p className="text-xs text-slate-500">
              Connectivity &amp; controlled execution layer
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill connected={connected} />
          <button
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
          >
            <RefreshCw className="h-4 w-4" />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>
    </header>
  );
}

function StatusPill({ connected }: { connected: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
        connected
          ? 'bg-accent-50 text-accent-700'
          : 'bg-error-50 text-error-600'
      }`}
    >
      <span
        className={`h-2 w-2 rounded-full ${
          connected ? 'bg-accent-500' : 'bg-error-500'
        }`}
      />
      {connected ? 'Connected' : 'Disconnected'}
    </span>
  );
}

function Section({
  title,
  icon,
  action,
  className = '',
  children,
}: {
  title: string;
  icon: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}
    >
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3.5">
        <div className="flex items-center gap-2 text-slate-700">
          <span className="text-primary-600">{icon}</span>
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function StatusCard({
  connState,
  status,
  error,
}: {
  connState: ConnectionState;
  status: StatusResponse | null;
  error: string | null;
}) {
  if (connState === 'connecting') {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking connection…
      </div>
    );
  }
  if (connState === 'disconnected' || !status) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-error-600">
          <XCircle className="h-5 w-5" />
          Not connected
        </div>
        {error && (
          <p className="rounded-md bg-error-50 px-3 py-2 text-xs text-error-700">
            {error}
          </p>
        )}
        <p className="text-xs text-slate-500">
          Make sure the backend (REST bridge on :8000 and MCP server on :8001)
          is running.
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-accent-700">
        <CheckCircle2 className="h-5 w-5" />
        Connected
      </div>
      <dl className="space-y-2 text-sm">
        <Row label="Protocol" value={status.mcp.protocol_version ?? '—'} />
        <Row
          label="Server"
          value={
            status.mcp.server_info
              ? `${status.mcp.server_info.name} v${status.mcp.server_info.version}`
              : '—'
          }
        />
        <Row
          label="Capabilities"
          value={(status.mcp.capabilities ?? []).join(', ') || '—'}
        />
      </dl>
    </div>
  );
}

function ServerInfo({ status }: { status: StatusResponse | null }) {
  if (!status) {
    return <p className="text-sm text-slate-400">No server data yet.</p>;
  }
  return (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      <Row label="Project" value={status.project} />
      <Row label="Server name" value={status.server_name} />
      <Row label="Server version" value={status.server_version} />
      <Row label="MCP endpoint" value={status.mcp_url} mono />
      <Row label="Uptime" value={`${status.uptime_seconds}s`} />
      <Row label="Overall status" value={status.status} />
    </dl>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd
        className={`mt-0.5 text-sm text-slate-800 ${mono ? 'font-mono text-xs' : ''}`}
      >
        {value}
      </dd>
    </div>
  );
}

function ToolList({
  tools,
  loading,
  error,
}: {
  tools: McpTool[];
  loading: boolean;
  error: string | null;
}) {
  if (loading && tools.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        Discovering tools…
      </div>
    );
  }
  if (error && tools.length === 0) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium text-error-600">
          <CircleSlash className="h-5 w-5" />
          Discovery failed
        </div>
        <p className="rounded-md bg-error-50 px-3 py-2 text-xs text-error-700">
          {error}
        </p>
      </div>
    );
  }
  if (tools.length === 0) {
    return (
      <p className="text-sm text-slate-400">No tools discovered.</p>
    );
  }
  return (
    <ul className="space-y-2">
      {tools.map((tool) => (
        <li
          key={tool.name}
          className="flex items-start gap-3 rounded-lg border border-slate-100 bg-slate-50/60 px-4 py-3"
        >
          <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" />
          <div className="min-w-0">
            <p className="font-mono text-sm font-semibold text-slate-800">
              {tool.name}
            </p>
            {tool.description && (
              <p className="mt-0.5 text-xs text-slate-500">{tool.description}</p>
            )}
            {tool.inputSchema?.properties && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(tool.inputSchema.properties).map(([key, schema]) => (
                  <span
                    key={key}
                    className="inline-flex items-center rounded bg-white px-2 py-0.5 font-mono text-xs text-slate-600 ring-1 ring-inset ring-slate-200"
                  >
                    {key}: {schema.type}
                  </span>
                ))}
              </div>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function ResponsePanel({
  loading,
  response,
  error,
  resultText,
}: {
  loading: boolean;
  response: InvokeResponse | null;
  error: string | null;
  resultText: string;
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        Invoking hello_mcp…
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-error-600">
          <XCircle className="h-5 w-5" />
          Error
        </div>
        <pre className="overflow-x-auto rounded-md bg-error-50 px-4 py-3 font-mono text-xs text-error-700">
          {error}
        </pre>
      </div>
    );
  }
  if (!response) {
    return (
      <p className="text-sm text-slate-400">
        Run the hello_mcp tool to see its response here.
      </p>
    );
  }
  const isError = response.result?.isError ?? false;
  return (
    <div className="space-y-3">
      <div
        className={`flex items-center gap-2 text-sm font-semibold ${
          isError ? 'text-warning-600' : 'text-accent-700'
        }`}
      >
        {isError ? (
          <XCircle className="h-5 w-5" />
        ) : (
          <CheckCircle2 className="h-5 w-5" />
        )}
        {isError ? 'Tool returned an error' : 'Success'}
      </div>
      <pre className="overflow-x-auto rounded-md bg-slate-900 px-4 py-3 font-mono text-sm text-slate-100">
        {resultText || JSON.stringify(response.result, null, 2)}
      </pre>
    </div>
  );
}
