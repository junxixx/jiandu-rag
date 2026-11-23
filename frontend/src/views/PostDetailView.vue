<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const auth = useAuthStore();
const id = computed(() => Number(route.params.id));

const post = ref<{
  title: string;
  content: string;
  ai_summary: string | null;
  likes_count: number;
  author: string;
  topic_id: number | null;
  topic_name: string | null;
  comments: Array<{ id: number; content: string; author: string }>;
} | null>(null);

const comment = ref("");
const debateSide = ref("正方");
const debateArg = ref("");
const rebuttal = ref("");
const debateLoading = ref(false);

async function load() {
  const { data } = await http.get(`/posts/${id.value}`);
  post.value = data;
}

async function like() {
  if (!auth.token) {
    ElMessage.warning("请先登录再击节");
    return;
  }
  const { data } = await http.post(`/posts/${id.value}/like`);
  if (post.value) post.value.likes_count = data.likes_count;
}

async function sendComment() {
  if (!auth.token) return;
  if (!comment.value.trim()) return;
  await http.post(`/posts/${id.value}/comments`, { content: comment.value });
  comment.value = "";
  load();
}

async function runAiDebate() {
  if (!auth.token) {
    ElMessage.warning("请先登录再唤 AI 辩论员");
    return;
  }
  if (!debateArg.value.trim()) {
    ElMessage.warning("请先写下你的论点");
    return;
  }
  debateLoading.value = true;
  rebuttal.value = "";
  try {
    const { data } = await http.post(`/posts/${id.value}/ai-debate`, {
      side: debateSide.value,
      argument: debateArg.value.trim(),
    });
    rebuttal.value = data.rebuttal || "";
  } catch {
    ElMessage.error("辩论员暂未能回应");
  } finally {
    debateLoading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div v-if="post" class="page dj-page">
    <el-card class="dj-slip-card">
      <div v-if="post.topic_name" class="topic-pill">{{ post.topic_name }}</div>
      <h2 class="dj-heading">{{ post.title }}</h2>
      <p class="author">撰者：{{ post.author }}</p>
      <el-alert
        v-if="post.ai_summary"
        :title="'提要：' + post.ai_summary"
        type="info"
        class="mb"
        :closable="false"
      />
      <div class="content">{{ post.content }}</div>
      <div class="actions">
        <el-button type="primary" plain @click="like">击节 {{ post.likes_count }}</el-button>
      </div>
    </el-card>

    <el-card v-if="auth.token" class="mt dj-slip-card">
      <template #header>帖内 AI 辩论员</template>
      <p class="hint">结合本帖正文，由「牍师辩席」依你所持方作简短质询与驳难，供切磋思路之用。</p>
      <el-radio-group v-model="debateSide" size="small" class="mb">
        <el-radio-button label="正方" />
        <el-radio-button label="反方" />
      </el-radio-group>
      <el-input v-model="debateArg" type="textarea" :rows="4" placeholder="写下你的论点（一两段即可）" />
      <el-button type="primary" class="mt" :loading="debateLoading" @click="runAiDebate">请辩论员驳难</el-button>
      <p v-if="rebuttal" class="rebuttal">{{ rebuttal }}</p>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>跋尾 · 评论</template>
      <div v-for="c in post.comments" :key="c.id" class="citem">
        <strong>{{ c.author }}</strong>
        <span>{{ c.content }}</span>
      </div>
      <el-input
        v-if="auth.token"
        v-model="comment"
        type="textarea"
        :rows="3"
        class="mt"
        placeholder="缀一言于帖后……"
      />
      <el-button v-if="auth.token" type="primary" class="mt" @click="sendComment">题跋</el-button>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 40px;
}
.topic-pill {
  display: inline-block;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(154, 52, 18, 0.12);
  color: var(--dj-seal);
  margin-bottom: 10px;
}
.author {
  color: var(--dj-ink-soft);
  font-size: 14px;
  margin: 0 0 12px;
}
.mb {
  margin: 12px 0;
}
.hint {
  font-size: 13px;
  color: var(--dj-ink-soft);
  line-height: 1.6;
  margin: 0 0 12px;
}
.content {
  white-space: pre-wrap;
  line-height: 1.85;
  color: var(--dj-ink);
  font-size: 15px;
}
.actions {
  margin-top: 20px;
}
.mt {
  margin-top: 12px;
}
.rebuttal {
  margin-top: 14px;
  padding: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  background: rgba(255, 251, 243, 0.95);
  border-left: 3px solid var(--el-color-primary);
  border-radius: 0 6px 6px 0;
  font-size: 14px;
}
.citem {
  padding: 10px 0;
  border-bottom: 1px dashed var(--dj-border-light);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
}
.citem strong {
  font-family: var(--dj-font-display);
  color: var(--el-color-primary);
  font-size: 13px;
}
</style>
