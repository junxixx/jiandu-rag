<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const email = ref("");
const nickname = ref("");
const password = ref("");
const inviteCode = ref("");
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    const { data } = await http.post("/auth/register", {
      username: username.value,
      email: email.value,
      nickname: nickname.value || username.value,
      password: password.value,
      invite_code: inviteCode.value.trim() || undefined,
    });
    auth.setSession(data.access_token, data.user, data.refresh_token ?? null);
    ElMessage.success("已入册，欢迎同道");
    router.push("/home");
  } catch {
    ElMessage.error("入册未就：用户名或邮箱或已占用");
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
    <div class="dj-auth-panel dj-auth-panel--wide">
      <h2 class="dj-heading dj-auth-panel__title">注册入册</h2>
      <p class="hint dj-auth-panel__hint">共摹简牍，同温故纸</p>
      <el-form class="dj-auth-panel__form" label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input v-model="username" autocomplete="username" placeholder="册上之名（唯一）" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="email" type="email" autocomplete="email" placeholder="鱼雁相通" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="nickname" placeholder="可留空，默认同用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="至少六位"
          />
        </el-form-item>
        <el-form-item label="邀请码（可选）">
          <el-input v-model="inviteCode" placeholder="同道所赠，可留空" maxlength="16" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" class="full">完成入册</el-button>
        <div class="sub">
          已有名籍？
          <router-link to="/login">返回登录</router-link>
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
