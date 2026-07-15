<!--
  Page.vue -- 插件详情页（被 MoviePilot 前端通过 Module Federation 加载到插件详情 Tab）。
  上方运行状态概览；下方手动搜索（TG 频道 + 资源站），结果用响应式卡片网格展示。
  props 由 MP 注入：pluginId、api。
-->
<template>
  <div class="tg115-page">
    <!-- ============ 状态概览 ============ -->
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
      </v-card-text>
    </v-card>

    <!-- ============ 手动搜索 ============ -->
    <v-card variant="outlined" rounded="lg">
      <v-card-title class="d-flex align-center px-4 py-3">
        <v-icon icon="mdi-magnify" color="primary" class="mr-2" />
        手动搜索网盘资源
        <v-chip v-if="results.length" size="x-small" variant="tonal" color="primary" class="ml-2">
          {{ results.length }} 条
        </v-chip>
        <v-spacer />
        <v-chip v-if="has115" size="x-small" variant="tonal" color="success">含 115 可转存</v-chip>
      </v-card-title>
      <v-divider />
      <v-card-text class="px-4 py-4">
        <v-text-field
          v-model="keyword"
          label="输入片名搜索（TG 频道 + 资源站，仅 115 可转存）"
          variant="outlined"
          density="comfortable"
          hide-details
          :loading="searching"
          append-inner-icon="mdi-magnify"
          @click:append-inner="doSearch"
          @keyup.enter="doSearch"
        />
        <div v-if="searchMsg" class="text-caption mt-2" :class="searchOk ? 'text-success' : 'text-error'">
          {{ searchMsg }}
        </div>
      </v-card-text>

      <!-- 搜索结果：响应式卡片网格（1/2/3/4 列） -->
      <v-card-text v-if="results.length" class="px-4 pb-4 pt-0">
        <v-row dense>
          <v-col v-for="(r, i) in results" :key="i" cols="12" sm="6" md="4" lg="3">
            <v-card variant="tonal" rounded="lg" class="result-card h-100 d-flex flex-column">
              <v-card-item class="pb-2">
                <div class="d-flex align-center mb-2">
                  <v-chip :color="panColor(r.pan_type)" size="x-small" variant="flat" class="mr-2">
                    {{ panLabel(r.pan_type) }}
                  </v-chip>
                  <span v-if="r.pub_date" class="text-caption text-medium-emphasis">{{ r.pub_date.slice(0, 10) }}</span>
                </div>
                <div class="text-body-2 font-weight-medium line-clamp-2" :title="r.title">{{ r.title }}</div>
                <div class="text-caption text-medium-emphasis mt-1">{{ r.channel || '未知来源' }}</div>
              </v-card-item>
              <v-card-text v-if="r.text" class="py-0 flex-grow-1">
                <div class="text-caption text-medium-emphasis line-clamp-3">{{ r.text }}</div>
              </v-card-text>
              <v-card-actions class="pt-2">
                <v-btn size="small" variant="text" prepend-icon="mdi-content-copy" @click="copy(r)">复制链接</v-btn>
                <v-spacer />
                <v-btn
                  v-if="r.pan_type === '115'"
                  size="small" variant="flat" color="primary" prepend-icon="mdi-cloud-download"
                  :loading="transferringIdx === i"
                  @click="transfer(r, i)"
                >转存</v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <v-snackbar v-model="snack" :color="snackColor" :timeout="2500" location="top">{{ snackText }}</v-snackbar>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

const props = defineProps({
  pluginId: { type: String, default: 'TgSearch115' },
  api: { type: Object, default: null },
})

const PID = computed(() => props.pluginId || 'TgSearch115')

// ---- 配置 / 状态 ----
const config = reactive({ enabled: false, p115_cookie: '', delay_seconds: 0, tg_channels: [] })
const channelCount = computed(() => (Array.isArray(config.tg_channels) ? config.tg_channels.length : 0))
const loginOk = computed(() => {
  const c = String(config.p115_cookie || '')
  return c.length > 0 && ['UID', 'CID', 'SEID'].every((k) => c.includes(k + '='))
})

