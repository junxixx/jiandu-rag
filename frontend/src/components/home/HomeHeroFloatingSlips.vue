<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

/** 固定配置；坐标为视口百分比，覆盖全屏各象限 */
type SlipDef = {
  left: string;
  top: string;
  w: number;
  h: number;
  rot: number;
  delayMs: number;
  depth: number;
  blurPx: number;
  text: string;
  fromX: number;
  fromY: number;
};

const SLIPS: SlipDef[] = [
  { left: "3%", top: "6%", w: 30, h: 132, rot: -7, delayMs: 0, depth: 0.88, blurPx: 0.3, text: "戍", fromX: -40, fromY: -55 },
  { left: "18%", top: "72%", w: 24, h: 108, rot: 5, delayMs: 120, depth: 0.72, blurPx: 1.2, text: "簿", fromX: 28, fromY: 48 },
  { left: "82%", top: "4%", w: 32, h: 142, rot: 6, delayMs: 200, depth: 0.92, blurPx: 0, text: "爰书", fromX: 45, fromY: -42 },
  { left: "92%", top: "52%", w: 26, h: 118, rot: -5, delayMs: 100, depth: 0.78, blurPx: 1, text: "禀", fromX: 35, fromY: 32 },
  { left: "1%", top: "38%", w: 22, h: 96, rot: 8, delayMs: 180, depth: 0.65, blurPx: 1.4, text: "候", fromX: -32, fromY: 18 },
  { left: "76%", top: "78%", w: 28, h: 124, rot: -4, delayMs: 160, depth: 0.75, blurPx: 1.1, text: "燧", fromX: 22, fromY: 55 },
  { left: "44%", top: "2%", w: 24, h: 102, rot: -3, delayMs: 70, depth: 0.7, blurPx: 1.2, text: "秩", fromX: -8, fromY: -48 },
  { left: "52%", top: "62%", w: 34, h: 128, rot: 4, delayMs: 140, depth: 0.85, blurPx: 0.45, text: "吏", fromX: -22, fromY: 38 },
  { left: "28%", top: "14%", w: 20, h: 84, rot: 7, delayMs: 230, depth: 0.58, blurPx: 1.5, text: "牒", fromX: -24, fromY: -28 },
  { left: "64%", top: "18%", w: 26, h: 112, rot: -6, delayMs: 170, depth: 0.8, blurPx: 0.85, text: "仓", fromX: 32, fromY: -30 },
  { left: "10%", top: "88%", w: 22, h: 98, rot: 3, delayMs: 190, depth: 0.68, blurPx: 1.3, text: "符", fromX: -18, fromY: 42 },
  { left: "48%", top: "42%", w: 18, h: 76, rot: -8, delayMs: 90, depth: 0.52, blurPx: 1.6, text: "檄", fromX: 12, fromY: 22 },
  { left: "36%", top: "78%", w: 28, h: 116, rot: 5, delayMs: 210, depth: 0.74, blurPx: 1, text: "爰", fromX: -30, fromY: 35 },
  { left: "88%", top: "22%", w: 24, h: 104, rot: -2, delayMs: 130, depth: 0.76, blurPx: 0.95, text: "隧", fromX: 28, fromY: -20 },
  { left: "14%", top: "22%", w: 26, h: 110, rot: 4, delayMs: 150, depth: 0.7, blurPx: 1.15, text: "卒", fromX: -26, fromY: -22 },
  { left: "70%", top: "44%", w: 22, h: 100, rot: -7, delayMs: 110, depth: 0.66, blurPx: 1.25, text: "禀", fromX: 24, fromY: 16 },
];

const reduceMotion = ref(false);
const px = ref(0);
const py = ref(0);
const rx = ref(0);
const ry = ref(0);

let raf = 0;
let mq: MediaQueryList | null = null;
let onMql: (() => void) | null = null;

function detachParallax() {
  window.removeEventListener("pointermove", onPointerMove);
  document.removeEventListener("mouseleave", onPointerLeave);
}

function attachParallax() {
  if (reduceMotion.value) return;
  window.addEventListener("pointermove", onPointerMove, { passive: true });
  document.addEventListener("mouseleave", onPointerLeave, { passive: true });
}

const parallaxStyle = computed(() => ({
  "--slip-px": `${px.value}px`,
  "--slip-py": `${py.value}px`,
  "--slip-rx": `${rx.value}deg`,
  "--slip-ry": `${ry.value}deg`,
}));

function slipVars(s: SlipDef) {
  return {
    "--slip-w": `${s.w}px`,
    "--slip-h": `${s.h}px`,
    "--slip-rot": `${s.rot}deg`,
    "--slip-delay": `${s.delayMs}ms`,
    "--slip-depth": String(s.depth),
    "--slip-blur": `${s.blurPx}px`,
    "--slip-from-x": `${s.fromX}px`,
    "--slip-from-y": `${s.fromY}px`,
    left: s.left,
    top: s.top,
  } as Record<string, string>;
}

