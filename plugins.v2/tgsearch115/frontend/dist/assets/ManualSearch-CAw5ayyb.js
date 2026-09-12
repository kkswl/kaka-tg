import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const MAGNET_FILTERS = [
  { title: '全部', value: 'all' },
  { title: '720P', value: '720p' },
  { title: '1080P', value: '1080p' },
  { title: '中字1080P', value: 'chs1080p' },
  { title: '4K', value: '4k' },
  { title: '中字4K', value: 'chs4k' },
  { title: '原盘', value: 'remux' },
  { title: '未知', value: 'unknown' },
];

const PAN_FILTERS = [
  { title: '全部', value: 'all' },
  { title: '迅雷网盘', value: 'xunlei' },
  { title: '百度网盘', value: 'baidu' },
  { title: '夸克网盘', value: 'quark' },
  { title: '天翼网盘', value: 'cloud189' },
  { title: '115网盘', value: '115' },
  { title: 'UC网盘', value: 'uc' },
  { title: '阿里网盘', value: 'aliyun' },
  { title: '123网盘', value: '123' },
  { title: '其他', value: 'other' },
];

function resultText(result) {
  return [result?.display_name, result?.title, result?.meta, result?.text]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

// Compatibility path for results restored from a pre-v4.7.51 browser cache.
// New API results always carry normalized fields produced by resource_metadata.py.
function legacyMetadata(result) {
  const text = resultText(result);
  const panType = String(result?.pan_type || '').toLowerCase();
  const is4k = /(?<![\w\d])(?:4\s*k|2160[pi]?|3840\s*[x×]\s*2160|uhd)(?![\w\d])/i.test(text);
  const is1080 = !is4k && /(?<![\w\d])(?:1080[pi]?|1920\s*[x×]\s*1080)(?![\w\d])/i.test(text);
  const is720 = !is4k && !is1080 && /(?<![\w\d])(?:720[pi]?|1280\s*[x×]\s*720)(?![\w\d])/i.test(text);
  const subtitle = /(?:中文字幕|中字|简体中文|繁体中文|简繁|\bchs\b|\bcht\b|\.(?:chs|cht)\.(?:srt|ass|sub)|chinese\s+subtitles?)/i.test(text);
  const isRemux = /(?<![\w])(?:remux|原盘|bdmv|blu[\s-]?ray\s+iso|uhd\s+blu[\s-]?ray\s+原盘)(?![\w])/i.test(text);
  const resolution = is4k ? '4k' : is1080 ? '1080p' : is720 ? '720p' : 'unknown';
  return {
    resource_kind: panType === 'magnet' ? 'magnet' : 'pan',
    pan_type: panType || 'other',
    resolution,
    has_chinese_subtitle: subtitle,
    is_remux: isRemux,
    quality_class: isRemux ? 'remux' : subtitle && resolution === '4k' ? 'chs4k' : subtitle && resolution === '1080p' ? 'chs1080p' : resolution,
  }
}

function searchResultMetadata(result) {
  if (result && ['magnet', 'pan'].includes(result.resource_kind) && result.quality_class) return result
  return { ...result, ...legacyMetadata(result) }
}

function filterSearchResults(results, resourceFilter, qualityFilter) {
  return (Array.isArray(results) ? results : []).filter((result) => {
    const metadata = searchResultMetadata(result);
    const panType = String(metadata.pan_type || 'other').toLowerCase();
    if (resourceFilter === 'magnet' && metadata.resource_kind !== 'magnet') return false
    if (resourceFilter === 'pan' && metadata.resource_kind !== 'pan') return false
    if (resourceFilter === '115' && panType !== '115') return false

    if (resourceFilter === 'pan' && qualityFilter !== 'all' && panType !== qualityFilter) return false
    if (resourceFilter === 'magnet' && qualityFilter !== 'all' && metadata.quality_class !== qualityFilter) return false
    // Legacy configuration page filters still use these values. Keep them structured too.
    if (qualityFilter === '4k' && metadata.resolution !== '4k') return false
    if (qualityFilter === '1080p' && metadata.resolution !== '1080p') return false
    const text = resultText(result);
    if (qualityFilter === 'hfr' && !/(?:\b(?:50|60|90|120)\s*fps\b|(?:50|60|90|120)\s*帧(?:率)?|\bhfr\b|高帧率)/i.test(text)) return false
    if (qualityFilter === 'no_hdr' && /(?:\bhdr(?:10\+?)?\b|dolby\s*vision|\bdv\b|dovi|杜比视界)/i.test(text)) return false
    return true
  })
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementVNode:_createElementVNode,withKeys:_withKeys,createElementBlock:_createElementBlock,unref:_unref,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "manual-search" };
const _hoisted_2 = { class: "filter-row mb-2" };
const _hoisted_3 = { class: "search-toolbar mb-3" };
const _hoisted_4 = {
  key: 1,
  class: "filter-row mb-2"
};
const _hoisted_5 = { class: "filter-row mb-2" };
const _hoisted_6 = {
  key: 2,
  class: "filter-row mb-3"
};
const _hoisted_7 = {
  key: 3,
  class: "filter-row mb-3"
};
const _hoisted_8 = {
  key: 4,
  class: "source-summary mb-2"
};
const _hoisted_9 = {
  key: 5,
  class: "text-caption text-medium-emphasis mb-3"
};
const _hoisted_10 = {
  key: 7,
  class: "empty-state"
};
const _hoisted_11 = { class: "d-flex align-center ga-1 mb-2" };
const _hoisted_12 = { class: "text-body-2 font-weight-medium" };
const _hoisted_13 = {
  key: 0,
  class: "text-caption text-primary mt-1"
};
const _hoisted_14 = { class: "text-caption text-medium-emphasis line-clamp-3 mt-1" };
const _hoisted_15 = { class: "text-caption text-medium-emphasis mt-1" };
const _hoisted_16 = {
  key: 9,
  class: "empty-state"
};

const {computed,ref,watch} = await importShared('vue');

const CACHE_KEY = 'TgSearch115:manual-search:v1';
const MAX_CACHED_RESULTS = 500;

const _sfc_main = {
  __name: 'ManualSearch',
  props: { pluginId: { type: String, default: 'TgSearch115' }, api: { type: Object, default: null } },
  setup(__props) {

const RESULT_FIELDS = ['title', 'display_name', 'meta', 'is_complete', 'episode_num', 'share_url', 'receive_code', 'channel', 'source', 'upstream_source', 'pan_type', 'resource_kind', 'resolution', 'quality_class', 'has_chinese_subtitle', 'subtitle_type', 'is_remux', 'season', 'year', 'pub_date', 'text'];
const props = __props;
const base = computed(() => `plugin/${props.pluginId || 'TgSearch115'}`);
const keyword = ref('');
const source = ref('all');
const resourceType = ref('all');
const detailFilter = ref('all');
const results = ref([]);
const sourceStatus = ref({});
const sourceStats = ref({});
const subscriptions = ref([]);
const subscribeId = ref(null);
const selectedResult = ref(null);
const processDialog = ref(false);
const searching = ref(false);
const searched = ref(false);
const transferring = ref('');
const message = ref('');
const ok = ref(false);
const snack = ref(false);
const snackColor = ref('');
const snackText = ref('');
const recoveryMessage = ref('');
const cacheAvailable = ref(true);
const filtered = computed(() => filterSearchResults(results.value, resourceType.value, detailFilter.value));
const resourceFilteredCount = computed(() => resourceType.value === 'all' ? results.value.length : filterSearchResults(results.value, resourceType.value, 'all').length);
const backendCount = computed(() => Object.values(sourceStats.value).reduce((total, stat) => total + Number(stat?.returned_count || 0), 0) || results.value.length);
const sourceSummary = computed(() => Object.entries(sourceStatus.value).map(([name, state]) => {
  const label = sourceLabel(name);
  if (state?.status === 'success' || state?.status === 'partial_success') return `${label} ${state.status === 'partial_success' ? '部分成功，' : ''}${state.count || 0} 条`
  if (state?.status === 'disabled') return `${label} 已关闭`
  if (state?.status === 'cooldown') return `${label} ${state.message || '冷却中'}`
  return `${label} ${state?.message || '请求失败'}`
}).join(' · '));

watch(resourceType, () => { detailFilter.value = 'all'; });
watch([source, resourceType, detailFilter], persistSession);
restoreSession();

function sessionStore() {
  if (!cacheAvailable.value) return null
  try { return window.sessionStorage } catch { cacheAvailable.value = false; return null }
}
function cacheGet(key) {
  try { return sessionStore()?.getItem(key) || null }
  catch { cacheAvailable.value = false; return null }
}
function cacheSet(key, value) {
  try { sessionStore()?.setItem(key, value); return true }
  catch { cacheAvailable.value = false; return false }
}
function cacheRemove(key) {
  try { sessionStore()?.removeItem(key); return true }
  catch { cacheAvailable.value = false; return false }
}
function safeResult(result) {
  return Object.fromEntries(RESULT_FIELDS.filter((field) => result?.[field] !== undefined).map((field) => [field, result[field]]))
}
function safeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback
  try { return String(value) } catch { return fallback }
}
function normalizeManualResult(result, index = 0) {
  const item = result && typeof result === 'object' && !Array.isArray(result) ? result : { title: safeText(result) };
  const panType = safeText(item.pan_type, 'other').toLowerCase() || 'other';
  const resourceKind = ['magnet', 'pan'].includes(item.resource_kind)
    ? item.resource_kind
    : panType === 'magnet' ? 'magnet' : 'pan';
  const title = safeText(item.title || item.display_name, '未命名资源').slice(0, 500);
  return {
    ...safeResult(item),
    result_id: `manual-${index}-${safeText(item.source, 'unknown')}-${panType}`,
    title,
    display_name: safeText(item.display_name || title, title).slice(0, 500),
    pan_type: panType,
    resource_kind: resourceKind,
    source: safeText(item.source, 'unknown'),
    text: safeText(item.text || title, title).slice(0, 2000),
    meta: safeText(item.meta).slice(0, 500),
    resolution: safeText(item.resolution, 'unknown').toLowerCase() || 'unknown',
    quality_class: safeText(item.quality_class, 'unknown').toLowerCase() || 'unknown',
    has_chinese_subtitle: item.has_chinese_subtitle === true,
    share_url: safeText(item.share_url),
  }
}
function persistSession() {
  const store = sessionStore();
  if (!store || !searched.value) return
  try {
    cacheSet(CACHE_KEY, JSON.stringify({
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
    }));
  } catch {}
}
function restoreSession() {
  const store = sessionStore();
  if (!store) return
  try {
    const cached = JSON.parse(cacheGet(CACHE_KEY) || 'null');
    if (!cached || !Array.isArray(cached.results)) return
    keyword.value = String(cached.keyword || '');
    source.value = String(cached.source || 'all');
    resourceType.value = String(cached.resourceType || 'all');
    detailFilter.value = String(cached.detailFilter || 'all');
    results.value = cached.results.slice(0, MAX_CACHED_RESULTS).map(normalizeManualResult);
    sourceStatus.value = cached.sourceStatus && typeof cached.sourceStatus === 'object' ? cached.sourceStatus : {};
    sourceStats.value = cached.sourceStats && typeof cached.sourceStats === 'object' ? cached.sourceStats : {};
    searched.value = !!cached.searched;
    message.value = String(cached.message || '');
    ok.value = !!cached.ok;
  } catch { cacheRemove(CACHE_KEY); }
}
function clearResults() {
  results.value = [];
  sourceStatus.value = {};
  sourceStats.value = {};
  searched.value = false;
  message.value = '';
  ok.value = false;
  cacheRemove(CACHE_KEY);
}
function resetFilters() { resourceType.value = 'all'; detailFilter.value = 'all'; }
function resetSearchArea() {
  searching.value = false;
  processDialog.value = false;
  selectedResult.value = null;
  transferring.value = '';
  recoveryMessage.value = '';
  message.value = '搜索区域已恢复，可以重新搜索';
  ok.value = true;
}

function unwrap(res) {
  let value = res;
  const seen = new Set();
  while (value && typeof value === 'object' && value.data && typeof value.data === 'object' && !seen.has(value.data)) {
    seen.add(value.data);
    value = value.data;
  }
  return value
}
function notify(text, color = 'success') { snackText.value = text; snackColor.value = color; snack.value = true; }
function fullUrl(r) {
  let url = String(r?.share_url || '');
  if (r?.pan_type === '115' && r?.receive_code && !/[?&](password|receive_code|pwd)=/.test(url)) {
    url += (url.includes('?') ? '&' : '?') + 'password=' + r.receive_code;
  }
  return url
}
async function search() {
  const value = safeText(keyword.value).trim();
  if (!value) return notify('请输入搜索关键字', 'warning')
  if (!props.api?.get) return notify('API 未就绪', 'error')
  try {
    clearResults();
    searching.value = true;
    searched.value = true;
    recoveryMessage.value = '';
    message.value = '';
    const data = unwrap(await props.api.get(`${base.value}/search?keyword=${encodeURIComponent(value)}&source=${source.value}`));
    const sourceItems = Array.isArray(data?.items)
      ? data.items
      : Array.isArray(data?.results)
        ? data.results
        : Array.isArray(data?.resources)
          ? data.resources
          : Array.isArray(data?.data?.items)
            ? data.data.items
            : [];
    results.value = sourceItems.map(normalizeManualResult);
    sourceStatus.value = data?.source_status && typeof data.source_status === 'object' ? data.source_status : {};
    sourceStats.value = data?.source_stats && typeof data.source_stats === 'object' ? data.source_stats : {};
    ok.value = !!data?.success;
    message.value = data?.warning || data?.message || (ok.value ? `找到 ${results.value.length} 条` : '搜索失败');
  } catch (e) {
    results.value = [];
    ok.value = false;
    const status = Number(e?.response?.status || 0);
    message.value = status ? `搜索请求失败（HTTP ${status}），可重试` : '搜索请求异常或超时，可重试';
    recoveryMessage.value = '搜索区域发生异常，已恢复；可重新搜索';
  } finally {
    searching.value = false;
    persistSession();
  }
}
async function copy(r) {
  try { await navigator.clipboard.writeText(fullUrl(r)); notify('已复制链接'); }
  catch { notify('复制失败，请手动复制', 'error'); }
}
async function openProcessDialog(r) {
  if (!props.api) return notify('API 未就绪', 'error')
  selectedResult.value = r;
  subscribeId.value = null;
  if (!subscriptions.value.length) await loadSubscriptions();
  processDialog.value = true;
}
function closeProcessDialog() {
  processDialog.value = false;
  selectedResult.value = null;
  subscribeId.value = null;
}
async function transfer() {
  const r = selectedResult.value;
  if (!r || !subscribeId.value) return notify('请选择 MoviePilot 订阅', 'warning')
  transferring.value = r.share_url;
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
    });
    const data = unwrap(response);
    if (!data || typeof data !== 'object') throw new Error('服务返回非 JSON，请检查插件日志')
    const success = data.success === true || data.code === 0;
    notify(data.message || (success ? '任务提交成功' : '提交失败'), success ? 'success' : 'error');
    if (success) closeProcessDialog();
  } catch (e) {
    const status = Number(e?.response?.status || 0);
    notify(status ? `提交请求失败（HTTP ${status}），可重试` : '提交请求异常或超时，可重试', 'error');
  } finally { transferring.value = ''; }
}
async function loadSubscriptions() {
  if (!props.api?.get) return
  try {
    const data = unwrap(await props.api.get(`${base.value}/manual/subscriptions`));
    subscriptions.value = Array.isArray(data?.items) ? data.items : [];
  } catch { subscriptions.value = []; }
}
function sourceLabel(value) { return ({ tg: 'TG', site: '观影', pansou: 'PanSou', juying: '聚影' })[value] || value }
function panLabel(t) { return ({ '115':'115网盘', quark:'夸克网盘', baidu:'百度网盘', aliyun:'阿里网盘', xunlei:'迅雷网盘', cloud189:'天翼网盘', uc:'UC网盘', '123':'123网盘', magnet:'磁力' })[t] || '其他' }
function panColor(t) { return ({ '115':'success', quark:'info', baidu:'error', aliyun:'warning', xunlei:'secondary', cloud189:'primary', uc:'orange', '123':'teal', magnet:'deep-purple' })[t] || 'grey' }
function qualityLabel(r) { return ({ '4k': '4K', '1080p': '1080P', '720p': '720P' })[r?.resolution] || '未知' }

