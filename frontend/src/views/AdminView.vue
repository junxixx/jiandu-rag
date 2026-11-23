<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import axios from "axios";

const token = ref(sessionStorage.getItem("dj_admin_token") || "");
const blockedText = ref('["示例敏感词"]');
const debateText = ref("");
const summary = ref<Record<string, number> | null>(null);
const slipId = ref(1);
const featureDate = ref("");
const qq = ref("日课问题？");
const qo = ref('["A","B","C","D"]');
const ci = ref(0);

function saveToken() {
  sessionStorage.setItem("dj_admin_token", token.value.trim());
  ElMessage.success("已保存令牌（仅本会话）");
}

function client() {
  return axios.create({
    baseURL: "/api",
    headers: { "X-Admin-Token": token.value.trim() },
    timeout: 60000,
  });
}

async function loadKv() {
  try {
    const b = await client().get("/admin/kv/blocked_words");
    blockedText.value = JSON.stringify(b.data.value ?? [], null, 2);
    const d = await client().get("/admin/kv/debate_topics");
    debateText.value = JSON.stringify(d.data.value ?? [], null, 2);
    ElMessage.success("已拉取配置");
  } catch {
    ElMessage.error("拉取失败：请检查 ADMIN_TOKEN 与后端配置");
  }
}

async function saveBlocked() {
  try {
    const value = JSON.parse(blockedText.value);
    await client().put("/admin/kv/blocked_words", { value });
    ElMessage.success("敏感词已更新");
  } catch {
    ElMessage.error("JSON 格式错误或保存失败");
  }
}

async function saveDebate() {
  try {
    const value = JSON.parse(debateText.value);
    await client().put("/admin/kv/debate_topics", { value });
    ElMessage.success("辩题已更新");
  } catch {
    ElMessage.error("JSON 格式错误或保存失败");
  }
}

async function loadSummary() {
  try {
    const { data } = await client().get("/admin/analytics/summary", { params: { days: 14 } });
    summary.value = data.counts;
  } catch {
    ElMessage.error("统计加载失败");
  }
}

onMounted(() => {
  const d = new Date();
  featureDate.value = d.toISOString().slice(0, 10);
});

async function setDaily() {
  try {
    const quiz_options = JSON.parse(qo.value);
    await client().post("/admin/daily", {
      slip_id: slipId.value,
      feature_date: featureDate.value,
      quiz_question: qq.value,
      quiz_options,
      correct_index: ci.value,
    });
    ElMessage.success("每日简牍已保存");
  } catch {
    ElMessage.error("保存失败（新建须完整题目 JSON）");
  }
}

const reindexBusy = ref(false);
const reindexResult = ref<string>("");
const neoLimit = ref(500);
const neoBusy = ref(false);
const neoResult = ref<string>("");

async function syncNeo4j() {
  if (!token.value.trim()) {
    ElMessage.warning("请先填写并保存管理令牌");
    return;
  }
  neoBusy.value = true;
  neoResult.value = "";
  try {
    const { data } = await client().post("/admin/graph/sync-neo4j", { limit: neoLimit.value });
    neoResult.value = JSON.stringify(data, null, 2);
    ElMessage[data.ok === false ? "error" : "success"](
      data.ok ? `已写入图谱 ${data.synced ?? 0} 条简牍` : (data.error as string) || "同步失败"
    );
  } catch {
    ElMessage.error("图谱同步失败：请检查图谱服务是否已启动及连接配置");
  } finally {
    neoBusy.value = false;
  }
}

async function reindexRag() {
  if (!token.value.trim()) {
    ElMessage.warning("请先填写并保存管理令牌");
    return;
  }
  reindexBusy.value = true;
  reindexResult.value = "";
  try {
    const { data } = await client().post("/rag/reindex", {});
    reindexResult.value = JSON.stringify(data, null, 2);
    ElMessage[data.ok === false ? "error" : "success"](
      data.ok ? `问牍索引已同步，约 ${data.count ?? 0} 条` : (data.error as string) || "同步失败"
    );
  } catch {
    ElMessage.error("问牍索引重建失败：请检查管理令牌与索引目录配置");
  } finally {
    reindexBusy.value = false;
  }
}

type PendingRow = { id: number; title: string; status: string; risk_score: number; created_at: string };
const pendingPosts = ref<PendingRow[]>([]);
const pendingBusy = ref(false);

async function loadPending() {
  if (!token.value.trim()) {
    ElMessage.warning("请先填写并保存管理令牌");
    return;
  }
  pendingBusy.value = true;
  try {
    const { data } = await client().get("/admin/posts/pending");
    pendingPosts.value = data.items || [];
    ElMessage.success("已加载待审队列");
  } catch {
    ElMessage.error("加载失败：令牌或接口");
  } finally {
    pendingBusy.value = false;
  }
}

async function moderatePost(pid: number, status: "published" | "blocked") {
  try {
    await client().patch(`/admin/posts/${pid}/moderate`, { status });
    ElMessage.success(status === "published" ? "已放行" : "已拦截");
    await loadPending();
  } catch {
    ElMessage.error("操作失败");
  }
}
</script>

