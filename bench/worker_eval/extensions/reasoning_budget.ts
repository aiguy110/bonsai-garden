/**
 * reasoning_budget (W2 w2-reasoning-budget): adds llama-server's per-request reasoning budget
 * fields to every chat-completions payload (before_provider_request). Parameters:
 * <agent>/w2-config.json -> reasoning_budget.{tokens,message}. Server side: llama.cpp-bonsai2
 * tools/server/server-common.cpp:1354-1364. One line per request goes to <agent>/w2-ext.jsonl.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const dir = process.env.PI_CODING_AGENT_DIR ?? ".";
const cfg = (() => {
	try {
		return JSON.parse(fs.readFileSync(path.join(dir, "w2-config.json"), "utf8")).reasoning_budget ?? {};
	} catch {
		return {};
	}
})();
const TOKENS = Number.isInteger(cfg.tokens) ? cfg.tokens : 1024;
const MESSAGE: string = typeof cfg.message === "string" ? cfg.message : "\n[Thinking budget reached. Stop thinking and act now with what you have.]\n";
const log = (o: Record<string, unknown>) =>
	fs.appendFileSync(path.join(dir, "w2-ext.jsonl"), JSON.stringify({ ext: "reasoning_budget", t: Date.now(), ...o }) + "\n");

export default function (pi: ExtensionAPI) {
	let request = 0;
	pi.on("before_provider_request", (event: any) => {
		request++;
		const payload = event.payload;
		if (!payload || typeof payload !== "object") return undefined;
		const next = { ...payload, reasoning_budget_tokens: TOKENS, reasoning_budget_message: MESSAGE };
		log({ event: "request", request, fields: ["reasoning_budget_tokens", "reasoning_budget_message"], tokens: TOKENS, max_tokens: payload.max_tokens ?? null, messages: Array.isArray(payload.messages) ? payload.messages.length : null });
		return next;
	});
}
