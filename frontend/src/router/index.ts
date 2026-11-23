import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0, left: 0 };
  },
  routes: [
    { path: "/", redirect: "/home" },
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/views/RegisterView.vue"),
    },
    {
      path: "/home",
      name: "home",
      component: () => import("@/views/HomeView.vue"),
    },
    {
      path: "/browse",
      name: "browse",
      component: () => import("@/views/BrowseSlipsView.vue"),
    },
    {
      path: "/slip/:id",
      name: "slip",
      component: () => import("@/views/SlipDetailView.vue"),
    },
    {
      path: "/graph",
      name: "graph",
      component: () => import("@/views/GraphView.vue"),
    },
    {
      path: "/chat",
      name: "chat",
      component: () => import("@/views/ChatView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/forum",
      name: "forum",
      component: () => import("@/views/ForumView.vue"),
    },
    {
      path: "/forum/:id",
      name: "post",
      component: () => import("@/views/PostDetailView.vue"),
    },
    {
      path: "/profile",
      name: "profile",
      component: () => import("@/views/ProfileView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/daily",
      name: "daily",
      component: () => import("@/views/DailyView.vue"),
    },
    {
      path: "/debate",
      name: "debate",
      component: () => import("@/views/DebateView.vue"),
    },
    {
      path: "/quests",
      name: "quests",
      component: () => import("@/views/QuestLogView.vue"),
    },
    {
      path: "/about",
      name: "about",
      component: () => import("@/views/AboutView.vue"),
    },
    { path: "/legal", redirect: "/legal/terms" },
    {
      path: "/legal/:section",
      name: "legal",
      component: () => import("@/views/LegalView.vue"),
    },
    {
      path: "/admin",
      name: "admin",
      component: () => import("@/views/AdminView.vue"),
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.token) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  return true;
});

export default router;
