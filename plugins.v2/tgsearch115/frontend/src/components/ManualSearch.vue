<template>
  <div class="manual-search">
    <div class="filter-row mb-2">
      <span class="filter-label">搜索范围</span>
      <v-btn-toggle v-model="source" mandatory color="primary" density="compact" divided class="filter-toggle">
        <v-btn value="all" size="small">全部</v-btn>
        <v-btn value="tg" size="small">TG</v-btn>
        <v-btn value="site" size="small">观影</v-btn>
        <v-btn value="pansou" size="small">PanSou</v-btn>
        <v-btn value="juying" size="small">聚影</v-btn>
      </v-btn-toggle>
      <span class="text-caption text-medium-emphasis">选择后点击搜索生效</span>
    </div>
    <div class="search-toolbar mb-3">
      <v-text-field
        v-model="keyword"
        label="搜索关键字（影片名 + 年份）"
        variant="outlined"
        density="comfortable"
        hide-details
        :loading="searching"
        @keyup.enter="search"
      />
      <v-btn color="primary" variant="flat" :loading="searching" prepend-icon="mdi-magnify" @click="search">搜索</v-btn>
    </div>

    <div v-if="results.length" class="filter-row mb-2">
      <v-btn size="small" variant="text" prepend-icon="mdi-delete-outline" @click="clearResults">清空结果</v-btn>
    </div>

    <div class="filter-row mb-2">
      <span class="filter-label">资源</span>
      <v-btn-toggle v-model="resourceType" mandatory color="primary" density="compact" divided class="filter-toggle">
        <v-btn value="all" size="small">全部</v-btn>
        <v-btn value="magnet" size="small">磁力</v-btn>
        <v-btn value="pan" size="small">网盘</v-btn>
      </v-btn-toggle>
      <v-chip v-if="results.length" size="x-small" variant="tonal" color="primary">{{ filtered.length }}/{{ results.length }} 条</v-chip>
      <v-btn v-if="resourceType !== 'all' || detailFilter !== 'all'" size="small" variant="text" @click="resetFilters">重置筛选</v-btn>
    </div>

    <div v-if="resourceType === 'magnet'" class="filter-row mb-3">
      <span class="filter-label">画质</span>
      <v-btn-toggle v-model="detailFilter" mandatory color="primary" density="compact" divided class="filter-toggle">
        <v-btn v-for="item in MAGNET_FILTERS" :key="item.value" :value="item.value" size="small">{{ item.title }}</v-btn>
      </v-btn-toggle>
    </div>
    <div v-else-if="resourceType === 'pan'" class="filter-row mb-3">
      <span class="filter-label">网盘</span>
      <v-btn-toggle v-model="detailFilter" mandatory color="primary" density="compact" divided class="filter-toggle">
        <v-btn v-for="item in PAN_FILTERS" :key="item.value" :value="item.value" size="small">{{ item.title }}</v-btn>
      </v-btn-toggle>
    </div>

    <div v-if="sourceSummary" class="source-summary mb-2">{{ sourceSummary }}</div>
    <div v-if="searched" class="text-caption text-medium-emphasis mb-3">后端返回：{{ backendCount }} 条 · 来源筛选：{{ sourceFilteredResults.length }} 条 · 资源筛选：{{ resourceFilteredCount }} 条 · 详细筛选：{{ filtered.length }} 条</div>
    <div v-if="message" class="text-caption mb-3" :class="ok ? 'text-success' : 'text-error'">{{ message }}</div>
    <div v-if="searching" class="empty-state"><v-progress-circular indeterminate size="40" color="primary" /></div>
    <v-row v-else-if="filtered.length" dense>
      <v-col v-for="(r, i) in filtered" :key="r.share_url || i" cols="12" sm="6" lg="4">
        <v-card variant="outlined" class="result-card h-100 d-flex flex-column">
          <v-card-item>
            <div class="d-flex align-center ga-1 mb-2">
              <v-chip :color="panColor(r.pan_type)" size="x-small" variant="tonal">{{ panLabel(r.pan_type) }}</v-chip>
              <v-chip v-if="r.source" size="x-small" variant="tonal">{{ sourceLabel(r.source) }}</v-chip>
              <v-chip v-if="r.upstream_source" size="x-small" variant="outlined">{{ r.upstream_source }}</v-chip>
              <v-chip v-if="r.resource_kind === 'magnet' && r.resolution !== 'unknown'" size="x-small" variant="outlined">{{ qualityLabel(r) }}</v-chip>
              <v-chip v-if="r.has_chinese_subtitle" size="x-small" color="success" variant="outlined">中文字幕</v-chip>
              <v-chip v-if="r.is_complete" color="success" size="x-small" variant="tonal">完结</v-chip>
            </div>
            <div class="text-body-2 font-weight-medium">{{ r.display_name || r.title }}</div>
            <div v-if="r.meta" class="text-caption text-primary mt-1">{{ r.meta }}</div>
            <div class="text-caption text-medium-emphasis line-clamp-3 mt-1">{{ r.text || r.title }}</div>
            <div class="text-caption text-medium-emphasis mt-1">{{ r.channel || '未知来源' }}</div>
          </v-card-item>
          <v-spacer />
          <v-card-actions>
            <v-btn size="small" variant="text" prepend-icon="mdi-content-copy" @click="copy(r)">复制链接</v-btn>
            <v-spacer />
            <v-btn
              v-if="['115', 'magnet'].includes(r.pan_type)"
              size="small"
              variant="flat"
              color="primary"
              prepend-icon="mdi-cloud-download"
              :loading="transferring === r.share_url"
              @click="openProcessDialog(r)"
            >{{ r.pan_type === 'magnet' ? '离线到115' : '转存' }}</v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
    <div v-else-if="searched && !searching" class="empty-state">{{ results.length ? '当前筛选条件下没有资源，可重置筛选后查看全部结果' : '所有可用来源均未找到符合条件的资源' }}</div>

    <v-dialog v-model="processDialog" max-width="520" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-shield-check-outline" color="primary" class="mr-2" />确认正式操作
        </v-card-title>
        <v-card-text>
          <div class="text-body-2 mb-3">请选择对应的 MoviePilot 订阅。系统将在提交前重新执行规则和媒体身份确认。</div>
          <v-select
            v-model="subscribeId"
            :items="subscriptions"
            item-title="label"
            item-value="id"
            label="MoviePilot 订阅"
            variant="outlined"
            density="comfortable"
            hide-details
          />
        </v-card-text>
        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" :disabled="!!transferring" @click="closeProcessDialog">取消</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!subscribeId" :loading="!!transferring" @click="transfer">确认提交</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snack" :color="snackColor" :timeout="3000" location="top">{{ snackText }}</v-snackbar>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { filterSearchResults, MAGNET_FILTERS, PAN_FILTERS } from '../searchFilters.js'