function onPointerMove(e: PointerEvent) {
  if (reduceMotion.value) return;
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(() => {
    const nx = e.clientX / Math.max(window.innerWidth, 1) - 0.5;
    const ny = e.clientY / Math.max(window.innerHeight, 1) - 0.5;
    px.value = nx * 18;
    py.value = ny * 14;
    rx.value = ny * -2.6;
    ry.value = nx * 3.2;
  });
}

function onPointerLeave() {
  if (reduceMotion.value) return;
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(() => {
    px.value = 0;
    py.value = 0;
    rx.value = 0;
    ry.value = 0;
  });
}

onMounted(() => {
  mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  reduceMotion.value = mq.matches;
  onMql = () => {
    const next = mq?.matches ?? false;
    if (next !== reduceMotion.value) {
      reduceMotion.value = next;
      detachParallax();
      attachParallax();
    }
  };
  mq.addEventListener("change", onMql);

  void nextTick(() => {
    attachParallax();
  });
});

onBeforeUnmount(() => {
  if (mq && onMql) mq.removeEventListener("change", onMql);
  detachParallax();
  cancelAnimationFrame(raf);
});
</script>

<template>
  <div
    class="home-slips"
    :class="{ 'home-slips--reduce': reduceMotion }"
    aria-hidden="true"
  >
    <div class="home-slips__vignette" />
    <div class="home-slips__parallax" :style="parallaxStyle">
      <div
        v-for="(s, i) in SLIPS"
        :key="i"
        class="home-slips__slip"
        :class="{ 'home-slips__slip--near': s.blurPx < 0.55 }"
        :style="slipVars(s)"
      >
        <div class="home-slips__inner">
          <span class="home-slips__sheen" aria-hidden="true" />
          <span class="home-slips__rope" />
          <span class="home-slips__glyph">{{ s.text }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 全视口固定背景层，随滚动仍铺满屏幕，营造「满屏飘荡」 */
.home-slips {
  position: fixed;
  inset: 0;
  width: 100vw;
  min-height: 100vh;
  min-height: 100dvh;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.home-slips__vignette {
  position: absolute;
  inset: 0;
  pointer-events: none;
  /* 与暖色牍面协调的轻暗角，不压成「黑幕」 */
  background: radial-gradient(
    ellipse 92% 82% at 50% 42%,
    transparent 0%,
    transparent 38%,
    rgba(139, 90, 43, 0.07) 72%,
    rgba(107, 93, 74, 0.1) 100%
  );
  z-index: 1;
}

.home-slips__parallax {
  position: absolute;
  inset: -4% -2%;
  height: 108%;
  width: 104%;
  pointer-events: none;
  z-index: 0;
  transform: translate3d(var(--slip-px, 0), var(--slip-py, 0), 0) perspective(1000px) rotateX(var(--slip-rx, 0deg))
    rotateY(var(--slip-ry, 0deg));
  transform-style: preserve-3d;
  transition: transform 0.4s ease-out;
}

.home-slips--reduce .home-slips__parallax {
  transform: none;
  transition: none;
}

.home-slips__slip {
  position: absolute;
  width: var(--slip-w);
  height: var(--slip-h);
  opacity: var(--slip-depth);
  filter: blur(var(--slip-blur));
  transform-origin: 50% 50%;
  will-change: transform;
  animation: home-slip-enter 2s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--slip-delay);
}

.home-slips__slip--near {
  z-index: 1;
}

.home-slips__inner {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 4px;
  overflow: hidden;
  will-change: transform;
  animation: home-slip-float 8.5s ease-in-out infinite;
  animation-delay: calc(var(--slip-delay) + 2s);
  /* 暖竹简纸色：与 theme.css / 首页 hero 牍面一致 */
  border: 1px solid rgba(201, 176, 138, 0.55);
  box-shadow:
    0 6px 22px rgba(139, 90, 43, 0.12),
    0 2px 8px rgba(62, 58, 57, 0.06),
    inset 0 1px 0 rgba(255, 252, 248, 0.92),
    inset 0 -1px 0 rgba(139, 90, 43, 0.1);
  background:
    linear-gradient(168deg, rgba(255, 252, 248, 0.55) 0%, transparent 38%),
    linear-gradient(90deg, rgba(139, 90, 43, 0.1) 0%, transparent 14%, transparent 86%, rgba(107, 74, 42, 0.09) 100%),
    repeating-linear-gradient(
      90deg,
      rgba(139, 90, 43, 0.07) 0px,
      rgba(139, 90, 43, 0.07) 1px,
      transparent 1px,
      transparent 4px
    ),
    linear-gradient(
      178deg,
      #fdf8f0 0%,
      #f5ebd8 22%,
      #efe0cc 48%,
      #e8d4b8 72%,
      #dcc9a8 92%,
      #d4bc91 100%
    );
}

/* 斜向柔光，模拟漆边与旧纸反光 */
.home-slips__sheen {
  position: absolute;
  inset: -20% -30%;
  pointer-events: none;
  background: linear-gradient(
    118deg,
    rgba(255, 252, 248, 0.45) 0%,
    rgba(255, 252, 248, 0.08) 32%,
    transparent 48%,
    transparent 100%
  );
  opacity: 0.85;
  mix-blend-mode: soft-light;
}

.home-slips__rope {
  position: absolute;
  z-index: 1;
  left: 0;
  right: 0;
  top: 9%;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(90deg, transparent, rgba(139, 90, 43, 0.28), rgba(184, 140, 88, 0.35), rgba(139, 90, 43, 0.28), transparent);
  box-shadow: 0 1px 0 rgba(255, 252, 248, 0.55);
}

.home-slips__glyph {
  position: absolute;
  z-index: 2;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--dj-font-slip-reading, var(--dj-font-display));
  font-weight: 600;
  font-size: clamp(11px, calc(var(--slip-w) * 0.38), 18px);
  letter-spacing: 0.18em;
  writing-mode: vertical-rl;
  text-orientation: upright;
  color: rgba(62, 58, 57, 0.72);
  text-shadow:
    0 1px 0 rgba(255, 252, 248, 0.45),
    0 0 1px rgba(255, 252, 248, 0.2);
  user-select: none;
  padding-top: 11px;
}