return (_ctx, _cache) => {
  const _component_v_btn = _resolveComponent("v-btn");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_btn_toggle = _resolveComponent("v-btn-toggle");
  const _component_v_text_field = _resolveComponent("v-text-field");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_progress_circular = _resolveComponent("v-progress-circular");
  const _component_v_card_item = _resolveComponent("v-card-item");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_card_actions = _resolveComponent("v-card-actions");
  const _component_v_card = _resolveComponent("v-card");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_select = _resolveComponent("v-select");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_dialog = _resolveComponent("v-dialog");
  const _component_v_snackbar = _resolveComponent("v-snackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (recoveryMessage.value)
      ? (_openBlock(), _createBlock(_component_v_alert, {
          key: 0,
          type: "warning",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          append: _withCtx(() => [
            _createVNode(_component_v_btn, {
              size: "small",
              variant: "text",
              onClick: resetSearchArea
            }, {
              default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
                _createTextVNode("重新加载搜索区域", -1)
              ]))]),
              _: 1
            })
          ]),
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(recoveryMessage.value) + " ", 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_2, [
      _cache[14] || (_cache[14] = _createElementVNode("span", { class: "filter-label" }, "搜索范围", -1)),
      _createVNode(_component_v_btn_toggle, {
        modelValue: source.value,
        "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((source).value = $event)),
        mandatory: "",
        color: "primary",
        density: "compact",
        divided: "",
        class: "filter-toggle"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_v_btn, {
            value: "all",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
              _createTextVNode("全部", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            value: "tg",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
              _createTextVNode("TG", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            value: "site",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
              _createTextVNode("观影", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            value: "pansou",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[12] || (_cache[12] = [
              _createTextVNode("PanSou", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            value: "juying",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[13] || (_cache[13] = [
              _createTextVNode("聚影", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"]),
      _cache[15] || (_cache[15] = _createElementVNode("span", { class: "text-caption text-medium-emphasis" }, "选择后点击搜索生效", -1))
    ]),
    _createElementVNode("div", _hoisted_3, [
      _createVNode(_component_v_text_field, {
        modelValue: keyword.value,
        "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((keyword).value = $event)),
        label: "搜索关键字（影片名 + 年份）",
        variant: "outlined",
        density: "comfortable",
        "hide-details": "",
        loading: searching.value,
        onKeyup: _withKeys(search, ["enter"])
      }, null, 8, ["modelValue", "loading"]),
      _createVNode(_component_v_btn, {
        color: "primary",
        variant: "flat",
        loading: searching.value,
        "prepend-icon": "mdi-magnify",
        onClick: search
      }, {
        default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
          _createTextVNode("搜索", -1)
        ]))]),
        _: 1
      }, 8, ["loading"])
    ]),
    (results.value.length)
      ? (_openBlock(), _createElementBlock("div", _hoisted_4, [
          _createVNode(_component_v_btn, {
            size: "small",
            variant: "text",
            "prepend-icon": "mdi-delete-outline",
            onClick: clearResults
          }, {
            default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
              _createTextVNode("清空结果", -1)
            ]))]),
            _: 1
          })
        ]))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_5, [
      _cache[22] || (_cache[22] = _createElementVNode("span", { class: "filter-label" }, "资源", -1)),
      _createVNode(_component_v_btn_toggle, {
        modelValue: resourceType.value,
        "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((resourceType).value = $event)),
        mandatory: "",
        color: "primary",
        density: "compact",
        divided: "",
        class: "filter-toggle"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_v_btn, {
            value: "all",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
              _createTextVNode("全部", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            value: "magnet",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
              _createTextVNode("磁力", -1)
            ]))]),
            _: 1
          }),
          _createVNode(_component_v_btn, {
            value: "pan",
            size: "small"
          }, {
            default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
              _createTextVNode("网盘", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      }, 8, ["modelValue"]),
      (results.value.length)
        ? (_openBlock(), _createBlock(_component_v_chip, {
            key: 0,
            size: "x-small",
            variant: "tonal",
            color: "primary"
          }, {
            default: _withCtx(() => [
              _createTextVNode(_toDisplayString(filtered.value.length) + "/" + _toDisplayString(results.value.length) + " 条", 1)
            ]),
            _: 1
          }))
        : _createCommentVNode("", true),
      (resourceType.value !== 'all' || detailFilter.value !== 'all')
        ? (_openBlock(), _createBlock(_component_v_btn, {
            key: 1,
            size: "small",
            variant: "text",
            onClick: resetFilters
          }, {
            default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
              _createTextVNode("重置筛选", -1)
            ]))]),
            _: 1
          }))
        : _createCommentVNode("", true)
    ]),
    (resourceType.value === 'magnet')
      ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
          _cache[23] || (_cache[23] = _createElementVNode("span", { class: "filter-label" }, "画质", -1)),
          _createVNode(_component_v_btn_toggle, {
            modelValue: detailFilter.value,
            "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((detailFilter).value = $event)),
            mandatory: "",
            color: "primary",
            density: "compact",
            divided: "",
            class: "filter-toggle"
          }, {
            default: _withCtx(() => [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(MAGNET_FILTERS), (item) => {
                return (_openBlock(), _createBlock(_component_v_btn, {
                  key: item.value,
                  value: item.value,
                  size: "small"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(item.title), 1)
                  ]),
                  _: 2
                }, 1032, ["value"]))
              }), 128))
            ]),
            _: 1
          }, 8, ["modelValue"])
        ]))
      : (resourceType.value === 'pan')
        ? (_openBlock(), _createElementBlock("div", _hoisted_7, [
            _cache[24] || (_cache[24] = _createElementVNode("span", { class: "filter-label" }, "网盘", -1)),
            _createVNode(_component_v_btn_toggle, {
              modelValue: detailFilter.value,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((detailFilter).value = $event)),
              mandatory: "",
              color: "primary",
              density: "compact",
              divided: "",
              class: "filter-toggle"
            }, {
              default: _withCtx(() => [
                (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_unref(PAN_FILTERS), (item) => {
                  return (_openBlock(), _createBlock(_component_v_btn, {
                    key: item.value,
                    value: item.value,
                    size: "small"
                  }, {
                    default: _withCtx(() => [
                      _createTextVNode(_toDisplayString(item.title), 1)
                    ]),
                    _: 2
                  }, 1032, ["value"]))
                }), 128))
              ]),
              _: 1
            }, 8, ["modelValue"])
          ]))
        : _createCommentVNode("", true),
    (sourceSummary.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_8, _toDisplayString(sourceSummary.value), 1))
      : _createCommentVNode("", true),
    (searched.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_9, "后端返回：" + _toDisplayString(backendCount.value) + " 条 · 来源筛选：" + _toDisplayString(_ctx.sourceFilteredResults.length) + " 条 · 资源筛选：" + _toDisplayString(resourceFilteredCount.value) + " 条 · 详细筛选：" + _toDisplayString(filtered.value.length) + " 条", 1))
      : _createCommentVNode("", true),
    (message.value)
      ? (_openBlock(), _createElementBlock("div", {
          key: 6,
          class: _normalizeClass(["text-caption mb-3", ok.value ? 'text-success' : 'text-error'])
        }, _toDisplayString(message.value), 3))
      : _createCommentVNode("", true),
    (searching.value)
      ? (_openBlock(), _createElementBlock("div", _hoisted_10, [
          _createVNode(_component_v_progress_circular, {
            indeterminate: "",
            size: "40",
            color: "primary"
          })
        ]))
      : (filtered.value.length)
        ? (_openBlock(), _createBlock(_component_v_row, {
            key: 8,
            dense: ""
          }, {
            default: _withCtx(() => [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(filtered.value, (r) => {
                return (_openBlock(), _createBlock(_component_v_col, {
                  key: r.result_id,
                  cols: "12",
                  sm: "6",
                  lg: "4"
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_card, {
                      variant: "outlined",
                      class: "result-card h-100 d-flex flex-column"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_v_card_item, null, {
                          default: _withCtx(() => [
                            _createElementVNode("div", _hoisted_11, [
                              _createVNode(_component_v_chip, {
                                color: panColor(r.pan_type),
                                size: "x-small",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(panLabel(r.pan_type)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"]),
                              (r.source)
                                ? (_openBlock(), _createBlock(_component_v_chip, {
                                    key: 0,
                                    size: "x-small",
                                    variant: "tonal"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(sourceLabel(r.source)), 1)
                                    ]),
                                    _: 2
                                  }, 1024))
                                : _createCommentVNode("", true),
                              (r.upstream_source)
                                ? (_openBlock(), _createBlock(_component_v_chip, {
                                    key: 1,
                                    size: "x-small",
                                    variant: "outlined"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(r.upstream_source), 1)
                                    ]),
                                    _: 2
                                  }, 1024))
                                : _createCommentVNode("", true),
                              (r.resource_kind === 'magnet' && r.resolution !== 'unknown')
                                ? (_openBlock(), _createBlock(_component_v_chip, {
                                    key: 2,
                                    size: "x-small",
                                    variant: "outlined"
                                  }, {
                                    default: _withCtx(() => [
                                      _createTextVNode(_toDisplayString(qualityLabel(r)), 1)
                                    ]),
                                    _: 2
                                  }, 1024))
                                : _createCommentVNode("", true),
                              (r.has_chinese_subtitle)
                                ? (_openBlock(), _createBlock(_component_v_chip, {
                                    key: 3,
                                    size: "x-small",
                                    color: "success",
                                    variant: "outlined"
                                  }, {
                                    default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                                      _createTextVNode("中文字幕", -1)
                                    ]))]),
                                    _: 1
                                  }))
                                : _createCommentVNode("", true),
                              (r.is_complete)
                                ? (_openBlock(), _createBlock(_component_v_chip, {
                                    key: 4,
                                    color: "success",
                                    size: "x-small",
                                    variant: "tonal"
                                  }, {
                                    default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
                                      _createTextVNode("完结", -1)
                                    ]))]),
                                    _: 1
                                  }))
                                : _createCommentVNode("", true)
                            ]),
                            _createElementVNode("div", _hoisted_12, _toDisplayString(r.display_name || r.title), 1),
                            (r.meta)
                              ? (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(r.meta), 1))
                              : _createCommentVNode("", true),
                            _createElementVNode("div", _hoisted_14, _toDisplayString(r.text || r.title), 1),
                            _createElementVNode("div", _hoisted_15, _toDisplayString(r.channel || '未知来源'), 1)
                          ]),
                          _: 2
                        }, 1024),
                        _createVNode(_component_v_spacer),
                        _createVNode(_component_v_card_actions, null, {
                          default: _withCtx(() => [
                            _createVNode(_component_v_btn, {
                              size: "small",
                              variant: "text",
                              "prepend-icon": "mdi-content-copy",
                              onClick: $event => (copy(r))
                            }, {
                              default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                                _createTextVNode("复制链接", -1)
                              ]))]),
                              _: 1
                            }, 8, ["onClick"]),
                            _createVNode(_component_v_spacer),
                            (['115', 'magnet'].includes(r.pan_type))
                              ? (_openBlock(), _createBlock(_component_v_btn, {
                                  key: 0,
                                  size: "small",
                                  variant: "flat",
                                  color: "primary",
                                  "prepend-icon": "mdi-cloud-download",
                                  loading: transferring.value === r.share_url,
                                  onClick: $event => (openProcessDialog(r))
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(r.pan_type === 'magnet' ? '离线到115' : '转存'), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["loading", "onClick"]))
                              : _createCommentVNode("", true)
                          ]),
                          _: 2
                        }, 1024)
                      ]),
                      _: 2
                    }, 1024)
                  ]),
                  _: 2
                }, 1024))
              }), 128))
            ]),
            _: 1
          }))
        : (searched.value && !searching.value)
          ? (_openBlock(), _createElementBlock("div", _hoisted_16, _toDisplayString(results.value.length ? '当前筛选条件下没有资源，可重置筛选后查看全部结果' : '所有可用来源均未找到符合条件的资源'), 1))
          : _createCommentVNode("", true),
    _createVNode(_component_v_dialog, {
      modelValue: processDialog.value,
      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((processDialog).value = $event)),
      "max-width": "520",
      persistent: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_card, null, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-shield-check-outline",
                  color: "primary",
                  class: "mr-2"
                }),
                _cache[28] || (_cache[28] = _createTextVNode("确认正式操作 ", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, null, {
              default: _withCtx(() => [
                _cache[29] || (_cache[29] = _createElementVNode("div", { class: "text-body-2 mb-3" }, "请选择对应的 MoviePilot 订阅。系统将在提交前重新执行规则和媒体身份确认。", -1)),
                _createVNode(_component_v_select, {
                  modelValue: subscribeId.value,
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((subscribeId).value = $event)),
                  items: subscriptions.value,
                  "item-title": "label",
                  "item-value": "id",
                  label: "MoviePilot 订阅",
                  variant: "outlined",
                  density: "comfortable",
                  "hide-details": ""
                }, null, 8, ["modelValue", "items"])
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_actions, { class: "px-6 pb-4" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  variant: "text",
                  disabled: !!transferring.value,
                  onClick: closeProcessDialog
                }, {
                  default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_v_btn, {
                  color: "primary",
                  variant: "flat",
                  disabled: !subscribeId.value,
                  loading: !!transferring.value,
                  onClick: transfer
                }, {
                  default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                    _createTextVNode("确认提交", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled", "loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_v_snackbar, {
      modelValue: snack.value,
      "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((snack).value = $event)),
      color: snackColor.value,
      timeout: 3000,
      location: "top"
    }, {
      default: _withCtx(() => [
        _createTextVNode(_toDisplayString(snackText.value), 1)
      ]),
      _: 1
    }, 8, ["modelValue", "color"])
  ]))
}
}

};
const ManualSearch = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-cc81a46b"]]);

export { ManualSearch as M, _export_sfc as _, filterSearchResults as f };
