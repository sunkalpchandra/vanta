import { describe, expect, it } from "vitest";
import { createSseParser } from "./sse";

describe("createSseParser", () => {
  it("parses a complete named event", () => {
    const p = createSseParser();
    expect(p.feed('event: status\ndata: {"ok":true}\n\n')).toEqual([
      { event: "status", data: '{"ok":true}' },
    ]);
  });

  it("defaults the event name to message when no event field is sent", () => {
    const p = createSseParser();
    expect(p.feed("data: hello\n\n")).toEqual([{ event: "message", data: "hello" }]);
  });

  it("parses multiple events from a single chunk", () => {
    const p = createSseParser();
    const msgs = p.feed("event: a\ndata: 1\n\nevent: b\ndata: 2\n\n");
    expect(msgs).toEqual([
      { event: "a", data: "1" },
      { event: "b", data: "2" },
    ]);
  });

  it("buffers partial chunks across feeds, including mid-line splits", () => {
    const p = createSseParser();
    expect(p.feed("event: agent_re")).toEqual([]);
    expect(p.feed('port\ndata: {"agent":')).toEqual([]);
    expect(p.feed(' "quant"}\n\n')).toEqual([
      { event: "agent_report", data: '{"agent": "quant"}' },
    ]);
  });

  it("joins multi-line data with newlines", () => {
    const p = createSseParser();
    expect(p.feed("data: line one\ndata: line two\n\n")).toEqual([
      { event: "message", data: "line one\nline two" },
    ]);
  });

  it("tolerates CRLF line endings, even split across chunks", () => {
    const p = createSseParser();
    expect(p.feed("event: x\r\ndata: 1\r")).toEqual([]);
    expect(p.feed("\n\r\n")).toEqual([{ event: "x", data: "1" }]);
  });

  it("ignores comment keep-alives and unknown fields", () => {
    const p = createSseParser();
    expect(p.feed(": ping\nid: 7\nretry: 500\ndata: real\n\n")).toEqual([
      { event: "message", data: "real" },
    ]);
  });

  it("strips exactly one leading space from field values", () => {
    const p = createSseParser();
    expect(p.feed("data:  padded\n\n")).toEqual([{ event: "message", data: " padded" }]);
    expect(p.feed("data:tight\n\n")).toEqual([{ event: "message", data: "tight" }]);
  });

  it("resets the event name between events", () => {
    const p = createSseParser();
    const msgs = p.feed("event: named\ndata: 1\n\ndata: 2\n\n");
    expect(msgs[1]).toEqual({ event: "message", data: "2" });
  });

  it("does not dispatch an event that carried no data", () => {
    const p = createSseParser();
    expect(p.feed("event: ping\n\n")).toEqual([]);
  });

  it("drops an event never terminated by a blank line", () => {
    const p = createSseParser();
    expect(p.feed("data: half")).toEqual([]);
    expect(p.feed("")).toEqual([]);
  });
});