<template>
  <div class="page">
    <el-alert
      title="站务端：请在服务器环境配置管理令牌，并于下方填入相同令牌后方可操作。"
      type="warning"
      :closable="false"
      class="mb"
      show-icon
    />
    <el-card class="dj-slip-card">
      <el-input
        v-model="token"
        type="password"
        show-password
        placeholder="X-Admin-Token"
        aria-label="管理端令牌"
      />
      <el-button class="mt" @click="saveToken">保存到会话</el-button>
    </el-card>

    <el-tabs class="mt">
      <el-tab-pane label="敏感词 / 辩题">
        <p class="hint">blocked_words 为 JSON 数组字符串；debate_topics 为 JSON 字符串数组。</p>
        <el-button @click="loadKv">从服务器读取</el-button>
        <h4 class="dj-heading">敏感词</h4>
        <el-input v-model="blockedText" type="textarea" :rows="5" aria-label="敏感词 JSON" />
        <el-button class="mt" type="primary" @click="saveBlocked">保存敏感词</el-button>
        <h4 class="dj-heading mt">辩论题预设</h4>
        <el-input v-model="debateText" type="textarea" :rows="6" aria-label="辩题 JSON" />
        <el-button class="mt" type="primary" @click="saveDebate">保存辩题</el-button>
      </el-tab-pane>
      <el-tab-pane label="每日简牍">
        <el-form label-width="100px">
          <el-form-item label="slip_id">
            <el-input-number v-model="slipId" :min="1" />
          </el-form-item>
          <el-form-item label="日期">
            <el-date-picker v-model="featureDate" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" />
          </el-form-item>
          <el-form-item label="题目">
            <el-input v-model="qq" />
          </el-form-item>
          <el-form-item label="选项 JSON">
            <el-input v-model="qo" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="正确索引">
            <el-input-number v-model="ci" :min="0" :max="10" />
          </el-form-item>
          <el-button type="primary" @click="setDaily">提交排期</el-button>
        </el-form>
      </el-tab-pane>
      <el-tab-pane label="知识图谱">
        <p class="hint">
          从牍库生成简牍—标签—人物—遗址—史事等编联关系，供「简牍图谱」页展示。按简牍编号合并，可重复执行以增量更新。
        </p>
        <p class="hint">
          <span class="lbl">同步条数上限</span>
          <el-input-number v-model="neoLimit" :min="1" :max="50000" class="neo-num" />
          （与牍库总条数一致时可一次全量；条数越大耗时越久。）
        </p>
        <el-button type="primary" :loading="neoBusy" @click="syncNeo4j">同步至图谱</el-button>
        <pre v-if="neoResult" class="pre mt">{{ neoResult }}</pre>
      </el-tab-pane>
      <el-tab-pane label="问牍索引">
        <p class="hint">
          为书斋「问牍」构建释文检索索引。需在服务器配置索引存储目录；首次构建可能较慢并需下载语言模型。
        </p>
        <el-button type="primary" :loading="reindexBusy" @click="reindexRag">重建问牍索引</el-button>
        <pre v-if="reindexResult" class="pre mt">{{ reindexResult }}</pre>
      </el-tab-pane>
      <el-tab-pane label="埋点汇总">
        <el-button @click="loadSummary">加载近 14 天</el-button>
        <pre v-if="summary" class="pre">{{ JSON.stringify(summary, null, 2) }}</pre>
      </el-tab-pane>
      <el-tab-pane label="雅集审帖">
        <p class="hint">经智能风控标为待审或拦截的雅集帖子；放行后前台用户可见。</p>
        <el-button type="primary" :loading="pendingBusy" @click="loadPending">加载待审 / 拦截队列</el-button>
        <el-table :data="pendingPosts" class="mt" size="small" empty-text="暂无待处理">
          <el-table-column prop="id" label="ID" width="72" />
          <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="96" />
          <el-table-column prop="risk_score" label="风险" width="72" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="success" plain @click="moderatePost(row.id, 'published')">放行</el-button>
              <el-button size="small" type="danger" plain @click="moderatePost(row.id, 'blocked')">拦截</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.page {
  padding: 12px 0 40px;
  max-width: 720px;
}
.mb {
  margin-bottom: 14px;
}
.mt {
  margin-top: 14px;
}
.hint {
  font-size: 13px;
  color: var(--dj-ink-soft);
  margin-bottom: 10px;
}
.hint code {
  font-size: 12px;
  padding: 0 4px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.06);
}
html.dark .hint code {
  background: rgba(255, 255, 255, 0.08);
}
.lbl {
  margin-right: 8px;
}
.neo-num {
  vertical-align: middle;
}
.pre {
  margin-top: 12px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 6px;
  font-size: 13px;
  overflow: auto;
}
html.dark .pre {
  background: rgba(255, 255, 255, 0.06);
}
</style>