@keyframes home-slip-enter {
  from {
    opacity: 0;
    transform: translate3d(var(--slip-from-x), var(--slip-from-y), 0) scale(0.9) rotate(var(--slip-rot));
  }
  to {
    opacity: var(--slip-depth);
    transform: translate3d(0, 0, 0) scale(1) rotate(var(--slip-rot));
  }
}

/* 全方向轻微飘荡 */
@keyframes home-slip-float {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  25% {
    transform: translate3d(5px, -8px, 0);
  }
  50% {
    transform: translate3d(-4px, 5px, 0);
  }
  75% {
    transform: translate3d(3px, 6px, 0);
  }
}

.home-slips--reduce .home-slips__slip {
  animation: none;
  opacity: var(--slip-depth);
  transform: rotate(var(--slip-rot));
  filter: blur(var(--slip-blur));
  will-change: auto;
}
.home-slips--reduce .home-slips__inner {
  animation: none;
  will-change: auto;
}

@media (prefers-reduced-motion: reduce) {
  .home-slips__slip {
    animation: none !important;
    opacity: var(--slip-depth);
    transform: rotate(var(--slip-rot));
    will-change: auto;
  }
  .home-slips__inner {
    animation: none !important;
    will-change: auto;
  }
  .home-slips__parallax {
    transform: none !important;
  }
}

:global(html.dark) .home-slips__inner {
  border-color: rgba(196, 154, 98, 0.32);
  box-shadow:
    0 6px 24px rgba(0, 0, 0, 0.28),
    inset 0 1px 0 rgba(90, 72, 52, 0.35),
    inset 0 -1px 0 rgba(0, 0, 0, 0.22);
  background:
    linear-gradient(168deg, rgba(90, 72, 52, 0.35) 0%, transparent 40%),
    linear-gradient(90deg, rgba(0, 0, 0, 0.15) 0%, transparent 15%, transparent 85%, rgba(0, 0, 0, 0.12) 100%),
    repeating-linear-gradient(90deg, rgba(196, 154, 98, 0.06) 0px, rgba(196, 154, 98, 0.06) 1px, transparent 1px, transparent 4px),
    linear-gradient(178deg, #4a3d2e 0%, #3a3228 45%, #2e2820 100%);
}
:global(html.dark) .home-slips__glyph {
  color: rgba(232, 220, 200, 0.72);
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.45);
}
:global(html.dark) .home-slips__sheen {
  opacity: 0.45;
  mix-blend-mode: overlay;
}
:global(html.dark) .home-slips__rope {
  background: linear-gradient(90deg, transparent, rgba(196, 154, 98, 0.25), rgba(212, 165, 116, 0.32), rgba(196, 154, 98, 0.25), transparent);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.2);
}
:global(html.dark) .home-slips__vignette {
  background: radial-gradient(
    ellipse 90% 82% at 50% 42%,
    transparent 0%,
    transparent 36%,
    rgba(0, 0, 0, 0.18) 100%
  );
}
</style>
