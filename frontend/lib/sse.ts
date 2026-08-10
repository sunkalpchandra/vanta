// Minimal incremental parser for text/event-stream bodies read via fetch +
// ReadableStream. Covers the subset the chat endpoint emits: `event:` /
// `data:` fields, comment keep-alives, and events terminated by a blank line.

export interface SseMessage {
  /** Event name from the `event:` field; "message" when absent (SSE default). */
  event: string;
  /** Raw payload — `data:` lines joined with newlines. Usually JSON. */
  data: string;
}

/**
 * Create a stateful parser. Feed it decoded chunks as they arrive; each call
 * returns the events that chunk completed. Partial lines and half-received
 * events are buffered until a later chunk finishes them, so chunk boundaries
 * can fall anywhere — mid-line, mid-event, even mid-CRLF.
 */
export function createSseParser() {
  let tail = ""; // last line of the previous chunk, not yet newline-terminated
  let eventName = "";
  let dataLines: string[] = [];

  return {
    feed(chunk: string): SseMessage[] {
      const out: SseMessage[] = [];
      const lines = (tail + chunk).split("\n");
      tail = lines.pop() ?? "";
      for (const raw of lines) {
        const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
        if (line === "") {
          // Blank line dispatches the accumulated event (if it carried data).
          if (dataLines.length) out.push({ event: eventName || "message", data: dataLines.join("\n") });
          eventName = "";
          dataLines = [];
          continue;
        }
        if (line.startsWith(":")) continue; // comment / keep-alive
        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        let value = colon === -1 ? "" : line.slice(colon + 1);
        if (value.startsWith(" ")) value = value.slice(1); // spec strips one leading space
        if (field === "event") eventName = value;
        else if (field === "data") dataLines.push(value);
        // id / retry are reconnection machinery — the chat stream never reconnects.
      }
      return out;
    },
  };
}
