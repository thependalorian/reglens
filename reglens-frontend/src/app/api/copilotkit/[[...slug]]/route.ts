import {
  CopilotRuntime,
  createCopilotEndpoint,
  InMemoryAgentRunner,
} from "@copilotkit/runtime/v2";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { handle } from "hono/vercel";

// Self-hosted: broker straight to the RegLens FastAPI AG-UI endpoint.
// No managed Intelligence gateway — corpus and conversation traffic stays
// between this Next.js runtime, the FastAPI backend, and Neon.
const AGENT_URL = process.env.AGENT_URL || "http://localhost:8058";
const token = process.env.REGLENS_API_TOKEN || "";

const reglensAgent = new LangGraphHttpAgent({
  url: `${AGENT_URL}/agui`,
  headers: token ? { Authorization: `Bearer ${token}` } : {},
});

const runtime = new CopilotRuntime({
  agents: { default: reglensAgent },
  runner: new InMemoryAgentRunner(),
  openGenerativeUI: true,
  a2ui: {
    injectA2UITool: false,
  },
});

const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

export const GET = handle(app);
export const POST = handle(app);
export const PATCH = handle(app);
export const DELETE = handle(app);
