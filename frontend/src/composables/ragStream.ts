export type RagStep = { stage: string; message: string };

export type RagDone = {
  references: Array<Record<string, unknown>>;
  refused: boolean;
  route: string;
};

export function pushRagStep(steps: RagStep[], step: RagStep): RagStep[] {
  const last = steps[steps.length - 1];
  if (last && last.message === step.message) return steps;
  return [...steps, step];
}

export function refLabel(r: Record<string, unknown>): string {
  const code = r.code != null ? String(r.code) : "";
  const title = r.title != null ? String(r.title) : "简牍";
  return code ? `${code}　${title}` : title;
}

export function refQuote(r: Record<string, unknown>): string {
  const trans = String(r.transcription || r.snippet || "").trim();
  const vern = String(r.vernacular || "").trim();
  if (trans && vern && vern !== trans) return `释文\n${trans}\n\n白话\n${vern}`;
  return trans || vern || "（这条材料没有释文）";
}

export async function readRagEventStream(
  res: Response,
  handlers: {
    onStatus: (step: RagStep) => void;
    onToken: (text: string) => void;
    onDone: (done: RagDone) => void;
  }
): Promise<void> {
  const reader = res.body?.getReader();
  if (!reader) throw new Error("no body");
  const dec = new TextDecoder();
  let buf = "";
  let sawDone = false;

  const take = (block: string) => {
    const line = block.split(/\r?\n/).find((item) => item.startsWith("data:"));
    if (!line) return;
    const raw = line.slice(5).trim();
    if (!raw) return;
    const ev = JSON.parse(raw) as Record<string, unknown>;
    if (ev.type === "status" && ev.message) {
      handlers.onStatus({ stage: String(ev.stage || ""), message: String(ev.message) });
    } else if (ev.type === "token" && ev.text) {
      handlers.onToken(String(ev.text));
    } else if (ev.type === "done") {
      sawDone = true;
      const refs = Array.isArray(ev.references) ? (ev.references as Array<Record<string, unknown>>) : [];
      handlers.onDone({
        references: refs,
        refused: Boolean(ev.refused),
        route: String(ev.route || ""),
      });
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) take(part);
  }
  if (buf.trim()) take(buf);
  if (!sawDone) throw new Error("stream ended without done");
}
