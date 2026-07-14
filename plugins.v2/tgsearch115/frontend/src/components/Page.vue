<!--
  Page.vue -- 插件详情页（被 MoviePilot 前端通过 Module Federation 加载到插件详情 Tab）。
  展示运行状态概览；props 由 MP 注入：pluginId、api。
-->
<template>
  <div class="tg115-page">
    <v-card variant="outlined" rounded="lg" class="mb-4">
      <v-card-title class="d-flex align-center px-4 py-3">
        <v-icon icon="mdi-robot-outline" color="primary" class="mr-2" />
        拦截mp订阅
        <v-spacer />
        <v-chip :color="config.enabled ? 'success' : 'grey'" variant="tonal" size="small">
          {{ config.enabled ? '运行中' : '已停用' }}
        </v-chip>
      </v-card-title>
      <v-divider />
      <v-card-text class="px-4 py-4">
        <v-row>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">TG 频道数</div>
            <div class="text-h6">{{ channelCount }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">115 登录</div>
            <div class="text-h6" :class="loginOk ? 'text-success' : 'text-medium-emphasis'">
              {{ loginOk ? '已登录' : '未登录' }}
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">触发延迟</div>
            <div class="text-h6">{{ config.delay_seconds || 0 }} 秒</div>
          </v-col>
        </v-row>
        <v-alert
          type="info"
          variant="tonal"
          class="mt-4"
          text="订阅新增时优先到 TG 频道搜索 115 资源，命中并转存成功后自动完成订阅；未命中或转存失败则平滑回退到 MoviePilot 默认搜索。"
        />
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'

const props = defineProps({
  pluginId: { type: String, default: 'TgSearch115' },
  api: { type: Object, default: null },
})

const config = reactive({ enabled: false, p115_cookie: '', delay_seconds: 0, tg_channels: [] })
const channelCount = computed(() => (Array.isArray(config.tg_channels) ? config.tg_channels.length : 0))
const loginOk = computed(() => {
  const c = String(config.p115_cookie || '')
  return c.length > 0 && ['UID', 'CID', 'SEID'].every((k) => c.includes(k + '='))
})

onMounted(async () => {
  if (!props.api?.get) return
  try {
    const res = await props.api.get(`plugin/${props.pluginId || 'TgSearch115'}/config/get`)
    const cfg = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    if (cfg && typeof cfg === 'object') Object.assign(config, cfg)
  } catch (e) {
    // 静默：详情页加载失败不影响主应用
  }
})
</script>

<style scoped>
.tg115-page {
  max-width: 960px;
  margin: 0 auto;
}
</style>
