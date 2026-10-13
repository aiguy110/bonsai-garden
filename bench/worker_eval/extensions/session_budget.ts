/**
 * session_budget (W2 w2-session-budget): warnings, then only submit_request allowed.
 * Parameters (<agent>/w2-config.json -> session_budget): limit_min (the arm's real session limit),
 * warn_min [12,16], warn_turns [30,40], block_min 17.5, block_turn 45.
 * A warning is appended to the next tool result once its threshold is crossed. From the block
 * threshold on, every tool call except submit_request is blocked with a message. Actions go to
 * <agent>/w2-ext.jsonl: {"ext":"session_budget","event":"warn"|"block",...}.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const dir = process.env.PI_CODING_AGENT_DIR ?? ".";
const cfg = (() => {
	try {
		return JSON.parse(fs.readFileSync(path.join(dir, "w2-config.json"), "utf8")).session_budget ?? {};
	} catch {
		return {};
	}
})();
const LIMIT: number = cfg.limit_min ?? 20;
const WARN_MIN: number[] = cfg.warn_min ?? [12, 16];
const WARN_TURNS: number[] = cfg.warn_turns ?? [30, 40];
const BLOCK_MIN: number = cfg.block_min ?? 17.5;
const BLOCK_TURN: number = cfg.block_turn ?? 45;
const T0 = Date.now();
const log = (o: Record<string, unknown>) =>
	fs.appendFileSync(path.join(dir, "w2-ext.jsonl"), JSON.stringify({ ext: "session_budget", t: Date.now(), ...o }) + "\n");

export default function (pi: ExtensionAPI) {
	let turn = 0;
	const fired = new Set<string>();
	const pending: string[] = [];
	const elapsed = () => (Date.now() - T0) / 60000;

	pi.on("turn_start", () => {
		turn++;
		const e = elapsed();
		const crossed: Array<[string, number, string]> = [
			...WARN_MIN.map((m): [string, number, string] => [`min${m}`, m, "time"]),
			...WARN_TURNS.map((n): [string, number, string] => [`turn${n}`, n, "turns"]),
		];
		for (const [key, thr, kind] of crossed) {
			if (fired.has(key) || (kind === "time" ? e < thr : turn < thr)) continue;
			fired.add(key);
			const text = `[Session budget] ${e.toFixed(1)} of ${LIMIT} minutes used, ${Math.max(0, LIMIT - e).toFixed(1)} left; this is turn ${turn}. ` +
				`The session is killed at ${LIMIT} minutes with nothing submitted. Wrap up and call submit_request ` +
				`(use "continue" with a note if the work is unfinished).`;
			pending.push(text);
			log({ event: "warn", kind, threshold: thr, elapsed_min: +e.toFixed(2), turn });
		}
	});

	pi.on("tool_call", (event: any) => {
		const e = elapsed();
		if (event.toolName === "submit_request" || (e < BLOCK_MIN && turn < BLOCK_TURN)) return undefined;
		log({ event: "block", tool: event.toolName, elapsed_min: +e.toFixed(2), turn });
		return {
			block: true,
			reason: `[Session budget] ${e.toFixed(1)} of ${LIMIT} minutes used (turn ${turn}). Only submit_request is allowed now: call it immediately ` +
				`(request "continue" with a note on what remains if you are not done).`,
		};
	});

	pi.on("tool_result", (event: any) => {
		if (pending.length === 0) return undefined;
		const text = pending.splice(0).join("\n");
		return { content: [...(event.content ?? []), { type: "text", text: "\n" + text }] };
	});
}
