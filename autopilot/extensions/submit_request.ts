/**
 * submit_request: how the autopilot worker ends a session.
 *
 * The orchestrator (autopilot.py) copies this into the worker's agent dir. The tool
 * checks the request when Bonsai calls it, so a malformed one comes back as an error
 * it can fix in the same session instead of costing a round. A valid request is
 * written to $PI_CODING_AGENT_DIR/request.json and ends the session. The orchestrator
 * re-checks everything; this is only the early, fixable half of the check.
 */
import * as fs from "node:fs";
import * as path from "node:path";
import { StringEnum } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const KINDS = ["run", "infra", "continue", "done", "stuck"] as const;
const MAX_TIMEOUT_MIN = 180;

function inside(file: string, dir: string) {
	const rel = path.relative(dir, file);
	return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel);
}

function check(p: Record<string, any>): string[] {
	const errs: string[] = [];
	const need = (k: string) => {
		if (typeof p[k] !== "string" || !p[k].trim()) errs.push(`"${k}" is required for a ${p.request} request`);
	};
	const repo = process.cwd();
	switch (p.request) {
		case "run": {
			need("command");
			need("why");
			if (typeof p.gpu !== "boolean") errs.push('"gpu" is required for a run request (true or false)');
			const t = p.timeout_min;
			if (t !== undefined && !(Number.isInteger(t) && t >= 1 && t <= MAX_TIMEOUT_MIN))
				errs.push(`"timeout_min" must be a whole number from 1 to ${MAX_TIMEOUT_MIN}`);
			const cmd = typeof p.command === "string" ? p.command.trim() : "";
			if (!cmd) break;
			if (/[|;&><`$]/.test(cmd)) errs.push("command: no shell operators (| ; & > < ` $); pass plain arguments");
			const argv = cmd.split(/\s+/);
			if (argv.length < 2 || !["python3", "bash"].includes(argv[0]))
				errs.push("command must be `python3 <script> ARGS` or `bash <script> ARGS`");
			else {
				const script = path.resolve(repo, argv[1]);
				if (!inside(script, path.join(repo, "bench")) && !inside(script, path.join(repo, "evals")))
					errs.push(`script ${argv[1]} must be under bench/ or evals/`);
				else if (!fs.existsSync(script) || !fs.statSync(script).isFile())
					errs.push(`script ${argv[1]} does not exist; write it first`);
			}
			break;
		}
		case "infra": {
			need("entry");
			need("why");
			if (typeof p.entry === "string" && p.entry.trim()) {
				const entry = path.resolve(repo, p.entry);
				if (!inside(entry, path.join(repo, "serving", "candidates")))
					errs.push("entry must be a file under serving/candidates/");
				else if (!fs.existsSync(entry)) errs.push(`entry ${p.entry} does not exist; write it first`);
			}
			break;
		}
		case "continue":
			need("note");
			break;
		case "done":
			need("summary");
			break;
		case "stuck":
			need("why");
			break;
	}
	return errs;
}

const submitRequest = defineTool({
	name: "submit_request",
	label: "Submit request",
	description:
		"End this session and hand a request to the orchestrator: run a host script (run), apply a live-server " +
		"config (infra), keep going next session (continue), declare the item finished (done), or ask for help " +
		"(stuck). The request is checked now; if it is invalid you get the errors back and can call it again. " +
		"A valid call ends the session.",
	promptSnippet: "End the session with a request to the orchestrator",
	promptGuidelines: [
		"Call submit_request exactly once, as your last action, when your chunk of work is done.",
		"If submit_request returns errors, fix them and call it again.",
	],
	parameters: Type.Object({
		request: StringEnum(KINDS, { description: "What you want next" }),
		report: Type.String({ description: "Short report: what you did, what you found, what's next" }),
		command: Type.Optional(Type.String({ description: "run: `python3 bench/x.py ARGS` or `bash ...`" })),
		gpu: Type.Optional(Type.Boolean({ description: "run: true if the script needs the GPU (port 8089)" })),
		timeout_min: Type.Optional(Type.Integer({ description: `run: minutes, at most ${MAX_TIMEOUT_MIN}` })),
		entry: Type.Optional(Type.String({ description: "infra: serving/candidates/NAME.yaml" })),
		note: Type.Optional(Type.String({ description: "continue: what you will do next session" })),
		summary: Type.Optional(
			Type.String({ description: "done: how each acceptance criterion is met, with file paths" }),
		),
		why: Type.Optional(Type.String({ description: "run/infra: why; stuck: what blocks you" })),
	}),

	async execute(_id, params) {
		const errs = check(params);
		if (!params.report?.trim()) errs.unshift('"report" is required');
		if (errs.length) throw new Error(`Request not accepted:\n- ${errs.join("\n- ")}`);
		const dir = process.env.PI_CODING_AGENT_DIR;
		if (!dir) throw new Error("PI_CODING_AGENT_DIR is not set; end with a fenced json block instead");
		fs.writeFileSync(path.join(dir, "request.json"), JSON.stringify(params, null, 2) + "\n");
		return {
			content: [{ type: "text", text: `Request "${params.request}" submitted. The session ends here.` }],
			details: params,
			terminate: true,
		};
	},
});

export default function (pi: ExtensionAPI) {
	pi.registerTool(submitRequest);
}
