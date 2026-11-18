export interface McpServerInfo {
  name: string;
  version: string;
}

export interface McpConnectionInfo {
  connected: boolean;
  protocol_version?: string;
  server_info?: McpServerInfo;
  capabilities?: string[];
  error?: string;
}

export interface StatusResponse {
  project: string;
  server_name: string;
  server_version: string;
  mcp_url: string;
  uptime_seconds: number;
  mcp: McpConnectionInfo;
  status: 'connected' | 'disconnected';
}

export interface ToolInputSchema {
  type: string;
  properties?: Record<string, { type: string; description?: string }>;
  required?: string[];
}

export interface McpTool {
  name: string;
  description: string | null;
  inputSchema: ToolInputSchema | null;
}

export interface ToolsResponse {
  ok: boolean;
  tools: McpTool[];
  error?: string;
}

export interface ContentBlock {
  type: string;
  text?: string;
}

export interface ToolResult {
  isError: boolean;
  content: ContentBlock[];
}

export interface InvokeResponse {
  ok: boolean;
  result?: ToolResult;
  error?: string;
}
