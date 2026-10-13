/**
 * drop_old_thinking (W2 w2-think-drop): before each model request, remove thinking blocks
 * from every assistant message except the last `keep_last`. Only the outgoing context is
 * changed; the session keeps them. Parameters: <agent>/w2-config.json -> drop_old_thinking.keep_last.
 * One line per request that removed something is appended to <agent>/w2-ext.jsonl.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const dir = process.env.PI_CODING_AGENT_DIR ?? ".";
const cfg = (() => {
	try {
		return JSON.parse(fs.readFileSync(path.join(dir, "w2-config.json"), "utf8")).drop_old_thinking ?? {};
	} catch {
		return {};
	}
})();
const KEEP = Number.isInteger(cfg.keep_last) ? cfg.keep_last : 2;
const log = (o: Record<string, unknown>) =>
	fs.appendFileSync(path.join(dir, "w2-ext.jsonl"), JSON.stringify({ ext: "drop_old_thinking", t: Date.now(), ...o }) + "\n");

export default function (pi: ExtensionAPI) {
	let request = 0;
	pi.on("context", async (event: any) => {
		request++;
		const msgs: any[] = event.messages;
		const asst = msgs.map((m, i) => (m.role === "assistant" ? i : -1)).filter((i) => i >= 0);
		const old = new Set(asst.slice(0, Math.max(0, asst.length - KEEP)));
		let blocks = 0;
		let chars = 0;
		let keptEmpty = 0;
		const out = msgs.map((m, i) => {
			if (!old.has(i) || !Array.isArray(m.content)) return m;
			const kept = m.content.filter((b: any) => b?.type !== "thinking");
			const dropped = m.content.filter((b: any) => b?.type === "thinking");
			if (dropped.length === 0) return m;
			if (kept.length === 0) {
				keptEmpty++; // never send an assistant message with no content
				return m;
			}
			blocks += dropped.length;
			chars += dropped.reduce((n: number, b: any) => n + String(b.thinking ?? b.text ?? "").length, 0);
			return { ...m, content: kept };
		});
		log({ event: "request", request, assistant_messages: asst.length, keep_last: KEEP, removed_blocks: blocks, removed_chars: chars, kept_empty: keptEmpty });
		return blocks > 0 ? { messages: out } : undefined;
	});
}
