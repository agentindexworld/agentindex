#!/usr/bin/env node
// AgentIndex Remote MCP Server — Streamable HTTP transport
// Zero installation: agents connect to https://agentindex.world/mcp
import { createServer } from "http";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { TOOLS, callTool } from "./tools.js";

const PORT = parseInt(process.env.MCP_PORT || "3002");

// JSON-RPC handler
async function handleJsonRpc(body) {
  const request = JSON.parse(body);

  // Handle batch requests
  if (Array.isArray(request)) {
    return Promise.all(request.map(handleSingleRequest));
  }
  return handleSingleRequest(request);
}

async function handleSingleRequest(request) {
  const { id, method, params } = request;

  try {
    switch (method) {
      case "initialize":
        return {
          jsonrpc: "2.0",
          id,
          result: {
            protocolVersion: "2025-03-26",
            capabilities: { tools: {} },
            serverInfo: { name: "agentindex", version: "2.0.0" }
          }
        };

      case "tools/list":
        return {
          jsonrpc: "2.0",
          id,
          result: { tools: TOOLS }
        };

      case "tools/call": {
        const { name, arguments: args } = params;
        const result = await callTool(name, args);
        return { jsonrpc: "2.0", id, result };
      }

      case "ping":
        return { jsonrpc: "2.0", id, result: {} };

      case "notifications/initialized":
        return null; // notifications don't get responses

      default:
        return {
          jsonrpc: "2.0",
          id,
          error: { code: -32601, message: `Method not found: ${method}` }
        };
    }
  } catch (error) {
    return {
      jsonrpc: "2.0",
      id,
      error: { code: -32603, message: error.message }
    };
  }
}

const httpServer = createServer(async (req, res) => {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  // Health check
  if (req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      name: "agentindex-mcp",
      version: "2.0.0",
      status: "running",
      transport: "streamable-http",
      tools: TOOLS.length,
      usage: "POST JSON-RPC requests to this endpoint",
      docs: "https://agentindex.world/docs.html"
    }));
    return;
  }

  if (req.method !== "POST") {
    res.writeHead(405, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Method not allowed. Use POST with JSON-RPC." }));
    return;
  }

  // Collect body
  let body = "";
  for await (const chunk of req) body += chunk;

  try {
    const result = await handleJsonRpc(body);

    if (result === null) {
      // Notification — no response needed
      res.writeHead(204);
      res.end();
      return;
    }

    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(result));
  } catch (error) {
    res.writeHead(400, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      jsonrpc: "2.0",
      id: null,
      error: { code: -32700, message: "Parse error: " + error.message }
    }));
  }
});

httpServer.listen(PORT, "0.0.0.0", () => {
  console.log(`AgentIndex Remote MCP Server running on port ${PORT}`);
  console.log(`Endpoint: http://0.0.0.0:${PORT}/`);
  console.log(`Tools: ${TOOLS.map(t => t.name).join(", ")}`);
});
