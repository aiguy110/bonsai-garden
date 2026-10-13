// W2 addition: a small replacement for the two functions of the `diff` package this
// extension uses (diffLines, diffArrays). The extension is loaded from the agent dir,
// where `diff` does not resolve. Output shape follows jsdiff: parts of
// { value, count, added?, removed? }, a removed part before the added part of the same change.
// Not minimal on huge inputs: past MAX_CELLS the middle is one removal plus one addition.

export interface Part<T> {
	value: T;
	count: number;
	added?: boolean;
	removed?: boolean;
}

const MAX_CELLS = 4_000_000;

function diffSeq(a: string[], b: string[]): Array<{ kind: "=" | "-" | "+"; items: string[] }> {
	let lo = 0;
	while (lo < a.length && lo < b.length && a[lo] === b[lo]) lo++;
	let ea = a.length;
	let eb = b.length;
	while (ea > lo && eb > lo && a[ea - 1] === b[eb - 1]) {
		ea--;
		eb--;
	}
	const ops: Array<{ kind: "=" | "-" | "+"; items: string[] }> = [];
	const push = (kind: "=" | "-" | "+", items: string[]) => {
		if (items.length === 0) return;
		const last = ops[ops.length - 1];
		if (last && last.kind === kind) last.items.push(...items);
		else ops.push({ kind, items: [...items] });
	};
	push("=", a.slice(0, lo));
	const am = a.slice(lo, ea);
	const bm = b.slice(lo, eb);
	const n = am.length;
	const m = bm.length;
	if (n === 0 || m === 0 || (n + 1) * (m + 1) > MAX_CELLS) {
		push("-", am);
		push("+", bm);
	} else {
		const w = m + 1;
		const t = new Uint32Array((n + 1) * w); // t[i*w+j] = LCS length of am[i..], bm[j..]
		for (let i = n - 1; i >= 0; i--)
			for (let j = m - 1; j >= 0; j--)
				t[i * w + j] =
					am[i] === bm[j] ? t[(i + 1) * w + j + 1]! + 1 : Math.max(t[(i + 1) * w + j]!, t[i * w + j + 1]!);
		let i = 0;
		let j = 0;
		const rem: string[] = [];
		const add: string[] = [];
		const flush = () => {
			push("-", rem.splice(0));
			push("+", add.splice(0));
		};
		while (i < n || j < m) {
			if (i < n && j < m && am[i] === bm[j]) {
				flush();
				push("=", [am[i]!]);
				i++;
				j++;
			} else if (j >= m || (i < n && t[(i + 1) * w + j]! >= t[i * w + j + 1]!)) {
				rem.push(am[i++]!);
			} else {
				add.push(bm[j++]!);
			}
		}
		flush();
	}
	push("=", a.slice(ea));
	return ops;
}

export function diffArrays(a: string[], b: string[]): Array<Part<string[]>> {
	return diffSeq(a, b).map((o) => ({
		value: o.items,
		count: o.items.length,
		...(o.kind === "+" ? { added: true } : {}),
		...(o.kind === "-" ? { removed: true } : {}),
	}));
}

function lineTokens(s: string): string[] {
	return s.match(/[^\n]*\n|[^\n]+$/g) ?? [];
}

export function diffLines(a: string, b: string): Array<Part<string>> {
	return diffSeq(lineTokens(a), lineTokens(b)).map((o) => ({
		value: o.items.join(""),
		count: o.items.length,
		...(o.kind === "+" ? { added: true } : {}),
		...(o.kind === "-" ? { removed: true } : {}),
	}));
}
