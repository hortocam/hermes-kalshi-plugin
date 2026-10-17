/**
 * S1 stub desktop half — Hermes Desktop plugin (runtime-loaded ESM, no build step).
 *
 * The real SDK contract (developer-guide/desktop-plugin-sdk.md):
 *   - default-export a PLUGIN OBJECT { id, name, register(ctx) }, not a function
 *   - contributions go through ctx.register({ id, area, ... }); a layout pane is
 *     area: 'panes' with data { placement, dock?, width?, height? }
 *   - the plugin's own backend namespace is reached with ctx.rest(path) —
 *     '/ping' here maps to /api/plugins/hermes-kalshi/ping (the dashboard/plugin_api.py
 *     sitting beside this file on the backend).
 *
 * ctx.rest is captured once in register() and used from components (the pattern the
 * bundled kanban plugin uses); 'react' and 'react/jsx-runtime' are rewritten by the
 * runtime loader to the host's React.
 */
import { useEffect, useState } from "react";
import { jsx } from "react/jsx-runtime";

let rest = null;

function PingPane() {
  const [state, setState] = useState("loading…");

  useEffect(() => {
    let alive = true;
    if (!rest) {
      setState("error: ctx.rest unavailable");
      return;
    }
    rest("/ping").then(
      (body) => alive && setState(JSON.stringify(body, null, 1)),
      (err) => alive && setState("error: " + (err && err.message ? err.message : String(err))),
    );
    return () => {
      alive = false;
    };
  }, []);

  return jsx("div", {
    className: "flex h-full flex-col gap-2 p-3 text-sm",
    children: [
      jsx("div", { className: "font-medium", children: "hermes-kalshi spike pane" }),
      jsx("pre", {
        className: "whitespace-pre-wrap text-(--ui-text-tertiary)",
        children: state,
      }),
    ],
  });
}

export default {
  id: "hermes-kalshi", // must match the folder name (desktop-plugins/hermes-kalshi)
  name: "Kalshi (spike)",
  register(ctx) {
    rest = ctx.rest;
    ctx.register({
      id: "pane",
      area: "panes",
      title: "Kalshi (spike)",
      data: { placement: "right", width: "320px" },
      render: () => jsx(PingPane, {}),
    });
  },
};
