<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    const { data } = await http.post("/auth/login", {
      username: username.value,
      password: password.value,
    });
    auth.setSession(data.access_token, data.user, data.refresh_token ?? null);
    const redir = (route.query.redirect as string) || "/home";
    router.push(redir);
  } catch {
    ElMessage.error("名籍不符，请核对用户名与密码");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="dj-auth-page dj-auth-page--animated dj-auth-stagger-in">
    <div class="dj-auth-ambient" aria-hidden="true">
      <span class="dj-auth-ambient__orb dj-auth-ambient__orb--seal" />
      <span class="dj-auth-ambient__orb dj-auth-ambient__orb--bamboo" />
    </div>
    <div class="dj-auth-panel">
      <h2 class="dj-heading dj-auth-panel__title">登入书斋</h2>
      <p class="hint dj-auth-panel__hint">以简为友，以学为旅</p>
      <el-form class="dj-auth-panel__form" label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="username" autocomplete="username" placeholder="册上之名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="密语"
          />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" class="full">进入问牍·青声</el-button>
        <div class="sub">
          尚无名籍？
          <router-link to="/register">注册入册</router-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
h2 {
  margin: 0 0 6px;
  font-size: 22px;
}
.hint {
  margin: 0 0 20px;
  font-size: 13px;
  color: var(--dj-ink-soft);
  letter-spacing: 0.15em;
}
.full {
  width: 100%;
  margin-top: 8px;
}
.sub {
  margin-top: 16px;
  text-align: center;
  font-size: 14px;
  color: var(--dj-ink-soft);
}
</style>
