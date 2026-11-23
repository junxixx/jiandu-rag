<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import http from "@/api/http";
import { getThemePref, setThemePref, type ThemePref } from "@/composables/useTheme";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const hideNav = computed(() => route.name === "login" || route.name === "register");

const activeMenu = computed(() => {
  const p = route.path;
  if (p.startsWith("/forum")) return "/forum";
  if (p.startsWith("/slip")) return "/browse";
  if (p.startsWith("/debate")) return "/debate";
  if (p.startsWith("/quests")) return "/quests";
  return p;
});

const themeMode = ref<ThemePref>("system");
onMounted(() => {
  themeMode.value = getThemePref();
});
function onThemeCommand(cmd: string) {
  const m = cmd as ThemePref;
  if (m === "light" || m === "dark" || m === "system") {
    themeMode.value = m;
    setThemePref(m);
  }
}

async function logout() {
  try {
    await http.post("/auth/logout");
  } catch {
    /* ignore */
  }
  auth.clear();
  router.push({ name: "login" });
}
</script>

<template>
  <a href="#main-content" class="skip-link">跳到正文</a>
  <div class="dj-top-accent" aria-hidden="true" />
  <el-container class="layout" direction="vertical">
    <el-header v-if="!hideNav" height="72px" class="header">
      <div
        class="brand-block"
        role="button"
        tabindex="0"
        aria-label="返回问牍·青声首页"
        @click="router.push('/home')"
        @keydown.enter.prevent="router.push('/home')"
      >
        <span class="brand-seal" aria-hidden="true">青</span>
        <div class="brand-text">
          <div class="brand">问牍·青声</div>
          <div class="tagline">RAG与多角色AI驱动的简牍社交学习平台</div>
        </div>
      </div>
      <el-divider direction="vertical" class="head-divider" />
      <el-menu
        mode="horizontal"
        :ellipsis="false"
        :router="true"
        :default-active="activeMenu"
        class="menu"
      >
        <el-menu-item index="/home">书斋</el-menu-item>
        <el-menu-item index="/browse">牍库</el-menu-item>
        <el-menu-item index="/daily">每日一牍</el-menu-item>
        <el-menu-item index="/graph">简牍图谱</el-menu-item>
        <el-menu-item index="/chat">边塞夜话</el-menu-item>
        <el-menu-item index="/debate">辩论社</el-menu-item>
        <el-menu-item index="/quests">戍边手记</el-menu-item>
        <el-menu-item index="/forum">雅集论道</el-menu-item>
        <el-menu-item v-if="auth.token" index="/profile">我的简册</el-menu-item>
      </el-menu>
      <div class="right">
        <el-dropdown trigger="click" @command="onThemeCommand">
          <el-button class="pill-btn" text type="primary" aria-label="外观与护眼模式">
            <span class="pill-inner">
              外观{{ themeMode === "system" ? "·随系统" : themeMode === "dark" ? "·夜读" : "·昼卷" }}
            </span>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="light">浅色纸帛</el-dropdown-item>
              <el-dropdown-item command="dark">深色护眼</el-dropdown-item>
              <el-dropdown-item command="system">跟随系统</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <template v-if="auth.token">
          <span class="nick" :title="auth.user?.nickname">{{ auth.user?.nickname }}</span>
          <el-button class="pill-btn" text type="primary" @click="logout">出关</el-button>
        </template>
        <template v-else>
          <el-button text class="pill-btn" @click="router.push('/login')">登录</el-button>
          <el-button type="primary" round class="cta-reg" @click="router.push('/register')">入册</el-button>
        </template>
      </div>
    </el-header>
    <el-main id="main-content" class="main app-main" tabindex="-1">
      <router-view v-slot="{ Component }">
        <transition name="fade-page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </el-main>
    <el-footer v-if="!hideNav" height="auto" class="site-footer">
      <div class="foot-inner">
        <div class="foot-brand-line" aria-hidden="true" />
        <nav class="foot-nav">
          <router-link to="/browse">牍库</router-link>
          <span class="dot">·</span>
          <router-link to="/debate">辩论社</router-link>
          <span class="dot">·</span>
          <router-link to="/quests">戍边手记</router-link>
          <span class="dot">·</span>
          <router-link to="/about">关于本站</router-link>
          <span class="dot">·</span>
          <router-link to="/legal/terms">用户协议</router-link>
          <span class="dot">·</span>
          <router-link to="/legal/privacy">隐私</router-link>
          <span class="dot">·</span>
          <router-link to="/legal/ai">智能内容说明</router-link>
          <span class="dot">·</span>
          <router-link to="/admin">站务</router-link>
        </nav>
        <p class="foot-copy">问牍·青声 —— RAG与多角色AI驱动的简牍社交学习平台</p>
        <p class="foot-sub">展卷释文、问牍绎读、烽燧夜话、雅集论道，墨迹如新，自成一册</p>
      </div>
    </el-footer>
    <el-backtop v-if="!hideNav" :right="28" :bottom="96" />
  </el-container>