const CACHE_KEY = 'TgSearch115:manual-search:v1'
const MAX_CACHED_RESULTS = 500
const RESULT_FIELDS = ['title', 'display_name', 'meta', 'is_complete', 'episode_num', 'share_url', 'receive_code', 'channel', 'source', 'upstream_source', 'pan_type', 'resource_kind', 'resolution', 'quality_class', 'has_chinese_subtitle', 'subtitle_type', 'is_remux', 'season', 'year', 'pub_date', 'text']
const props = defineProps({ pluginId: { type: String, default: 'TgSearch115' }, api: { type: Object, default: null } })
const base = computed(() => `plugin/${props.pluginId || 'TgSearch115'}`)
const keyword = ref('')
const source = ref('all')
const resourceType = ref('all')
const detailFilter = ref('all')
const results = ref([])
const sourceStatus = ref({})
const sourceStats = ref({})
const subscriptions = ref([])
const subscribeId = ref(null)
const selectedResult = ref(null)
const processDialog = ref(false)
const searching = ref(false)
const searched = ref(false)
const transferring = ref('')
const message = ref('')
const ok = ref(false)
const snack = ref(false)
const snackColor = ref('')
const snackText = ref('')
const filtered = computed(() => filterSearchResults(results.value, resourceType.value, detailFilter.value))
const resourceFilteredCount = computed(() => resourceType.value === 'all' ? results.value.length : filterSearchResults(results.value, resourceType.value, 'all').length)
const backendCount = computed(() => Object.values(sourceStats.value).reduce((total, stat) => total + Number(stat?.returned_count || 0), 0) || results.value.length)
const sourceSummary = computed(() => Object.entries(sourceStatus.value).map(([name, state]) => {
  const label = sourceLabel(name)
  if (state?.status === 'success' || state?.status === 'partial_success') return `${label} ${state.status === 'partial_success' ? '部分成功，' : ''}${state.count || 0} 条`
  if (state?.status === 'disabled') return `${label} 已关闭`
  if (state?.status === 'cooldown') return `${label} ${state.message || '冷却中'}`
  return `${label} ${state?.message || '请求失败'}`
}).join(' · '))

