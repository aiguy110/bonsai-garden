/**
 * tool_audit (W2 w2-hashline instrumentation): at the first turn, appends the session's tool list
 * (name, plus whatever source metadata pi reports) to <agent>/w2-ext.jsonl, so a smoke run can show that an
 * extension's edit/read replaced the built-ins. It changes nothing in the session.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const dir = process.env.PI_CODING_AGENT_DIR ?? ".";

export default function (pi: ExtensionAPI) {
	let done = false;
	pi.on("turn_start", () => {
		if (done) return;
		done = true;
		const all: any[] = (pi as any).getAllTools?.() ?? [];
		const active: string[] = (pi as any).getActiveTools?.() ?? [];
		const tools = all.map((t) => ({
			name: t.name,
			source: t.sourceInfo ?? t.source ?? t.extensionPath ?? null,
			description_head: String(t.description ?? "").slice(0, 80),
		}));
		fs.appendFileSync(path.join(dir, "w2-ext.jsonl"), JSON.stringify({ ext: "tool_audit", t: Date.now(), event: "tools", active, tools }) + "\n");
	});
}