// ---- 搜索 ----
const keyword = ref(localStorage.getItem('tg115_last_keyword') || '')
const results = ref([])
const searching = ref(false)
const searchMsg = ref('')
const searchOk = ref(false)
const transferringIdx = ref(-1)
const has115 = computed(() => results.value.some((r) => r.pan_type === '115'))
// snackbar
const snack = ref(false)
const snackColor = ref('')
const snackText = ref('')

const PAN_LABEL = { '115': '115', quark: '夸克', baidu: '百度', aliyun: '阿里', xunlei: '迅雷', cloud189: '天翼', uc: 'UC', other: '其他' }
const PAN_COLOR = { '115': 'success', quark: 'info', baidu: 'error', aliyun: 'cyan', xunlei: 'purple', cloud189: 'indigo', uc: 'orange', other: 'grey' }
function panLabel(t) { return PAN_LABEL[t] || t || '其他' }
function panColor(t) { return PAN_COLOR[t] || 'grey' }

async function doSearch() {
  const kw = (keyword.value || '').trim()
  if (!kw) { showSnack('请输入搜索关键字', 'warning'); return }
  if (!props.api?.get) { showSnack('API 未就绪', 'error'); return }
  searching.value = true
  searchMsg.value = ''
  try {
    const res = await props.api.get(`plugin/${PID.value}/search?keyword=${encodeURIComponent(kw)}`)
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    if (data && data.success) {
      results.value = Array.isArray(data.results) ? data.results : []
      searchMsg.value = data.message || `找到 ${results.value.length} 条`
      searchOk.value = true
      localStorage.setItem('tg115_last_keyword', kw)
    } else {
      results.value = []
      searchMsg.value = (data && data.message) || '搜索失败'
      searchOk.value = false
    }
  } catch (e) {
    results.value = []
    searchMsg.value = '搜索异常：' + (e?.message || e)
    searchOk.value = false
  } finally {
    searching.value = false
  }
}

// 115 链接：若提取码未附在 URL 上，补上（share_receive 需要 receive_code）
function fullShareUrl(r) {
  let url = r.share_url || ''
  const rc = r.receive_code || ''
  if (r.pan_type === '115' && rc && !/[?&](password|receive_code|pwd)=/.test(url)) {
    url += (url.includes('?') ? '&' : '?') + 'password=' + rc
  }
  return url
}

async function copy(r) {
  const url = fullShareUrl(r)
  try {
    await navigator.clipboard.writeText(url)
    showSnack('已复制链接', 'success')
  } catch {
    showSnack('复制失败，请手动复制', 'error')
  }
}

async function transfer(r, i) {
  if (!loginOk.value) { showSnack('未登录 115，无法转存', 'error'); return }
  transferringIdx.value = i
  try {
    const url = encodeURIComponent(fullShareUrl(r))
    const res = await props.api.get(`plugin/${PID.value}/transfer?share_url=${url}`)
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    showSnack(data?.message || (data?.success ? '转存成功' : '转存失败'), data?.success ? 'success' : 'error')
  } catch (e) {
    showSnack('转存异常：' + (e?.message || e), 'error')
  } finally {
    transferringIdx.value = -1
  }
}

function showSnack(text, color) {
  snackText.value = text
  snackColor.value = color
  snack.value = true
}

onMounted(async () => {
  if (!props.api?.get) return
  try {
    const res = await props.api.get(`plugin/${PID.value}/config/get`)
    const cfg = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    if (cfg && typeof cfg === 'object') Object.assign(config, cfg)
  } catch {
    // 静默
  }
})
</script>

<style scoped>
.tg115-page {
  max-width: 1280px;
  margin: 0 auto;
}
.result-card {
  min-height: 180px;
}
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