watch(resourceType, () => { detailFilter.value = 'all' })
watch([source, resourceType, detailFilter], persistSession)
restoreSession()

function sessionStore() {
  try { return window.sessionStorage } catch { return null }
}
function safeResult(result) {
  return Object.fromEntries(RESULT_FIELDS.filter((field) => result?.[field] !== undefined).map((field) => [field, result[field]]))
}
function persistSession() {
  const store = sessionStore()
  if (!store || !searched.value) return
  try {
    store.setItem(CACHE_KEY, JSON.stringify({
      keyword: keyword.value,
      source: source.value,
      resourceType: resourceType.value,
      detailFilter: detailFilter.value,
      results: results.value.slice(0, MAX_CACHED_RESULTS).map(safeResult),
      sourceStatus: sourceStatus.value,
      sourceStats: sourceStats.value,
      searched: searched.value,
      message: message.value,
      ok: ok.value,
    }))
  } catch {}
}
function restoreSession() {
  const store = sessionStore()
  if (!store) return
  try {
    const cached = JSON.parse(store.getItem(CACHE_KEY) || 'null')
    if (!cached || !Array.isArray(cached.results)) return
    keyword.value = String(cached.keyword || '')
    source.value = String(cached.source || 'all')
    resourceType.value = String(cached.resourceType || 'all')
    detailFilter.value = String(cached.detailFilter || 'all')
    results.value = cached.results.slice(0, MAX_CACHED_RESULTS).map(safeResult)
    sourceStatus.value = cached.sourceStatus && typeof cached.sourceStatus === 'object' ? cached.sourceStatus : {}
    sourceStats.value = cached.sourceStats && typeof cached.sourceStats === 'object' ? cached.sourceStats : {}
    searched.value = !!cached.searched
    message.value = String(cached.message || '')
    ok.value = !!cached.ok
  } catch { store.removeItem(CACHE_KEY) }
}
function clearResults() {
  results.value = []
  sourceStatus.value = {}
  sourceStats.value = {}
  searched.value = false
  message.value = ''
  ok.value = false
  sessionStore()?.removeItem(CACHE_KEY)
}
function resetFilters() { resourceType.value = 'all'; detailFilter.value = 'all' }

