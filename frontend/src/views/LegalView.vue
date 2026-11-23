<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const section = computed(() => (route.params.section as string) || "terms");

const titles: Record<string, string> = {
  terms: "用户协议（试运行稿）",
  privacy: "隐私政策（试运行稿）",
  ai: "人工智能生成内容说明",
};

const heading = computed(() => titles[section.value] || titles.terms);
</script>

<template>
  <div class="legal-page dj-page">
    <nav class="tabs" aria-label="法务与 AI 说明">
      <router-link :class="{ active: section === 'terms' }" to="/legal/terms">用户协议</router-link>
      <router-link :class="{ active: section === 'privacy' }" to="/legal/privacy">隐私政策</router-link>
      <router-link :class="{ active: section === 'ai' }" to="/legal/ai">AI 说明</router-link>
    </nav>

    <article class="doc">
      <h1 class="dj-heading">{{ heading }}</h1>
      <p class="muted">以下为便于试运行的概要条款，正式对外前应由法务审阅定稿。</p>

      <template v-if="section === 'terms'">
        <section>
          <h2>一、服务性质</h2>
          <p>
            「问牍·青声」面向简牍文化学习与青年社交化场景提供演示级功能，包括但不限于牍库检索、辩论与手记、AI
            辅助问答等。服务可能变更、中断或终止，恕不另行通知。
          </p>
          <h2>二、账号与行为</h2>
          <p>
            您应保证注册信息真实、合法，不得利用本平台传播违法、侵权、仇恨或骚扰性内容。发帖与公开内容须遵守站内审核规则及管理员配置之敏感词策略。
          </p>
          <h2>三、内容与版权</h2>
          <p>
            平台展示的简牍释文、影像等可能来自开放数据集、学术资源平台或合作方整理，仅供学习交流；学术引用请以正式出版物为准。用户生成内容的权利归属以适用法律与平台规则为准。
          </p>
        </section>
      </template>

      <template v-else-if="section === 'privacy'">
        <section>
          <h2>一、我们收集的信息</h2>
          <p>
            可能包括：账号（用户名、邮箱）、您在站内产生的内容与互动记录、为改进产品而采集的匿名或去标识化埋点（如页面路径、事件类型）。
          </p>
          <h2>二、用途</h2>
          <p>用于提供与改进服务、安全风控、合规审计及经您同意的其他用途。</p>
          <h2>三、第三方与 AI</h2>
          <p>
            若您使用问牍、边塞夜话、快读等功能，相关提问与上下文可能经加密传输至合作方智能服务处理。请勿在对话中提交个人敏感信息或保密数据。
          </p>
          <h2>四、您的权利</h2>
          <p>在适用法律范围内，您可查阅、更正或删除部分个人信息，亦可联系运营方咨询。</p>
        </section>
      </template>

      <template v-else-if="section === 'ai'">
        <section>
          <h2>标识与提示</h2>
          <p>
            本平台部分内容由人工智能模型生成或辅助生成（如帖文摘要、辩论反驳、简牍故事化绎读、角色对话等），可能存在事实错误、过度推断或与学术共识不符之处，不构成学术鉴定或法律意见。
          </p>
          <h2>建议用法</h2>
          <p>请将 AI 输出作为启发与草稿，重要结论请核对原始简牍、整理本与专业文献。</p>
        </section>
      </template>
    </article>
  </div>
</template>

<style scoped>
.legal-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 8px 12px 56px;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--dj-border-light);
}
.tabs a {
  color: var(--dj-ink-soft);
  text-decoration: none;
  font-size: 14px;
  padding: 6px 10px;
  border-radius: 4px;
}
.tabs a:hover {
  color: var(--el-color-primary);
  background: rgba(154, 52, 18, 0.08);
}
.tabs a.active {
  color: var(--el-color-primary);
  font-weight: 600;
  background: rgba(154, 52, 18, 0.12);
}
.doc h1 {
  margin: 0 0 10px;
  font-size: 24px;
}
.muted {
  margin: 0 0 24px;
  font-size: 13px;
  color: var(--dj-ink-soft);
  line-height: 1.6;
}
.doc section h2 {
  margin: 22px 0 10px;
  font-size: 17px;
  color: var(--dj-ink);
}
.doc section p {
  margin: 0 0 12px;
  line-height: 1.85;
  font-size: 14px;
  color: var(--dj-ink);
}
</style>