</template>

<style scoped>
.dj-top-accent {
  height: 3px;
  width: 100%;
  flex-shrink: 0;
  background: linear-gradient(
    90deg,
    var(--dj-bamboo) 0%,
    var(--dj-seal) 35%,
    var(--dj-gold) 70%,
    var(--dj-bamboo) 100%
  );
  opacity: 0.85;
}
.layout {
  min-height: 100vh;
  background: transparent;
}
.header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 24px 0 20px;
  border-bottom: 1px solid var(--dj-border-light, #dccfb5);
  background: linear-gradient(
    180deg,
    rgba(255, 252, 245, 0.88) 0%,
    rgba(252, 246, 234, 0.78) 55%,
    rgba(245, 236, 218, 0.82) 100%
  );
  backdrop-filter: blur(14px) saturate(1.15);
  box-shadow: 0 1px 0 rgba(201, 176, 138, 0.25), 0 8px 32px rgba(42, 34, 24, 0.04);
  position: sticky;
  top: 0;
  z-index: 100;
}
.header::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  pointer-events: none;
  opacity: 0.42;
  background:
    repeating-linear-gradient(90deg, rgba(139, 90, 43, 0.22) 0, rgba(139, 90, 43, 0.22) 4px, transparent 4px, transparent 8px),
    url("/patterns/bamboo-stripes.svg") repeat-x left bottom;
  background-size: auto, 100px 14px;
  mix-blend-mode: multiply;
}
.brand-block {
  cursor: pointer;
  padding: 8px 4px 8px 0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-seal {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--dj-font-display, serif);
  font-size: 20px;
  font-weight: 700;
  color: rgba(192, 76, 76, 0.92);
  border: 2px solid rgba(139, 90, 43, 0.45);
  border-radius: 4px;
  background: radial-gradient(circle at 35% 28%, rgba(255, 252, 248, 0.98), rgba(212, 165, 116, 0.22));
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.45), 0 2px 8px rgba(62, 58, 57, 0.08);
  transform: rotate(-4deg);
}
.brand-text {
  min-width: 0;
}
.brand {
  font-family: var(--dj-font-display, serif);
  font-weight: 700;
  font-size: 20px;
  letter-spacing: 0.14em;
  color: var(--dj-ink, #2a2218);
  line-height: 1.15;
}
.tagline {
  font-size: 10px;
  line-height: 1.35;
  max-width: min(520px, 42vw);
  color: var(--dj-ink-soft, #4a3f32);
  letter-spacing: 0.06em;
  margin-top: 4px;
  opacity: 0.88;
  white-space: normal;
}
.head-divider {
  height: 36px;
  margin: 0 4px;
  border-color: rgba(201, 176, 138, 0.55) !important;
}
.menu {
  flex: 1;
  min-width: 0;
  border-bottom: none !important;
  background: transparent;
}
.right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.pill-btn {
  font-size: 13px;
}
.pill-inner {
  padding: 2px 4px;
}
.nick {
  color: var(--dj-ink-soft, #4a3f32);
  font-size: 13px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cta-reg {
  padding: 8px 18px;
  font-family: var(--dj-font-display);
  letter-spacing: 0.08em;
}
.main {
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 12px 22px 40px;
}
.app-main {
  min-height: calc(100vh - 200px);
}
.site-footer {
  padding: 32px 20px 40px;
  background: linear-gradient(
    180deg,
    rgba(252, 246, 234, 0.42) 0%,
    rgba(236, 224, 200, 0.72) 55%,
    rgba(220, 206, 178, 0.55) 100%
  );
  border-top: 1px solid rgba(201, 176, 138, 0.45);
  box-shadow: inset 0 1px 0 rgba(255, 252, 245, 0.5);
}
.foot-inner {
  max-width: 1180px;
  margin: 0 auto;
  text-align: center;
}
.foot-brand-line {
  width: 48px;
  height: 2px;
  margin: 0 auto 16px;
  background: linear-gradient(90deg, transparent, var(--dj-seal), transparent);
  opacity: 0.55;
  border-radius: 2px;
}
.foot-nav {
  font-size: 14px;
  margin-bottom: 10px;
  line-height: 1.8;
}
.foot-nav a {
  color: var(--dj-ink-soft);
  text-decoration: none;
  transition: color 0.2s ease;
}
.foot-nav a:hover {
  color: var(--el-color-primary);
}
.foot-nav a.router-link-active {
  color: var(--el-color-primary);
  font-weight: 600;
}
.dot {
  margin: 0 5px;
  color: var(--dj-border);
  user-select: none;
}
.foot-copy {
  margin: 0;
  font-size: 13px;
  color: var(--dj-ink-soft);
  letter-spacing: 0.12em;
  font-family: var(--dj-font-display);
}
.foot-sub {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--dj-bamboo);
  letter-spacing: 0.2em;
  opacity: 0.9;
}
.fade-page-enter-active,
.fade-page-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}
.fade-page-enter-from,
.fade-page-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
