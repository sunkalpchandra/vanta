"use client";

import { useEffect, useState } from "react";

/** Renders "today" from the reader's clock, not the server's timezone. */
export function TodayDate() {
  const [text, setText] = useState("");
  useEffect(() => {
    setText(
      new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }),
    );
  }, []);
  return <div className="micro-label min-h-[1em]">{text}</div>;
}
