/**
 * 简牍影像地址：支持相对路径（走 Vite /api 代理）、绝对路径与完整 CDN URL。
 */
export function slipImageSrc(url: string | null | undefined): string {
  if (!url) return "";
  const u = url.trim();
  if (u.startsWith("http://") || u.startsWith("https://")) return u;
  return u.startsWith("/") ? u : `/${u}`;
}