function unwrap(res) {
  let value = res
  const seen = new Set()
  while (value && typeof value === 'object' && value.data && typeof value.data === 'object' && !seen.has(value.data)) {
    seen.add(value.data)
    value = value.data
  }
  return value
}
function notify(text, color = 'success') { snackText.value = text; snackColor.value = color; snack.value = true }
function fullUrl(r) {
  let url = String(r?.share_url || '')
  if (r?.pan_type === '115' && r?.receive_code && !/[?&](password|receive_code|pwd)=/.test(url)) {
    url += (url.includes('?') ? '&' : '?') + 'password=' + r.receive_code
  }
  return url
}
async function search() {
  const value = keyword.value.trim()
  if (!value) return notify('请输入搜索关键字', 'warning')
  if (!props.api?.get) return notify('API 未就绪', 'error')
  clearResults()
  searching.value = true
  searched.value = true
  message.value = ''
  try {
    const data = unwrap(await props.api.get(`${base.value}/search?keyword=${encodeURIComponent(value)}&source=${source.value}`))
    const sourceItems = Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data?.results)
        ? data.results
        : Array.isArray(data?.resources)
          ? data.resources
          : Array.isArray(data?.data?.items)
            ? data.data.items
            : []
    results.value = sourceItems
    sourceStatus.value = data?.source_status && typeof data.source_status === 'object' ? data.source_status : {}
    sourceStats.value = data?.source_stats && typeof data.source_stats === 'object' ? data.source_stats : {}
    ok.value = !!data?.success
    message.value = data?.warning || data?.message || (ok.value ? `找到 ${results.value.length} 条` : '搜索失败')
  } catch (e) {
    results.value = []
    ok.value = false
    message.value = e?.response?.data?.message || e?.message || '搜索失败'
  } finally {
    searching.value = false
    persistSession()
  }
}
async function copy(r) {
  try { await navigator.clipboard.writeText(fullUrl(r)); notify('已复制链接') }
  catch { notify('复制失败，请手动复制', 'error') }
}
async function openProcessDialog(r) {
  if (!props.api) return notify('API 未就绪', 'error')
  selectedResult.value = r
  subscribeId.value = null
  if (!subscriptions.value.length) await loadSubscriptions()
  processDialog.value = true
}
function closeProcessDialog() {
  processDialog.value = false
  selectedResult.value = null
  subscribeId.value = null
}
async function transfer() {
  const r = selectedResult.value
  if (!r || !subscribeId.value) return notify('请选择 MoviePilot 订阅', 'warning')
  transferring.value = r.share_url
  try {
    const response = await props.api.post(`${base.value}/manual/process`, {
      subscribe_id: subscribeId.value,
      confirm: true,
      candidate: {
        share_url: fullUrl(r),
        receive_code: r.receive_code || '',
        title: r.title || r.display_name || '',
        text: r.text || '',
        pan_type: r.pan_type || '',
        source: r.source || '',
      },
    })
    const data = unwrap(response)
    if (!data || typeof data !== 'object') throw new Error('服务返回非 JSON，请检查插件日志')
    const success = data.success === true || data.code === 0
    notify(data.message || (success ? '任务提交成功' : '提交失败'), success ? 'success' : 'error')
    if (success) closeProcessDialog()
  } catch (e) {
    notify(e?.response?.data?.message || e?.message || '离线请求失败', 'error')
  } finally { transferring.value = '' }
}
async function loadSubscriptions() {
  if (!props.api?.get) return
  try {
    const data = unwrap(await props.api.get(`${base.value}/manual/subscriptions`))
    subscriptions.value = Array.isArray(data?.items) ? data.items : []
  } catch { subscriptions.value = [] }
}
function sourceLabel(value) { return ({ tg: 'TG', site: '观影', pansou: 'PanSou', juying: '聚影' })[value] || value }
function panLabel(t) { return ({ '115':'115网盘', quark:'夸克网盘', baidu:'百度网盘', aliyun:'阿里网盘', xunlei:'迅雷网盘', cloud189:'天翼网盘', uc:'UC网盘', '123':'123网盘', magnet:'磁力' })[t] || '其他' }
function panColor(t) { return ({ '115':'success', quark:'info', baidu:'error', aliyun:'warning', xunlei:'secondary', cloud189:'primary', uc:'orange', '123':'teal', magnet:'deep-purple' })[t] || 'grey' }
function qualityLabel(r) { return ({ '4k': '4K', '1080p': '1080P', '720p': '720P' })[r?.resolution] || '未知' }
</script>

<style scoped>
.search-toolbar { display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:8px; align-items:center; }
.filter-row { display:flex; align-items:center; gap:8px; min-width:0; flex-wrap:wrap; }
.filter-label { flex:0 0 32px; font-size:.75rem; color:rgba(var(--v-theme-on-surface),.6); }
.filter-toggle { flex-wrap:wrap; height:auto; max-width:calc(100% - 40px); overflow-x:auto; }
.source-summary { padding:10px 12px; border:1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius:6px; font-size:.8rem; }
.result-card { min-height:172px; border-radius:8px; }
.line-clamp-3 { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.empty-state { padding:36px 20px; text-align:center; color:rgba(var(--v-theme-on-surface),.6); }
@media (max-width:600px) { .search-toolbar { grid-template-columns:1fr; } .search-toolbar .v-btn { width:100%; } }
</style>
