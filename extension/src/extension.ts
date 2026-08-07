import * as vscode from "vscode";

const BASE_URL = "http://localhost:8000";
const AFFIRMATIVE = /^(go|yes|approve|go for it|looks good|lgtm)\b/i;

type Stage =
  | "planning"
  | "awaiting_plan_approval"
  | "drafting_html"
  | "awaiting_draft_approval"
  | "engineering"
  | "critiquing"
  | "running"
  | "done"
  | "failed";

interface SwarmState {
  session_id: string;
  stage: Stage;
  plan?: { rationale: string; layout_style: string; components: { name: string; purpose: string }[] };
  html_draft?: string;
  engineer_output?: { summary: string; files: { path: string; content: string }[] };
  critic_report?: { findings: { file: string; summary: string; severity: string }[]; approved: boolean };
  run_result?: { passed: boolean; log: string };
}

let current: SwarmState | undefined;

async function post(path: string, body?: unknown): Promise<SwarmState> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  return res.json() as Promise<SwarmState>;
}

async function pollUntil(sessionId: string, stages: Stage[]): Promise<SwarmState> {
  for (;;) {
    const res = await fetch(`${BASE_URL}/status/${sessionId}`);
    const state = (await res.json()) as SwarmState;
    if (stages.includes(state.stage)) return state;
    await new Promise((r) => setTimeout(r, 1500));
  }
}

function renderPlan(stream: vscode.ChatResponseStream, state: SwarmState) {
  const p = state.plan!;
  stream.markdown(`**Plan:** ${p.rationale}\n\n- Layout: ${p.layout_style}\n`);
  for (const c of p.components) stream.markdown(`- **${c.name}**: ${c.purpose}\n`);
  stream.markdown("\nReply `go` to sketch the UI, or describe changes.");
}

async function showDraftWebview(html: string) {
  const panel = vscode.window.createWebviewPanel("robinDraft", "Robin — Draft Sketch", vscode.ViewColumn.Beside, {});
  panel.webview.html = html;
}

async function applyFiles(files: { path: string; content: string }[]) {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders) throw new Error("Open a workspace folder first.");
  const root = folders[0].uri;
  const edit = new vscode.WorkspaceEdit();
  for (const f of files) {
    const uri = vscode.Uri.joinPath(root, f.path);
    edit.createFile(uri, { overwrite: true, ignoreIfExists: false });
    edit.insert(uri, new vscode.Position(0, 0), f.content);
  }
  await vscode.workspace.applyEdit(edit);
}

async function handler(
  request: vscode.ChatRequest,
  _context: vscode.ChatContext,
  stream: vscode.ChatResponseStream,
): Promise<void> {
  const affirmative = AFFIRMATIVE.test(request.prompt.trim());

  if (!current) {
    stream.progress("Planning…");
    current = await post("/run", { prompt: request.prompt });
    renderPlan(stream, current);
    return;
  }

  if (current.stage === "awaiting_plan_approval" && affirmative) {
    stream.progress("Sketching UI…");
    current = await post(`/approve-plan/${current.session_id}`);
    await showDraftWebview(current.html_draft!);
    stream.markdown("Draft opened beside this chat. Reply `go` to build it, or describe changes.");
    return;
  }

  if (current.stage === "awaiting_draft_approval" && affirmative) {
    stream.progress("Engineer building, critic reviewing, runner verifying…");
    await post(`/approve-draft/${current.session_id}`);
    current = await pollUntil(current.session_id, ["done", "failed"]);

    const critic = current.critic_report!;
    const run = current.run_result!;
    stream.markdown(`**${critic.approved ? "Passed review" : "Shipped after revisions"}.** ${current.engineer_output!.summary}\n\n`);
    if (critic.findings.length) {
      stream.markdown("Findings addressed:\n");
      for (const f of critic.findings) stream.markdown(`- [${f.severity}] ${f.file}: ${f.summary}\n`);
    }
    stream.markdown(`\n**Run check:** ${run.passed ? "✅ passed" : "❌ failed"}\n\`\`\`\n${run.log}\n\`\`\`\n`);

    if (run.passed) {
      await applyFiles(current.engineer_output!.files);
      stream.markdown("\nFiles applied — review the diff in your editor.");
    } else {
      stream.markdown("\nNot applying files until the run check passes.");
    }
    current = undefined;
    return;
  }

  // Anything else: treat as a new planning request, replacing the session.
  stream.progress("Planning…");
  current = await post("/run", { prompt: request.prompt });
  renderPlan(stream, current);
}

export function activate(context: vscode.ExtensionContext) {
  const participant = vscode.chat.createChatParticipant("swarm", handler);
  context.subscriptions.push(participant);
}

export function deactivate() {}
