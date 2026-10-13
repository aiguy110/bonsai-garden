import { open as fsOpen, stat as fsStat } from "fs/promises";

// W2 patch: the `file-type` dependency is replaced by a magic-byte check for the four
// image types this file already knew about. Other binary formats are still caught by the
// null-byte check below; they are described as "binary" without a MIME type.
function sniffMimeType(b: Uint8Array): string | undefined {
	const at = (i: number, ...v: number[]) => v.every((x, k) => b[i + k] === x);
	if (at(0, 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) return "image/png";
	if (at(0, 0xff, 0xd8, 0xff)) return "image/jpeg";
	if (at(0, 0x47, 0x49, 0x46, 0x38)) return "image/gif";
	if (at(0, 0x52, 0x49, 0x46, 0x46) && at(8, 0x57, 0x45, 0x42, 0x50)) return "image/webp";
	return undefined;
}

const IMAGE_MIME_TYPES = new Set<string>([
	"image/jpeg",
	"image/png",
	"image/gif",
	"image/webp",
]);

const TEXT_LIKE_MIME_TYPES = new Set<string>([
	"application/rtf",
	"application/xml",
	"application/x-ms-regedit",
]);

function isTextLikeMimeType(mimeType: string): boolean {
	return mimeType.startsWith("text/") || TEXT_LIKE_MIME_TYPES.has(mimeType);
}

const FILE_TYPE_SNIFF_BYTES = 8192;

export type LoadedFile =
	| { kind: "directory" }
	| { kind: "image"; mimeType: string }
	| { kind: "text"; text: string; hadUtf8DecodeErrors?: true }
	| { kind: "binary"; description: string };

function hasNullByte(buffer: Uint8Array): boolean {
	return buffer.includes(0);
}

export async function loadFileKindAndText(
	filePath: string,
): Promise<LoadedFile> {
	const pathStat = await fsStat(filePath);
	if (pathStat.isDirectory()) {
		return { kind: "directory" };
	}
	if (!pathStat.isFile()) {
		return {
			kind: "binary",
			description: "unsupported file type",
		};
	}

	const fileHandle = await fsOpen(filePath, "r");
	try {
		const buffer = Buffer.alloc(FILE_TYPE_SNIFF_BYTES);
		const { bytesRead } = await fileHandle.read(
			buffer,
			0,
			FILE_TYPE_SNIFF_BYTES,
			0,
		);
		if (bytesRead === 0) {
			return { kind: "text", text: "" };
		}

		const sample = buffer.subarray(0, bytesRead);
		const detectedMimeType = sniffMimeType(sample);
		if (
			detectedMimeType !== undefined &&
			!isTextLikeMimeType(detectedMimeType)
		) {
			if (IMAGE_MIME_TYPES.has(detectedMimeType)) {
				return { kind: "image", mimeType: detectedMimeType };
			}
			return {
				kind: "binary",
				description: detectedMimeType,
			};
		}
		if (hasNullByte(sample)) {
			return {
				kind: "binary",
				description: "null bytes detected",
			};
		}

		// Non-fatal decode, matching pi's built-in tools: invalid UTF-8 becomes
		// U+FFFD rather than rejecting the file. The null-byte guard above is the
		// only signal we treat as binary, so non-UTF-8 text (CP1251, GBK, …) reads
		// instead of forcing the model to bypass hashline with raw shell edits.
		// Track fatal-decoder failures separately so a literal, valid U+FFFD in a
		// UTF-8 file does not get mistaken for lossy decoding.
		const decoder = new TextDecoder("utf-8");
		const fatalDecoder = new TextDecoder("utf-8", { fatal: true });
		let hadUtf8DecodeErrors = false;
		const noteUtf8DecodeErrors = (chunk?: Uint8Array): void => {
			if (hadUtf8DecodeErrors) return;
			try {
				fatalDecoder.decode(chunk, { stream: chunk !== undefined });
			} catch (error: unknown) {
				if (error instanceof TypeError) {
					hadUtf8DecodeErrors = true;
					return;
				}
				throw error;
			}
		};

		noteUtf8DecodeErrors(sample);
		const parts: string[] = [decoder.decode(sample, { stream: true })];

		let position = bytesRead;
		while (true) {
			const { bytesRead: chunkBytesRead } = await fileHandle.read(
				buffer,
				0,
				FILE_TYPE_SNIFF_BYTES,
				position,
			);
			if (chunkBytesRead === 0) {
				break;
			}

			const chunk = buffer.subarray(0, chunkBytesRead);
			if (hasNullByte(chunk)) {
				return {
					kind: "binary",
					description: "null bytes detected",
				};
			}
			noteUtf8DecodeErrors(chunk);
			parts.push(decoder.decode(chunk, { stream: true }));
			position += chunkBytesRead;
		}

		noteUtf8DecodeErrors();
		parts.push(decoder.decode());

		return {
			kind: "text",
			text: parts.join(""),
			...(hadUtf8DecodeErrors ? { hadUtf8DecodeErrors: true as const } : {}),
		};
	} finally {
		await fileHandle.close();
	}
}
