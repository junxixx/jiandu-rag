const KEY = "dj_rag_history";
const MAX = 10;

export function pushRagQuestion(q: string): void {
  const t = q.trim();
  if (!t) return;
  try {
    let arr: string[] = JSON.parse(localStorage.getItem(KEY) || "[]");
    if (!Array.isArray(arr)) arr = [];
    arr = [t, ...arr.filter((x) => x !== t)].slice(0, MAX);
    localStorage.setItem(KEY, JSON.stringify(arr));
  } catch {
    localStorage.setItem(KEY, JSON.stringify([t]));
  }
}

export function getRagHistory(): string[] {
  try {
    const arr = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function clearRagHistory(): void {
  localStorage.removeItem(KEY);
}
