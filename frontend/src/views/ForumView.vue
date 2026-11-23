<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import http from "@/api/http";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

type TopicRow = { id: number; name: string; description: string | null; post_count?: number; hot?: number };
type PostRow = {
  id: number;
  title: string;
  summary: string | null;
  author: string;
  likes_count: number;
  topic_id: number | null;
  topic_name?: string | null;
};

const topics = ref<TopicRow[]>([]);
const topicFilter = ref<number | null>(null);
const items = ref<PostRow[]>([]);
const dialog = ref(false);
const title = ref("");
const content = ref("");
const topicId = ref<number | null>(null);

async function loadTopics() {
  try {
    const { data } = await http.get<{ items: TopicRow[] }>("/public/topics");
    topics.value = data.items || [];
  } catch {
    topics.value = [];
  }
}

async function load() {
  const { data } = await http.get("/posts", {
    params: { page: 1, size: 30, topic_id: topicFilter.value ?? undefined },
  });
  items.value = data.items;
}

async function create() {
  if (!auth.token) {
    router.push("/login");
    return;
  }
  try {
    await http.post("/posts", {
      title: title.value,
      content: content.value,
      topic_id: topicId.value ?? undefined,
    });
    ElMessage.success("已张帖于雅集");
    dialog.value = false;
    title.value = "";
    content.value = "";
    topicId.value = null;
    load();
  } catch {
    ElMessage.error("发帖未就");
  }
}

function openDialog() {
  topicId.value = topicFilter.value;
  dialog.value = true;
}

watch(topicFilter, () => load());

onMounted(async () => {
  await loadTopics();
  load();
});
</script>

<template>
  <div class="page dj-page">
    <span class="dj-kicker head-kicker">同好切磋</span>
    <div class="head">
      <div>
        <h2 class="dj-heading page-h2">雅集论道</h2>
        <p class="sub">切磋简牍研读、考古见闻与青年之见；可按话题分区浏览。</p>
      </div>
      <el-button type="primary" @click="openDialog">张帖</el-button>
    </div>

    <div class="filters">
      <span class="f-lbl">话题</span>
      <el-select v-model="topicFilter" clearable placeholder="全部" class="f-select">
        <el-option label="全部" :value="null" />
        <el-option v-for="t in topics" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
    </div>

    <el-card
      v-for="p in items"
      :key="p.id"
      class="post dj-slip-card"
      shadow="hover"
      @click="router.push(`/forum/${p.id}`)"
    >
      <div v-if="p.topic_name" class="topic-pill">{{ p.topic_name }}</div>
      <h3>{{ p.title }}</h3>
      <p class="summary">{{ p.summary || "启卷阅全文" }}</p>
      <div class="meta">
        <span>{{ p.author }}</span>
        <span>击节 {{ p.likes_count }}</span>
      </div>
    </el-card>
    <el-empty v-if="!items.length" description="雅集尚静，待君首帖" />

    <el-dialog v-model="dialog" width="560px" class="dj-dialog" aria-labelledby="forum-dialog-title">
      <template #header>
        <span id="forum-dialog-title" class="dj-heading">张帖雅集</span>
      </template>
      <p class="field-label">话题（可选）</p>
      <el-select v-model="topicId" clearable placeholder="不选则归入综合" class="full-sel">
        <el-option v-for="t in topics" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
      <el-input v-model="title" placeholder="帖名" />
      <el-input v-model="content" class="mt" type="textarea" :rows="8" placeholder="正文：考证、读后感、问题皆可" />
      <template #footer>
        <el-button @click="dialog = false">作罢</el-button>
        <el-button type="primary" @click="create">张贴</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 32px;
}
.head-kicker {
  display: block;
  margin-bottom: 6px;
}
.page-h2 {
  font-size: 22px;
  margin: 0 0 8px;
  letter-spacing: 0.06em;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
  gap: 12px;
}
.head h2 {
  margin: 0 0 6px;
  font-size: 22px;
}
.sub {
  margin: 0;
  font-size: 13px;
  color: var(--dj-ink-soft);
}
.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.f-lbl {
  font-size: 13px;
  color: var(--dj-ink-soft);
}
.f-select {
  min-width: 200px;
}
.full-sel {
  width: 100%;
}
.topic-pill {
  display: inline-block;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(154, 52, 18, 0.12);
  color: var(--dj-seal);
  margin-bottom: 8px;
}
.post {
  margin-bottom: 14px;
  cursor: pointer;
  transition: transform 0.15s ease;
}
.post:hover {
  transform: translateY(-2px);
}
.post h3 {
  margin: 0 0 8px;
  font-family: var(--dj-font-display);
  color: var(--dj-ink);
  font-size: 17px;
}
.summary {
  color: var(--dj-ink-soft);
  font-size: 14px;
  margin: 0;
  line-height: 1.6;
}
.meta {
  margin-top: 10px;
  font-size: 12px;
  color: var(--dj-bamboo);
  display: flex;
  gap: 16px;
}
.mt {
  margin-top: 12px;
}
.field-label {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--dj-ink-soft);
}
</style>
