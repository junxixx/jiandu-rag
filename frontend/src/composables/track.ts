import http from "@/api/http";

export function trackEvent(eventType: string, meta?: Record<string, unknown>): void {
  http
    .post("/analytics/event", {
      event_type: eventType,
      path: typeof location !== "undefined" ? location.pathname : "",
      meta,
    })
    .catch(() => {
      /* 埋点失败不影响主流程 */
    });
}
