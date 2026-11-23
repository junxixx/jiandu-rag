<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import http from "@/api/http";

const health = ref<{ tagline?: string } | null>(null);

function resetTour() {
  localStorage.removeItem("dj_tour_v1");
  ElMessage.success("已清除指引记录，返回书斋首页将再次出现新手引导");
}

onMounted(async () => {
  try {
    const { data } = await http.get("/health");
    health.value = data;
  } catch {
    health.value = null;
  }
});
</script>

<template>
  <div class="page dj-page">
    <section class="intro-block dj-slip-card">
      <span class="dj-kicker">关于本站</span>
      <h1 class="dj-heading h1">问牍·青声</h1>
      <p class="dj-prose lead">
        本站面向青年学习者，以<strong>展卷、问疑、夜话、雅集</strong>为脉络，让出土简牍走出库房与论文，进入日常阅读与同伴切磋。边塞禀食、烽燧更鼓、乡里名籍——愿你能在此自成一册学习轨迹。
      </p>
      <el-alert
        v-if="health?.tagline"
        :title="`服务就绪 · ${health.tagline}`"
        type="success"
        :closable="false"
        class="mb"
      />
    </section>

    <el-card class="mt dj-slip-card">
      <template #header>你能在这里做什么</template>
      <ul class="feature-list">
        <li>
          <strong>牍库与图谱</strong>
          <span>检索释文与编号，在编联图谱中见人、见地、见简。</span>
        </li>
        <li>
          <strong>问牍</strong>
          <span>以自然语言提问，系统据牍库材料作答，并附所据简牍出处。</span>
        </li>
        <li>
          <strong>边塞夜话与辩论</strong>
          <span>与历史语境中的角色对谈，或在辩论社中试论简牍与大众史读法。</span>
        </li>
        <li>
          <strong>每日一牍与手记</strong>
          <span>日课、快读、戍边手记与功课积分，养成持续读牍的节奏。</span>
        </li>
        <li>
          <strong>雅集论道</strong>
          <span>按话题发帖、击节、跋尾；长帖可生成提要，便于浏览。</span>
        </li>
        <li>
          <strong>我的简册</strong>
          <span>徽章、打卡、学习地图与展牍记录，一览自己的进度。</span>
        </li>
      </ul>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>数据来源说明</template>
      <ul class="ul">
        <li>
          <strong>简牍影像与释文</strong>：以本站实际入库数据为准，可含公开影像标注集、整理本或合作方授权材料；出土地等著录信息有则展示、无则留空。
        </li>
        <li>
          <strong>学术背景</strong>：可与国内外简牍目录、释文数据库、考古报告等对照阅读；若使用「简牍学术资源数据共享平台」等第三方资源，请以该平台授权与引用规范为准。本站当前未与其做自动 API 对接，是否接入取决于后续合作与接口开放情况。
        </li>
        <li>
          <strong>字体</strong>：界面优先使用系统宋体与黑体；若需与某数据集体例完全一致，可将指定字体文件置于静态资源并通过网页字体引入。
        </li>
      </ul>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>使用贴士</template>
      <ul class="ul">
        <li>未登录亦可浏览牍库、问牍与雅集；<strong>边塞夜话、记入掌阅、功课销号</strong>等需登录。</li>
        <li>图谱若为空，可在站务中同步牍库至图谱服务，或检查筛选条件与节点上限。</li>
        <li>问牍历史仅保存在本机浏览器，清除站点数据后会丢失。</li>
        <li>构建为 PWA 后，可离线访问已缓存的静态页面；简牍全文与智能功能仍需网络。</li>
        <li>站务入口在页脚，需由管理员配置令牌后方可使用排期与配置类功能。</li>
      </ul>
    </el-card>

    <el-card class="mt dj-slip-card">
      <template #header>新手引导</template>
      <p class="p">首次进入书斋会依次提示牍库、每日一牍与问牍。也可在书斋首页点击「重温指引」或在此清除完成标记。</p>
      <el-button type="primary" plain round @click="resetTour">清除引导完成标记</el-button>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  max-width: 800px;
  margin: 0 auto;
}
.intro-block {
  padding: 28px 28px 32px 36px;
  margin-bottom: 8px;
}
.h1 {
  font-size: 26px;
  margin: 0 0 14px;
  letter-spacing: 0.08em;
}
.lead {
  margin: 0;
}
.mb {
  margin-top: 16px;
}
.mt {
  margin-top: 18px;
}
.p {
  line-height: 1.85;
  color: var(--dj-ink-soft);
  margin: 0 0 14px;
  font-size: 15px;
}
.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.feature-list li {
  padding: 14px 0;
  border-bottom: 1px dashed var(--dj-border-light);
  display: grid;
  gap: 6px;
}
.feature-list li:last-child {
  border-bottom: none;
}
.feature-list strong {
  font-family: var(--dj-font-display);
  color: var(--dj-ink);
  font-size: 15px;
  letter-spacing: 0.04em;
}
.feature-list span {
  font-size: 14px;
  color: var(--dj-ink-soft);
  line-height: 1.75;
}
.ul {
  margin: 0;
  padding-left: 1.2em;
  line-height: 1.9;
  color: var(--dj-ink-soft);
  font-size: 14px;
}
</style>
