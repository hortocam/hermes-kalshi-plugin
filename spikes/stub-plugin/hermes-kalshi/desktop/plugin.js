// S1 stub desktop half. Adapt to the real @hermes/plugin-sdk surface and record deviations.
import { createElement as h, useEffect, useState } from "react";

function Pane({ ctx }) {
  const [state, setState] = useState("loading");
  useEffect(() => {
    ctx.rest("/api/plugins/hermes-kalshi/ping").then(
      (r) => setState(JSON.stringify(r)),
      (e) => setState("error: " + e),
    );
  }, []);
  return h("div", null, "hermes-kalshi spike pane: " + state);
}

export default function register(ctx) {
  ctx.registerPane && ctx.registerPane({ id: "hermes-kalshi", title: "Kalshi (spike)", component: () => h(Pane, { ctx }) });
}
