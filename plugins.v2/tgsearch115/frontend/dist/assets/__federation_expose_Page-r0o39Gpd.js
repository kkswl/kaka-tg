import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

function isCopyableResourceUrl(value) {
  const text = normalizeResourceUrl(value);
  if (!text) return false
  if (/^magnet:\?xt=urn:btih:[a-z0-9]+/i.test(text)) return true
  try {
    const parsed = new URL(text);
    return ['http:', 'https:'].includes(parsed.protocol) && Boolean(parsed.hostname)
  } catch {
    return false
  }
}

function normalizeResourceUrl(value) {
  // APIs sometimes serialize query delimiters as HTML entities.  Decode only
  // delimiters that are valid in a URL; never use the display title as a
  // fallback and never encode an already-complete resource URL again.
  return String(value || '').trim()
    .replace(/&amp;/gi, '&')
    .replace(/&#38;|&#x26;/gi, '&')
}

function getResourceLink(resource) {
  if (!resource || typeof resource !== 'object') return ''
  const candidates = [
    resource.share_url,
    resource.resource_url,
    resource.magnet,
    resource.download_url,
    resource.enclosure,
    resource.page_url,
    resource.url,
    resource.link,
  ];
  for (const candidate of candidates) {
    const text = normalizeResourceUrl(candidate);
    if (isCopyableResourceUrl(text)) return text
  }
  return ''
}

function fallbackCopyText(text, documentRef = globalThis.document, windowRef = globalThis.window) {
  if (!documentRef?.createElement || !documentRef?.body?.appendChild) return false
  const scrollX = Number(windowRef?.scrollX) || 0;
  const scrollY = Number(windowRef?.scrollY) || 0;
  const textarea = documentRef.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.left = '0';
  textarea.style.top = '0';
  textarea.style.width = '1px';
  textarea.style.height = '1px';
  textarea.style.overflow = 'hidden';
  textarea.style.fontSize = '12pt';
  textarea.style.opacity = '0';
  textarea.style.pointerEvents = 'none';
  documentRef.body.appendChild(textarea);
  let copied = false;
  try {
    textarea.focus();
    textarea.select();
    if (typeof textarea.setSelectionRange === 'function') textarea.setSelectionRange(0, text.length);
    copied = documentRef.execCommand?.('copy') === true;
  } catch {
    copied = false;
  } finally {
    try { textarea.remove(); } catch { documentRef.body.removeChild?.(textarea); }
    try { windowRef?.scrollTo?.(scrollX, scrollY); } catch { /* Scroll restoration is best effort. */ }
  }
  return copied
}

async function copyTextWithFallback(text, options = {}) {
  const navigatorRef = options.navigatorRef ?? globalThis.navigator;
  const documentRef = options.documentRef ?? globalThis.document;
  const windowRef = options.windowRef ?? globalThis.window;
  // Some embedded/local-IP browsers expose Clipboard API despite a non-secure
  // origin. Invoke it immediately while the click gesture is active, then use
  // the legacy fallback only if the browser actually rejects the request.
  if (navigatorRef?.clipboard?.writeText) {
    try {
      await navigatorRef.clipboard.writeText(text);
      return true
    } catch {
      // HTTP/local-IP pages often expose Clipboard API but reject writes.
    }
  }
  return fallbackCopyText(text, documentRef, windowRef)
}

function openResourceLink(url, options = {}) {
  const text = String(url || '').trim();
  if (!isCopyableResourceUrl(text)) return false
  const windowRef = options.windowRef ?? globalThis.window;
  const documentRef = options.documentRef ?? globalThis.document;
  if (/^magnet:\?/i.test(text)) {
    if (!documentRef?.createElement || !documentRef?.body?.appendChild) return false
    const anchor = documentRef.createElement('a');
    anchor.href = text;
    anchor.style.display = 'none';
    documentRef.body.appendChild(anchor);
    try {
      anchor.click();
      return true
    } catch {
      return false
    } finally {
      try { anchor.remove(); } catch { documentRef.body.removeChild?.(anchor); }
    }
  }
  const opened = windowRef?.open?.(text, '_blank', 'noopener,noreferrer');
  if (opened) {
    try { opened.opener = null; } catch { /* Cross-window assignment is best effort. */ }
    return true
  }
  return false
}

function buildManualTransferPayload(shareUrl, target, useDefault = true) {
  const payload = { confirm: true, share_url: String(shareUrl || '').trim() };
  if (!useDefault) payload.target = String(target).trim() || '0';
  return payload
}

const {resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,withModifiers:_withModifiers,withKeys:_withKeys,normalizeClass:_normalizeClass,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createBlock:_createBlock,vShow:_vShow,withDirectives:_withDirectives,unref:_unref,vModelText:_vModelText} = await importShared('vue');

const _hoisted_1 = { class: "tg115-page" };
const _hoisted_2 = { class: "text-caption text-medium-emphasis ml-3 status-summary" };
const _hoisted_3 = { class: "text-h6" };
const _hoisted_4 = { class: "text-body-2" };
const _hoisted_5 = { class: "text-body-2" };
const _hoisted_6 = { class: "text-body-2" };
const _hoisted_7 = { class: "text-body-2" };
const _hoisted_8 = { class: "text-body-2" };
const _hoisted_9 = { class: "text-body-2" };
const _hoisted_10 = { class: "text-body-2" };
const _hoisted_11 = { class: "text-body-2" };
const _hoisted_12 = { class: "text-body-2" };
const _hoisted_13 = {
  key: 0,
  class: "text-caption text-warning"
};
const _hoisted_14 = {
  key: 0,
  class: "d-flex flex-wrap ga-2 mt-3"
};
const _hoisted_15 = {
  key: 0,
  class: "text-caption text-medium-emphasis mb-3"
};
const _hoisted_16 = { class: "d-flex align-center ga-2 flex-wrap" };
const _hoisted_17 = { class: "text-caption" };
const _hoisted_18 = { class: "text-caption text-medium-emphasis mt-1" };
const _hoisted_19 = {
  key: 0,
  class: "text-caption text-warning mt-1"
};
const _hoisted_20 = {
  key: 1,
  class: "text-caption text-medium-emphasis mt-1"
};
const _hoisted_21 = { key: 0 };
const _hoisted_22 = { key: 1 };
const _hoisted_23 = { key: 2 };
const _hoisted_24 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_25 = { class: "task-title" };
const _hoisted_26 = { class: "text-caption text-medium-emphasis" };
const _hoisted_27 = { class: "text-caption text-medium-emphasis" };
const _hoisted_28 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_29 = { key: 0 };
const _hoisted_30 = {
  key: 1,
  class: "text-caption text-error"
};
const _hoisted_31 = {
  key: 2,
  class: "text-caption text-warning"
};
const _hoisted_32 = {
  key: 3,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_33 = { class: "text-caption" };
const _hoisted_34 = { class: "text-right" };
const _hoisted_35 = {
  key: 0,
  class: "text-warning"
};
const _hoisted_36 = { class: "text-caption text-medium-emphasis" };
const _hoisted_37 = {
  class: "manual-search-shell",
  "data-testid": "manual-search-root"
};
const _hoisted_38 = {
  class: "manual-filter-row mb-2",
  "data-testid": "manual-source-filter"
};
const _hoisted_39 = { class: "manual-button-group" };
const _hoisted_40 = ["onClick"];
const _hoisted_41 = {
  class: "manual-search-toolbar",
  "data-testid": "manual-search-controls"
};
const _hoisted_42 = ["disabled"];
const _hoisted_43 = {
  class: "manual-filter-row mt-3 mb-2",
  "data-testid": "manual-resource-filter"
};
const _hoisted_44 = { class: "manual-button-group" };
const _hoisted_45 = ["onClick"];
const _hoisted_46 = {
  key: 0,
  class: "manual-count"
};
const _hoisted_47 = {
  key: 0,
  class: "manual-filter-row mb-3",
  "data-testid": "manual-detail-filter"
};
const _hoisted_48 = { class: "manual-filter-label" };
const _hoisted_49 = { class: "manual-button-group" };
const _hoisted_50 = ["onClick"];
const _hoisted_51 = {
  key: 1,
  class: "manual-source-summary"
};
const _hoisted_52 = {
  key: 3,
  class: "manual-loading",
  role: "status",
  "aria-live": "polite"
};
const _hoisted_53 = {
  key: 4,
  class: "manual-result-grid",
  "data-testid": "manual-search-results"
};
const _hoisted_54 = { class: "manual-result-badges" };
const _hoisted_55 = { class: "manual-badge" };
const _hoisted_56 = { class: "manual-badge" };
const _hoisted_57 = {
  key: 0,
  class: "manual-badge"
};
const _hoisted_58 = {
  key: 1,
  class: "manual-badge success"
};
const _hoisted_59 = { class: "manual-result-title" };
const _hoisted_60 = {
  key: 0,
  class: "manual-result-meta"
};
const _hoisted_61 = { class: "manual-result-text" };
const _hoisted_62 = { class: "manual-result-actions" };
const _hoisted_63 = ["onPointerdown", "onClick"];
const _hoisted_64 = ["onClick"];
const _hoisted_65 = ["onClick"];
const _hoisted_66 = {
  key: 5,
  class: "manual-empty-state"
};
const _hoisted_67 = { class: "frontend-build-info text-caption text-medium-emphasis mt-2" };
const _hoisted_68 = {
  key: 0,
  class: "manual-default-target"
};
const _hoisted_69 = {
  key: 1,
  class: "manual-directory-toolbar"
};
const _hoisted_70 = ["disabled"];
const _hoisted_71 = ["disabled"];
const _hoisted_72 = { class: "text-caption text-medium-emphasis" };
const _hoisted_73 = ["disabled"];
const _hoisted_74 = {
  key: 2,
  class: "manual-loading",
  role: "status"
};
const _hoisted_75 = {
  key: 3,
  class: "manual-directory-list"
};
const _hoisted_76 = ["onClick"];
const _hoisted_77 = {
  key: 4,
  class: "manual-empty-state"
};
const _hoisted_78 = { class: "text-caption text-medium-emphasis" };
const _hoisted_79 = ["value"];
const {computed,getCurrentInstance,nextTick,onMounted,onUnmounted,reactive,ref,watch} = await importShared('vue');
const FRONTEND_VERSION = "4.8.28";
const MANUAL_CACHE_KEY = "TgSearch115:manual-search:v2";
const FORCE_TIMELINE_CONFIRMATION = "强制清理诊断记录";
const _sfc_main = {
  __name: "Page",
  props: {
    pluginId: { type: String, default: "TgSearch115" },
    api: { type: Object, default: null }
  },
  emits: ["close", "back"],
  setup(__props, { emit: __emit }) {
    const FRONTEND_BUILD_ID = "v4.8.28-manual-transfer-params" ;
    const FRONTEND_BUILD_TIME = "2026-09-23T02:09:14.771Z" ;
    const props = __props;
    const emit = __emit;
    const instance = getCurrentInstance();
    const frontendVersion = FRONTEND_VERSION;
    const frontendBuildId = FRONTEND_BUILD_ID;
    const frontendBuildTime = FRONTEND_BUILD_TIME;
    function unwrapApiResponse(response) {
      let value = response;
      const seen = /* @__PURE__ */ new Set();
      for (let depth = 0; depth < 4; depth += 1) {
        if (!value || typeof value !== "object" || !value.data || typeof value.data !== "object" || seen.has(value.data)) break;
        seen.add(value.data);
        value = value.data;
      }
      return value;
    }
    const MANUAL_SOURCE_FILTERS = [
      { title: "全部", value: "all" },
      { title: "TG", value: "tg" },
      { title: "观影", value: "site" },
      { title: "PanSou", value: "pansou" },
      { title: "聚影", value: "juying" }
    ];
    const MANUAL_RESOURCE_FILTERS = [
      { title: "全部", value: "all" },
      { title: "磁力", value: "magnet" },
      { title: "网盘", value: "pan" }
    ];
    const MANUAL_MAGNET_FILTERS = [
      { title: "全部", value: "all" },
      { title: "720P", value: "720p" },
      { title: "1080P", value: "1080p" },
      { title: "中字1080P", value: "chs1080p" },
      { title: "4K", value: "4k" },
      { title: "中字4K", value: "chs4k" },
      { title: "原盘", value: "remux" },
      { title: "未知", value: "unknown" }
    ];
    const MANUAL_PAN_FILTERS = [
      { title: "全部", value: "all" },
      { title: "迅雷网盘", value: "xunlei" },
      { title: "百度网盘", value: "baidu" },
      { title: "夸克网盘", value: "quark" },
      { title: "天翼网盘", value: "cloud189" },
      { title: "115网盘", value: "115" },
      { title: "UC网盘", value: "uc" },
      { title: "阿里网盘", value: "aliyun" },
      { title: "123网盘", value: "123" },
      { title: "其他", value: "other" }
    ];
    const manualKeyword = ref("");
    const manualSource = ref("all");
    const manualResourceType = ref("all");
    const manualDetailFilter = ref("all");
    const manualSearching = ref(false);
    const manualSearched = ref(false);
    const manualResults = ref([]);
    const manualSourceStatus = ref({});
    const manualSourceStats = ref({});
    const manualMessage = ref("");
    const manualOk = ref(false);
    const manualProcessDialog = ref(false);
    const manualSelectedResult = ref(null);
    const manualSubscriptions = ref([]);
    const manualSubscribeId = ref(null);
    const manualTransferring = ref("");
    const manualTransferDialog = ref(false);
    const manualTransferResult = ref(null);
    const manualTransferPath = ref([{ cid: "0", name: "根目录" }]);
    const manualTransferDirectories = ref([]);
    const manualTransferLoading = ref(false);
    const manualTransferSubmitting = ref(false);
    const manualTransferUseDefault = ref(true);
    const manualCacheAvailable = ref(true);
    const manualCopyDialog = ref(false);
    const manualCopyUrl = ref("");
    const manualCopyInput = ref(null);
    const manualPointerCopyActive = ref(false);
    const manualDetailFilters = computed(() => manualResourceType.value === "magnet" ? MANUAL_MAGNET_FILTERS : MANUAL_PAN_FILTERS);
    const manualTransferPathText = computed(() => {
      const names = manualTransferPath.value.slice(1).map((part) => part.name);
      return names.length ? `/${names.join("/")}` : "/";
    });
    const manualFilteredResults = computed(() => {
      try {
        return manualResults.value.filter((item) => {
          if (manualResourceType.value === "magnet" && item.resource_kind !== "magnet") return false;
          if (manualResourceType.value === "pan" && item.resource_kind !== "pan") return false;
          if (manualDetailFilter.value === "all") return true;
          if (manualResourceType.value === "magnet") return item.quality_class === manualDetailFilter.value;
          if (manualResourceType.value === "pan") return item.pan_type === manualDetailFilter.value;
          return true;
        });
      } catch {
        return [];
      }
    });
    const manualSourceSummary = computed(() => {
      try {
        return Object.entries(manualSourceStatus.value || {}).map(([name, state]) => {
          const label = manualSourceLabel(name);
          if (state?.status === "success" || state?.status === "partial_success") return `${label} ${Number(state.count || 0)} 条`;
          if (state?.status === "disabled") return `${label} 已关闭`;
          return `${label} ${String(state?.message || "请求失败")}`;
        }).join(" · ");
      } catch {
        return "";
      }
    });
    function manualSafeText(value, fallback = "") {
      if (value === null || value === void 0) return fallback;
      try {
        return String(value);
      } catch {
        return fallback;
      }
    }
    function normalizeManualResult(value, index) {
      const item = value && typeof value === "object" && !Array.isArray(value) ? value : { title: manualSafeText(value) };
      const panType = manualSafeText(item.pan_type, "other").toLowerCase() || "other";
      const resourceKind = ["magnet", "pan"].includes(item.resource_kind) ? item.resource_kind : panType === "magnet" ? "magnet" : "pan";
      const title = manualSafeText(item.title || item.display_name, "未命名资源").slice(0, 500);
      const resolution = manualSafeText(item.resolution, "unknown").toLowerCase() || "unknown";
      const qualityClass = manualSafeText(item.quality_class, "unknown").toLowerCase() || "unknown";
      return {
        result_id: `manual-${index}-${manualSafeText(item.source, "unknown")}-${panType}`,
        title,
        display_name: manualSafeText(item.display_name || title, title).slice(0, 500),
        source: manualSafeText(item.source, "unknown"),
        upstream_source: manualSafeText(item.upstream_source),
        pan_type: panType,
        resource_kind: resourceKind,
        text: manualSafeText(item.text || title, title).slice(0, 2e3),
        meta: manualSafeText(item.meta).slice(0, 500),
        resolution,
        quality_class: qualityClass,
        has_chinese_subtitle: item.has_chinese_subtitle === true,
        receive_code: manualSafeText(item.receive_code).slice(0, 16),
        share_url: getResourceLink(item)
      };
    }
    function manualSessionStore() {
      if (!manualCacheAvailable.value) return null;
      try {
        return window.sessionStorage;
      } catch {
        manualCacheAvailable.value = false;
        return null;
      }
    }
    function persistManualSession() {
      if (!manualSearched.value) return;
      try {
        manualSessionStore()?.setItem(MANUAL_CACHE_KEY, JSON.stringify({
          keyword: manualKeyword.value,
          source: manualSource.value,
          resourceType: manualResourceType.value,
          detailFilter: manualDetailFilter.value,
          results: manualResults.value.slice(0, 500),
          sourceStatus: manualSourceStatus.value,
          sourceStats: manualSourceStats.value,
          message: manualMessage.value,
          ok: manualOk.value
        }));
      } catch {
        manualCacheAvailable.value = false;
      }
    }
    function restoreManualSession() {
      try {
        const raw = manualSessionStore()?.getItem(MANUAL_CACHE_KEY);
        if (!raw) return;
        const cached = JSON.parse(raw);
        if (!cached || !Array.isArray(cached.results)) return;
        manualKeyword.value = manualSafeText(cached.keyword);
        manualSource.value = manualSafeText(cached.source, "all");
        manualResourceType.value = manualSafeText(cached.resourceType, "all");
        manualDetailFilter.value = manualSafeText(cached.detailFilter, "all");
        manualResults.value = cached.results.slice(0, 500).map(normalizeManualResult);
        manualSourceStatus.value = cached.sourceStatus && typeof cached.sourceStatus === "object" ? cached.sourceStatus : {};
        manualSourceStats.value = cached.sourceStats && typeof cached.sourceStats === "object" ? cached.sourceStats : {};
        manualMessage.value = manualSafeText(cached.message);
        manualOk.value = cached.ok === true;
        manualSearched.value = true;
      } catch {
        try {
          manualSessionStore()?.removeItem(MANUAL_CACHE_KEY);
        } catch {
          manualCacheAvailable.value = false;
        }
      }
    }
    function setManualResourceType(value) {
      manualResourceType.value = value;
      manualDetailFilter.value = "all";
    }
    async function runManualSearch() {
      const value = manualSafeText(manualKeyword.value).trim();
      if (!value) {
        manualMessage.value = "请输入搜索关键字";
        manualOk.value = false;
        return;
      }
      if (!props.api?.get) {
        manualMessage.value = "搜索 API 未就绪";
        manualOk.value = false;
        return;
      }
      manualSearching.value = true;
      manualSearched.value = true;
      manualMessage.value = "";
      manualResults.value = [];
      manualSourceStatus.value = {};
      manualSourceStats.value = {};
      try {
        const data = unwrapApiResponse(await props.api.get(`plugin/${PID.value}/search?keyword=${encodeURIComponent(value)}&source=${manualSource.value}`));
        if (!data || typeof data !== "object") throw new TypeError("invalid-response");
        const sourceItems = Array.isArray(data.items) ? data.items : Array.isArray(data.results) ? data.results : Array.isArray(data.resources) ? data.resources : [];
        manualResults.value = sourceItems.map(normalizeManualResult);
        manualSourceStatus.value = data.source_status && typeof data.source_status === "object" ? data.source_status : {};
        manualSourceStats.value = data.source_stats && typeof data.source_stats === "object" ? data.source_stats : {};
        manualOk.value = data.success !== false;
        manualMessage.value = manualSafeText(data.warning || data.message || (manualOk.value ? `找到 ${manualResults.value.length} 条资源` : "搜索失败，可重试"));
      } catch (error) {
        manualResults.value = [];
        manualOk.value = false;
        manualMessage.value = safeRequestError(error, "搜索请求失败，可重试");
      } finally {
        manualSearching.value = false;
        persistManualSession();
      }
    }
    function manualSourceLabel(value) {
      return { tg: "TG", site: "观影", pansou: "PanSou", juying: "聚影" }[value] || value || "未知";
    }
    function manualPanLabel(value) {
      return { "115": "115网盘", quark: "夸克网盘", baidu: "百度网盘", aliyun: "阿里网盘", xunlei: "迅雷网盘", cloud189: "天翼网盘", uc: "UC网盘", "123": "123网盘", magnet: "磁力" }[value] || "其他";
    }
    function manualQualityLabel(item) {
      return { "4k": "4K", "1080p": "1080P", "720p": "720P" }[item?.resolution] || "未知";
    }
    function manualFullUrl(item) {
      let url = getResourceLink(item);
      if (item?.pan_type === "115" && item?.receive_code && !/[?&](password|receive_code|pwd)=/.test(url)) url += `${url.includes("?") ? "&" : "?"}password=${item.receive_code}`;
      return url;
    }
    async function copyManualResult(item) {
      const url = manualFullUrl(item).trim();
      if (!isCopyableResourceUrl(url)) {
        showSnack("该资源没有有效链接", "warning");
        return false;
      }
      try {
        const copied = await copyTextWithFallback(url);
        if (copied) {
          manualCopyDialog.value = false;
          showSnack("链接已复制", "success");
          return true;
        }
      } catch {
      }
      manualCopyUrl.value = url;
      manualCopyDialog.value = true;
      showSnack("复制失败，请长按或手动复制", "warning");
      return false;
    }
    function startManualCopy(item) {
      manualPointerCopyActive.value = true;
      void copyManualResult(item);
      window.setTimeout(() => {
        manualPointerCopyActive.value = false;
      }, 450);
    }
    function handleManualCopyClick(item) {
      if (manualPointerCopyActive.value) return;
      void copyManualResult(item);
    }
    async function selectManualCopyText() {
      await nextTick();
      const input = manualCopyInput.value;
      if (!input) return;
      try {
        input.focus({ preventScroll: true });
        input.select();
        input.setSelectionRange?.(0, input.value.length);
      } catch {
      }
    }
    async function retryManualCopy() {
      const url = manualCopyUrl.value.trim();
      if (!isCopyableResourceUrl(url)) {
        showSnack("该资源没有有效链接", "warning");
        return;
      }
      const copied = await copyTextWithFallback(url);
      if (copied) {
        manualCopyDialog.value = false;
        showSnack("链接已复制", "success");
        return;
      }
      showSnack("仍无法自动复制，请长按或手动复制", "warning");
      await selectManualCopyText();
    }
    function openManualResult(item) {
      const url = manualFullUrl(item).trim();
      if (!isCopyableResourceUrl(url)) {
        showSnack("该资源没有有效链接", "warning");
        return;
      }
      if (!openResourceLink(url)) showSnack("链接无法打开，请检查浏览器弹窗或磁力关联设置", "warning");
    }
    async function loadManualTransferDirectories(cid) {
      if (!props.api?.get) {
        showSnack("目录服务不可用", "error");
        return;
      }
      manualTransferLoading.value = true;
      manualTransferDirectories.value = [];
      try {
        const response = await props.api.get(`plugin/${PID.value}/dirs?cid=${encodeURIComponent(cid)}`);
        const data = unwrapApiResponse(response);
        if (data?.success) manualTransferDirectories.value = Array.isArray(data.dirs) ? data.dirs : [];
        else showSnack(manualSafeText(data?.message, "获取目录失败"), "error");
      } catch (error) {
        const data = unwrapApiResponse(error?.response?.data);
        showSnack(manualSafeText(data?.message, safeRequestError(error, "获取目录失败")), "error");
      } finally {
        manualTransferLoading.value = false;
      }
    }
    async function openManualTransferDialog(item) {
      const url = manualFullUrl(item).trim();
      if (!isCopyableResourceUrl(url) || item?.pan_type !== "115") {
        showSnack("该资源没有有效的 115 分享链接", "warning");
        return;
      }
      manualTransferResult.value = item;
      manualTransferPath.value = [{ cid: "0", name: "根目录" }];
      manualTransferUseDefault.value = true;
      manualTransferDirectories.value = [];
      manualTransferDialog.value = true;
    }
    function closeManualTransferDialog() {
      if (manualTransferSubmitting.value) return;
      manualTransferDialog.value = false;
      manualTransferResult.value = null;
      manualTransferDirectories.value = [];
    }
    async function navigateManualTransferInto(directory) {
      const cid = manualSafeText(directory?.cid).trim();
      const name = manualSafeText(directory?.name).trim();
      if (!cid || !name) return;
      manualTransferPath.value.push({ cid, name });
      await loadManualTransferDirectories(cid);
    }
    async function chooseManualTransferDirectory() {
      manualTransferUseDefault.value = false;
      manualTransferPath.value = [{ cid: "0", name: "根目录" }];
      await loadManualTransferDirectories("0");
    }
    function useManualTransferDefault() {
      manualTransferUseDefault.value = true;
      manualTransferDirectories.value = [];
    }
    async function navigateManualTransferUp() {
      if (manualTransferPath.value.length > 1) manualTransferPath.value.pop();
      await loadManualTransferDirectories(manualTransferPath.value.at(-1)?.cid || "0");
    }
    async function navigateManualTransferRoot() {
      manualTransferPath.value = [{ cid: "0", name: "根目录" }];
      await loadManualTransferDirectories("0");
    }
    async function submitManualTransfer() {
      const item = manualTransferResult.value;
      if (!item || !props.api?.post || manualTransferSubmitting.value) return;
      const shareUrl = manualFullUrl(item).trim();
      if (!isCopyableResourceUrl(shareUrl) || item.pan_type !== "115") {
        showSnack("该资源没有有效的 115 分享链接", "warning");
        return;
      }
      manualTransferSubmitting.value = true;
      try {
        const payload = buildManualTransferPayload(
          shareUrl,
          manualTransferPath.value.at(-1)?.cid || "0",
          manualTransferUseDefault.value
        );
        const response = await props.api.post(`plugin/${PID.value}/manual/transfer`, payload);
        const data = unwrapApiResponse(response);
        const success = data?.success === true;
        showSnack(formatManualTransferMessage(data, success), success ? "success" : "error");
        if (success) {
          manualTransferSubmitting.value = false;
          closeManualTransferDialog();
        }
      } catch (error) {
        const data = unwrapApiResponse(error?.response?.data);
        showSnack(formatManualTransferMessage(data, false, safeRequestError(error, "转存请求失败，请重试")), "error");
      } finally {
        manualTransferSubmitting.value = false;
      }
    }
    function formatManualTransferMessage(data, success, fallback = "") {
      const message = manualSafeText(data?.message, fallback || (success ? "转存成功" : "转存失败"));
      const stage = manualSafeText(data?.diagnostic?.stage);
      const labels = {
        share_url: "分享链接",
        cookie: "115 登录状态",
        target_cid: "目标目录",
        share_snap: "读取分享目录",
        file_id: "分享文件标识",
        share_receive: "115 接收资源"
      };
      return !success && labels[stage] && !message.includes(labels[stage]) ? `${labels[stage]}：${message}` : message;
    }
    async function loadManualSubscriptions() {
      if (!props.api?.get) return;
      try {
        const data = unwrapApiResponse(await props.api.get(`plugin/${PID.value}/manual/subscriptions`));
        manualSubscriptions.value = Array.isArray(data?.items) ? data.items : [];
      } catch {
        manualSubscriptions.value = [];
      }
    }
    async function openManualProcessDialog(item) {
      manualSelectedResult.value = item;
      manualSubscribeId.value = null;
      if (!manualSubscriptions.value.length) await loadManualSubscriptions();
      manualProcessDialog.value = true;
    }
    function closeManualProcessDialog() {
      manualProcessDialog.value = false;
      manualSelectedResult.value = null;
      manualSubscribeId.value = null;
    }
    async function submitManualResult() {
      const item = manualSelectedResult.value;
      if (!item || !manualSubscribeId.value || !props.api?.post) return;
      manualTransferring.value = item.result_id;
      try {
        const data = unwrapApiResponse(await props.api.post(`plugin/${PID.value}/manual/process`, {
          subscribe_id: manualSubscribeId.value,
          confirm: true,
          candidate: {
            share_url: manualFullUrl(item),
            receive_code: item.receive_code || "",
            title: item.title || item.display_name || "",
            text: item.text || "",
            pan_type: item.pan_type || "",
            source: item.source || ""
          }
        }));
        const success = data?.success === true || data?.code === 0;
        showSnack(manualSafeText(data?.message, success ? "任务提交成功" : "提交失败"), success ? "success" : "error");
        if (success) closeManualProcessDialog();
      } catch (error) {
        showSnack(safeRequestError(error, "提交请求失败，可重试"), "error");
      } finally {
        manualTransferring.value = "";
      }
    }
    watch([manualSource, manualResourceType, manualDetailFilter], persistManualSession);
    restoreManualSession();
    function closePage() {
      try {
        if (instance?.vnode?.props?.onClose) {
          emit("close");
          return;
        }
        if (instance?.vnode?.props?.onBack) {
          emit("back");
          return;
        }
      } catch {
      }
      try {
        window.history.back();
      } catch {
      }
    }
    const PID = computed(() => props.pluginId || "TgSearch115");
    const config = reactive({ enabled: false, tg_search_enabled: true, p115_cookie: "", offline_allow_cancel: false, tg_channels: [] });
    const runtime = reactive({
      plugin_version: "",
      scheduler: { running: false, last_run: "", next_run: "", scanned_count: 0, queue_size: 0 },
      recognition: { waiting: 0, active: 0, max_active: 0, last_wait_seconds: 0, retries: 0, identity_unavailable: 0, stopping: false },
      sources: {},
      tg: { enabled: true, configured_channels: 0, enabled_channels: 0, status: "empty" },
      pansou: { enabled: false, last_request: "", last_success: "", last_error: "", result_count: 0, type_counts: {}, cache_hits: 0, deduplicated: 0, rule_passed: 0, identity_checked: 0, safe_candidates: 0 },
      tasks: []
    });
    const diagnosticsExpanded = ref(false);
    const timeline = reactive({ total: 0, active_count: 0, terminal_count: 0, items: [] });
    const clearingTimeline = ref(false);
    const forceClearingTimeline = ref(false);
    const forceTimelineDialog = ref(false);
    const forceTimelineConfirmation = ref("");
    const sourceHealth = ref({});
    const healthLabels = computed(() => Object.entries(sourceHealth.value || {}).map(([source, item]) => `${{ tg: "TG", site: "观影", pansou: "PanSou", juying: "聚影" }[source] || source} ${item.score}分`).join(" · "));
    const statusLoading = ref(false);
    const statusExpanded = ref(false);
    const statusText = computed(() => {
      const tgState = runtime.tg?.status === "disabled" ? "已关闭" : runtime.tg?.status === "empty" ? "已启用但无频道" : "已启用";
      return `${config.enabled ? "运行中" : "已停用"} · TG ${tgState} · 115 ${loginOk.value ? "已登录" : "未登录"} · PanSou ${runtime.pansou.enabled ? "已启用" : "未启用"}`;
    });
    const versionMismatch = computed(() => !!runtime.plugin_version && runtime.plugin_version !== FRONTEND_VERSION);
    const tasksExpanded = ref(false);
    const retryingBtih = ref("");
    const clearingTasks = ref(false);
    const clearTasksDialog = ref(false);
    const ACTIVE_TASK_STATUSES = /* @__PURE__ */ new Set(["waiting", "submitted", "downloading", "pending_organize"]);
    const terminalTaskCount = computed(() => runtime.tasks.filter((task) => !ACTIVE_TASK_STATUSES.has(task.status)).length);
    const activeTaskCount = computed(() => runtime.tasks.filter((task) => ACTIVE_TASK_STATUSES.has(task.status)).length);
    let statusTimer = null;
    const sourceStates = computed(() => Object.entries(runtime.sources || {}).map(([name, state]) => ({ name, ...state })));
    const channelCount = computed(() => Array.isArray(config.tg_channels) ? config.tg_channels.length : 0);
    const loginOk = computed(() => {
      const c = String(config.p115_cookie || "");
      return c.length > 0 && ["UID", "CID", "SEID"].every((k) => c.includes(k + "="));
    });
    const snack = ref(false);
    const snackColor = ref("");
    const snackText = ref("");
    function formatTime(value) {
      if (!value) return "尚未运行";
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
    }
    function formatWaitDuration(value) {
      const started = new Date(value || "");
      if (Number.isNaN(started.getTime())) return "未知";
      const minutes = Math.max(0, Math.floor((Date.now() - started.getTime()) / 6e4));
      if (minutes < 60) return `${minutes} 分钟`;
      const hours = Math.floor(minutes / 60);
      return `${hours} 小时 ${minutes % 60} 分钟`;
    }
    function taskStatusLabel(status) {
      return {
        waiting: "等待中",
        submitted: "已提交",
        downloading: "下载中",
        pending_organize: "待整理",
        completed: "已完成",
        failed: "失败",
        timed_out: "超时",
        cancelled: "已取消"
      }[status] || status || "未知";
    }
    function taskStatusColor(status) {
      return {
        waiting: "info",
        submitted: "info",
        downloading: "primary",
        pending_organize: "warning",
        completed: "success",
        failed: "error",
        timed_out: "warning",
        cancelled: "grey"
      }[status] || "grey";
    }
    function timelineStatus(status) {
      return { running: "处理中", waiting_organize: "等待整理", completed: "已完成", recovered: "已恢复", failed: "失败", skipped: "已跳过" }[status] || status || "未知";
    }
    function timelineColor(status) {
      return { running: "primary", waiting_organize: "warning", completed: "success", recovered: "info", failed: "error", skipped: "grey" }[status] || "grey";
    }
    async function clearTimeline() {
      if (!props.api?.post) {
        showSnack("诊断接口未就绪，请重新加载插件页面后重试", "error");
        return;
      }
      const terminalCount = Number(timeline.terminal_count || 0);
      if (!terminalCount) {
        showSnack("没有可清理的终态诊断记录", "info");
        return;
      }
      if (!window.confirm(`仅删除本地终态诊断记录；不会删除 115 文件、不会取消下载、不会修改订阅。
将清理当前列表中的 ${terminalCount} 条终态记录，是否继续？`)) return;
      clearingTimeline.value = true;
      try {
        const res = await props.api.post(`plugin/${PID.value}/runtime/timeline/clear`, { confirm: true });
        const raw = res?.data || res;
        const data = raw?.data?.success !== void 0 ? raw.data : raw;
        showSnack(data?.message || "清除失败", data?.success ? "success" : "error");
        if (data?.success) await loadRuntimeStatus();
      } catch (error) {
        const message = error?.response?.data?.message;
        showSnack(message || "清除诊断记录请求失败，可重试", "error");
      } finally {
        clearingTimeline.value = false;
      }
    }
    function openForceTimelineDialog() {
      if (forceClearingTimeline.value) return;
      forceTimelineConfirmation.value = "";
      forceTimelineDialog.value = true;
    }
    function closeForceTimelineDialog() {
      if (forceClearingTimeline.value) return;
      forceTimelineDialog.value = false;
      forceTimelineConfirmation.value = "";
    }
    async function forceClearTimeline() {
      if (!props.api?.post || forceClearingTimeline.value) return;
      if (forceTimelineConfirmation.value !== FORCE_TIMELINE_CONFIRMATION) {
        showSnack("请输入完整确认文字", "warning");
        return;
      }
      forceClearingTimeline.value = true;
      try {
        const response = await props.api.post(`plugin/${PID.value}/runtime/timeline/clear`, {
          confirm: true,
          force: true,
          confirmation_text: FORCE_TIMELINE_CONFIRMATION
        });
        const data = unwrapApiResponse(response);
        showSnack(data?.message || (data?.success ? "诊断记录已清理" : "强制清理失败"), data?.success ? "success" : "error");
        if (data?.success) {
          forceTimelineDialog.value = false;
          forceTimelineConfirmation.value = "";
          await loadRuntimeStatus();
        }
      } catch (error) {
        showSnack(safeRequestError(error, "强制清理请求失败"), "error");
      } finally {
        forceClearingTimeline.value = false;
        if (!forceTimelineDialog.value) forceTimelineConfirmation.value = "";
      }
    }
    async function loadRuntimeStatus() {
      if (!props.api?.get) return;
      statusLoading.value = true;
      try {
        const res = await props.api.get(`plugin/${PID.value}/runtime/status`);
        const data = res && typeof res === "object" && "data" in res && ("success" in res || "code" in res) ? res.data : res;
        if (data?.success) {
          runtime.plugin_version = String(data.plugin_version || "");
          Object.assign(runtime.scheduler, data.scheduler || {});
          Object.assign(runtime.recognition, data.recognition || {});
          runtime.sources = data.sources || {};
          Object.assign(runtime.pansou, data.pansou || {});
          runtime.tasks = Array.isArray(data.tasks) ? data.tasks : [];
          Object.assign(timeline, data.timeline || { total: 0, active_count: 0, terminal_count: 0, items: [] });
          sourceHealth.value = data.source_health || {};
        }
      } catch {
      } finally {
        statusLoading.value = false;
      }
    }
    async function retryTask(task) {
      if (!props.api?.post || !task?.btih) return;
      retryingBtih.value = task.btih;
      try {
        const res = await props.api.post(`plugin/${PID.value}/tasks/retry`, { btih: task.btih });
        const data = res && typeof res === "object" && "data" in res && ("success" in res || "code" in res) ? res.data : res;
        showSnack(data?.message || (data?.success ? "订阅已恢复" : "重试失败"), data?.success ? "success" : "error");
        await loadRuntimeStatus();
      } catch (e) {
        showSnack(safeRequestError(e, "重试请求失败"), "error");
      } finally {
        retryingBtih.value = "";
      }
    }
    async function cancelTask(task) {
      if (!props.api?.post || !task?.btih) return;
      try {
        const res = await props.api.post(`plugin/${PID.value}/tasks/cancel`, { btih: task.btih });
        const data = res && typeof res === "object" && "data" in res && ("success" in res || "code" in res) ? res.data : res;
        showSnack(data?.message || "取消失败", data?.success ? "success" : "error");
        await loadRuntimeStatus();
      } catch (e) {
        showSnack(safeRequestError(e, "取消请求失败"), "error");
      }
    }
    function openClearTasksDialog() {
      if (clearingTasks.value) return;
      clearTasksDialog.value = true;
    }
    async function clearTasksConfirmed() {
      if (!props.api?.post || clearingTasks.value) return;
      clearingTasks.value = true;
      try {
        const res = await props.api.post(`plugin/${PID.value}/tasks/clear`, { confirm: true });
        const data = res && typeof res === "object" && "data" in res && ("success" in res || "code" in res) ? res.data : res;
        showSnack(data?.message || "清除失败", data?.success ? "success" : "error");
        if (data?.success) {
          clearTasksDialog.value = false;
          await loadRuntimeStatus();
        }
      } catch (e) {
        showSnack(safeRequestError(e, "清除任务记录失败"), "error");
      } finally {
        clearingTasks.value = false;
      }
    }
    function showSnack(text, color) {
      snackText.value = text;
      snackColor.value = color;
      snack.value = true;
    }
    function safeRequestError(error, fallback) {
      const status = Number(error?.response?.status || error?.status || 0);
      if (status >= 400 && status <= 599) return `${fallback}（HTTP ${status}）`;
      const code = String(error?.code || "").toUpperCase();
      if (code.includes("TIMEOUT") || code === "ECONNABORTED") return `${fallback}（请求超时）`;
      return fallback;
    }
    onMounted(async () => {
      if (!props.api?.get) return;
      try {
        const res = await props.api.get(`plugin/${PID.value}/config/get`);
        const cfg = res && typeof res === "object" && "data" in res && ("success" in res || "code" in res) ? res.data : res;
        if (cfg && typeof cfg === "object") Object.assign(config, cfg);
      } catch {
      }
      await loadRuntimeStatus();
      statusTimer = setInterval(loadRuntimeStatus, 3e4);
    });
    onUnmounted(() => {
      if (statusTimer) clearInterval(statusTimer);
    });
    return (_ctx, _cache) => {
      const _component_v_icon = _resolveComponent("v-icon");
      const _component_v_spacer = _resolveComponent("v-spacer");
      const _component_v_tooltip = _resolveComponent("v-tooltip");
      const _component_v_btn = _resolveComponent("v-btn");
      const _component_v_card_title = _resolveComponent("v-card-title");
      const _component_v_divider = _resolveComponent("v-divider");
      const _component_v_col = _resolveComponent("v-col");
      const _component_v_row = _resolveComponent("v-row");
      const _component_v_chip = _resolveComponent("v-chip");
      const _component_v_card_text = _resolveComponent("v-card-text");
      const _component_v_expand_transition = _resolveComponent("v-expand-transition");
      const _component_v_card = _resolveComponent("v-card");
      const _component_v_table = _resolveComponent("v-table");
      const _component_v_card_actions = _resolveComponent("v-card-actions");
      const _component_v_dialog = _resolveComponent("v-dialog");
      const _component_v_text_field = _resolveComponent("v-text-field");
      const _component_v_alert = _resolveComponent("v-alert");
      const _component_v_select = _resolveComponent("v-select");
      const _component_v_snackbar = _resolveComponent("v-snackbar");
      return _openBlock(), _createElementBlock("div", _hoisted_1, [
        _createVNode(_component_v_card, {
          variant: "outlined",
          rounded: "lg",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, {
              class: "d-flex align-center px-4 py-3 status-toggle",
              role: "button",
              tabindex: "0",
              "aria-expanded": statusExpanded.value,
              "aria-label": "展开或收起运行状态",
              onClick: _cache[0] || (_cache[0] = ($event) => statusExpanded.value = !statusExpanded.value),
              onKeydown: _cache[1] || (_cache[1] = _withKeys(($event) => statusExpanded.value = !statusExpanded.value, ["enter"]))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-robot-outline",
                  color: "primary",
                  class: "mr-2"
                }),
                _cache[16] || (_cache[16] = _createTextVNode(" 运行状态 ", -1)),
                _createElementVNode("span", _hoisted_2, _toDisplayString(statusText.value), 1),
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  icon: "",
                  variant: "text",
                  size: "small",
                  "aria-label": "关闭",
                  onClick: _withModifiers(closePage, ["stop"])
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, { icon: "mdi-close" }),
                    _createVNode(_component_v_tooltip, {
                      activator: "parent",
                      location: "top"
                    }, {
                      default: _withCtx(() => [..._cache[15] || (_cache[15] = [
                        _createTextVNode("关闭", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_icon, {
                  icon: statusExpanded.value ? "mdi-chevron-up" : "mdi-chevron-down"
                }, null, 8, ["icon"])
              ]),
              _: 1
            }, 8, ["aria-expanded"]),
            _createVNode(_component_v_expand_transition, null, {
              default: _withCtx(() => [
                _withDirectives(_createElementVNode("div", null, [
                  _createVNode(_component_v_divider),
                  _createVNode(_component_v_card_text, { class: "px-4 py-4" }, {
                    default: _withCtx(() => [
                      _createVNode(_component_v_row, null, {
                        default: _withCtx(() => [
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[17] || (_cache[17] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TG 频道数", -1)),
                              _createElementVNode("div", _hoisted_3, _toDisplayString(channelCount.value), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[18] || (_cache[18] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "115 登录", -1)),
                              _createElementVNode("div", {
                                class: _normalizeClass(["text-h6", loginOk.value ? "text-success" : "text-medium-emphasis"])
                              }, _toDisplayString(loginOk.value ? "已登录" : "未登录"), 3)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [..._cache[19] || (_cache[19] = [
                              _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "订阅处理", -1),
                              _createElementVNode("div", { class: "text-h6" }, "插件来源优先", -1)
                            ])]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[20] || (_cache[20] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "上次周期扫描", -1)),
                              _createElementVNode("div", _hoisted_4, _toDisplayString(formatTime(runtime.scheduler.last_run)), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[21] || (_cache[21] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "下次周期扫描", -1)),
                              _createElementVNode("div", _hoisted_5, _toDisplayString(formatTime(runtime.scheduler.next_run)), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[22] || (_cache[22] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "队列 / 本轮订阅", -1)),
                              _createElementVNode("div", _hoisted_6, _toDisplayString(runtime.scheduler.queue_size || 0) + " / " + _toDisplayString(runtime.scheduler.scanned_count || 0), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[23] || (_cache[23] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TMDB 识别队列", -1)),
                              _createElementVNode("div", _hoisted_7, "等待 " + _toDisplayString(runtime.recognition.waiting || 0) + " / 活动 " + _toDisplayString(runtime.recognition.active || 0), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[24] || (_cache[24] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TMDB 最大并发", -1)),
                              _createElementVNode("div", _hoisted_8, _toDisplayString(runtime.recognition.max_active || 0) + " / 1", 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[25] || (_cache[25] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "识别恢复", -1)),
                              _createElementVNode("div", _hoisted_9, "重试 " + _toDisplayString(runtime.recognition.retries || 0) + " / 暂不可用 " + _toDisplayString(runtime.recognition.identity_unavailable || 0), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[26] || (_cache[26] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "PanSou", -1)),
                              _createElementVNode("div", _hoisted_10, _toDisplayString(runtime.pansou.enabled ? "已启用" : "未启用") + " · 最近 " + _toDisplayString(runtime.pansou.result_count || 0) + " 条", 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[27] || (_cache[27] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "PanSou 处理", -1)),
                              _createElementVNode("div", _hoisted_11, "去重 " + _toDisplayString(runtime.pansou.deduplicated || 0) + " / 规则 " + _toDisplayString(runtime.pansou.rule_passed || 0) + " / 安全 " + _toDisplayString(runtime.pansou.safe_candidates || 0), 1)
                            ]),
                            _: 1
                          }),
                          _createVNode(_component_v_col, {
                            cols: "12",
                            md: "4"
                          }, {
                            default: _withCtx(() => [
                              _cache[28] || (_cache[28] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "PanSou 最近状态", -1)),
                              _createElementVNode("div", _hoisted_12, _toDisplayString(formatTime(runtime.pansou.last_success)) + " · 缓存 " + _toDisplayString(runtime.pansou.cache_hits || 0), 1),
                              runtime.pansou.last_error ? (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(runtime.pansou.last_error), 1)) : _createCommentVNode("", true)
                            ]),
                            _: 1
                          })
                        ]),
                        _: 1
                      }),
                      sourceStates.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_14, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceStates.value, (source) => {
                          return _openBlock(), _createBlock(_component_v_chip, {
                            key: source.name,
                            size: "small",
                            variant: "tonal",
                            color: source.cooldown_seconds > 0 ? "warning" : "success"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(source.name) + " · " + _toDisplayString(source.cooldown_seconds > 0 ? `冷却 ${source.cooldown_seconds}s` : "可用"), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"]);
                        }), 128))
                      ])) : _createCommentVNode("", true)
                    ]),
                    _: 1
                  })
                ], 512), [
                  [_vShow, statusExpanded.value]
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_card, {
          variant: "outlined",
          rounded: "lg",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, {
              class: "d-flex align-center px-4 py-3 task-toggle",
              onClick: _cache[2] || (_cache[2] = ($event) => diagnosticsExpanded.value = !diagnosticsExpanded.value)
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-chart-timeline-variant",
                  color: "primary",
                  class: "mr-2"
                }),
                _cache[31] || (_cache[31] = _createTextVNode("订阅处理诊断 ", -1)),
                _createVNode(_component_v_chip, {
                  size: "x-small",
                  variant: "tonal",
                  class: "ml-2"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(timeline.total || 0), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  size: "x-small",
                  variant: "text",
                  loading: clearingTimeline.value,
                  "aria-label": "清理已结束的订阅诊断记录",
                  onClick: _withModifiers(clearTimeline, ["stop"])
                }, {
                  default: _withCtx(() => [..._cache[29] || (_cache[29] = [
                    _createTextVNode("清理已结束", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_btn, {
                  size: "x-small",
                  variant: "text",
                  color: "error",
                  loading: forceClearingTimeline.value,
                  "aria-label": "强制清理全部订阅诊断记录",
                  onClick: _withModifiers(openForceTimelineDialog, ["stop"])
                }, {
                  default: _withCtx(() => [..._cache[30] || (_cache[30] = [
                    _createTextVNode("强制清理", -1)
                  ])]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_icon, {
                  icon: diagnosticsExpanded.value ? "mdi-chevron-up" : "mdi-chevron-down"
                }, null, 8, ["icon"])
              ]),
              _: 1
            }),
            _createVNode(_component_v_expand_transition, null, {
              default: _withCtx(() => [
                _withDirectives(_createElementVNode("div", null, [
                  _createVNode(_component_v_divider),
                  _createVNode(_component_v_card_text, { class: "px-4 py-3" }, {
                    default: _withCtx(() => [
                      healthLabels.value ? (_openBlock(), _createElementBlock("div", _hoisted_15, _toDisplayString(healthLabels.value), 1)) : _createCommentVNode("", true),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timeline.items, (run) => {
                        return _openBlock(), _createElementBlock("div", {
                          key: run.run_id,
                          class: "mb-3"
                        }, [
                          _createElementVNode("div", _hoisted_16, [
                            _createVNode(_component_v_chip, {
                              size: "x-small",
                              color: timelineColor(run.status)
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(timelineStatus(run.status)), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"]),
                            _createElementVNode("strong", null, [
                              _createTextVNode(_toDisplayString(run.title), 1),
                              run.year ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                _createTextVNode("（" + _toDisplayString(run.year) + "）", 1)
                              ], 64)) : _createCommentVNode("", true),
                              run.season !== null && run.season !== void 0 ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                _createTextVNode(" S" + _toDisplayString(String(run.season).padStart(2, "0")), 1)
                              ], 64)) : _createCommentVNode("", true)
                            ]),
                            _createElementVNode("span", _hoisted_17, _toDisplayString(run.stage), 1)
                          ]),
                          _createElementVNode("div", _hoisted_18, _toDisplayString(run.events?.map((e) => e.summary).filter(Boolean).join(" → ") || run.reason || "等待诊断事件"), 1),
                          run.organize_wait_reason ? (_openBlock(), _createElementBlock("div", _hoisted_19, "当前：" + _toDisplayString(run.organize_wait_reason), 1)) : _createCommentVNode("", true),
                          run.btih_prefix || run.last_reconcile_at ? (_openBlock(), _createElementBlock("div", _hoisted_20, [
                            run.btih_prefix ? (_openBlock(), _createElementBlock("span", _hoisted_21, "BTIH " + _toDisplayString(run.btih_prefix) + "…", 1)) : _createCommentVNode("", true),
                            run.last_reconcile_at ? (_openBlock(), _createElementBlock("span", _hoisted_22, " · 最近检查 " + _toDisplayString(formatTime(run.last_reconcile_at)), 1)) : _createCommentVNode("", true),
                            run.status === "waiting_organize" ? (_openBlock(), _createElementBlock("span", _hoisted_23, " · 已等待 " + _toDisplayString(formatWaitDuration(run.started_at)), 1)) : _createCommentVNode("", true)
                          ])) : _createCommentVNode("", true)
                        ]);
                      }), 128)),
                      !timeline.items?.length ? (_openBlock(), _createElementBlock("div", _hoisted_24, "尚无订阅处理诊断记录")) : _createCommentVNode("", true)
                    ]),
                    _: 1
                  })
                ], 512), [
                  [_vShow, diagnosticsExpanded.value]
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        runtime.tasks.length ? (_openBlock(), _createBlock(_component_v_card, {
          key: 0,
          variant: "outlined",
          rounded: "lg",
          class: "mb-4"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, {
              class: "d-flex align-center px-4 py-3 task-toggle",
              onClick: _cache[3] || (_cache[3] = ($event) => tasksExpanded.value = !tasksExpanded.value)
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-cloud-sync-outline",
                  color: "primary",
                  class: "mr-2"
                }),
                _cache[35] || (_cache[35] = _createTextVNode(" 磁力下载任务 ", -1)),
                _createVNode(_component_v_chip, {
                  size: "x-small",
                  variant: "tonal",
                  class: "ml-2"
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(runtime.tasks.length), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  size: "small",
                  variant: "outlined",
                  color: "error",
                  "prepend-icon": "mdi-delete-sweep-outline",
                  "aria-label": "清除已结束的磁力下载任务记录",
                  loading: clearingTasks.value,
                  onClick: _withModifiers(openClearTasksDialog, ["stop"])
                }, {
                  default: _withCtx(() => [
                    _cache[33] || (_cache[33] = _createTextVNode("清除记录 ", -1)),
                    _createVNode(_component_v_tooltip, {
                      activator: "parent",
                      location: "top"
                    }, {
                      default: _withCtx(() => [..._cache[32] || (_cache[32] = [
                        _createTextVNode("清除已结束的本地任务记录", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_btn, {
                  icon: "",
                  variant: "text",
                  size: "small",
                  loading: statusLoading.value,
                  onClick: _withModifiers(loadRuntimeStatus, ["stop"])
                }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, { icon: "mdi-refresh" }),
                    _createVNode(_component_v_tooltip, {
                      activator: "parent",
                      location: "top"
                    }, {
                      default: _withCtx(() => [..._cache[34] || (_cache[34] = [
                        _createTextVNode("刷新任务状态", -1)
                      ])]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_icon, {
                  icon: tasksExpanded.value ? "mdi-chevron-up" : "mdi-chevron-down"
                }, null, 8, ["icon"])
              ]),
              _: 1
            }),
            _createVNode(_component_v_expand_transition, null, {
              default: _withCtx(() => [
                _withDirectives(_createElementVNode("div", null, [
                  _createVNode(_component_v_divider),
                  _cache[39] || (_cache[39] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "115 直接磁力状态来自插件脱敏台账；手动取消只对可识别的当前任务可用", -1)),
                  _createVNode(_component_v_table, { density: "compact" }, {
                    default: _withCtx(() => [
                      _cache[38] || (_cache[38] = _createElementVNode("thead", null, [
                        _createElementVNode("tr", null, [
                          _createElementVNode("th", null, "资源"),
                          _createElementVNode("th", null, "状态"),
                          _createElementVNode("th", null, "提交时间"),
                          _createElementVNode("th", { class: "text-right" }, "操作")
                        ])
                      ], -1)),
                      _createElementVNode("tbody", null, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(runtime.tasks, (task) => {
                          return _openBlock(), _createElementBlock("tr", {
                            key: `${task.btih}-${task.submitted_at}`
                          }, [
                            _createElementVNode("td", null, [
                              _createElementVNode("div", _hoisted_25, _toDisplayString(task.title), 1),
                              _createElementVNode("div", _hoisted_26, "115 直接磁力 · task " + _toDisplayString(String(task.task_id || "").slice(0, 12)) + "...", 1),
                              _createElementVNode("div", _hoisted_27, "BTIH " + _toDisplayString(String(task.btih || "").slice(0, 12)) + "...", 1),
                              task.target_cid ? (_openBlock(), _createElementBlock("div", _hoisted_28, [
                                _createTextVNode(" 115 目标 cid " + _toDisplayString(task.target_cid), 1),
                                task.download_name ? (_openBlock(), _createElementBlock("span", _hoisted_29, " · " + _toDisplayString(task.download_name), 1)) : _createCommentVNode("", true)
                              ])) : _createCommentVNode("", true),
                              task.error_message ? (_openBlock(), _createElementBlock("div", _hoisted_30, _toDisplayString(task.error_message), 1)) : _createCommentVNode("", true),
                              task.organize_wait_reason ? (_openBlock(), _createElementBlock("div", _hoisted_31, _toDisplayString(task.organize_wait_reason), 1)) : _createCommentVNode("", true),
                              task.last_reconcile_at ? (_openBlock(), _createElementBlock("div", _hoisted_32, "最近对账 " + _toDisplayString(formatTime(task.last_reconcile_at)), 1)) : _createCommentVNode("", true)
                            ]),
                            _createElementVNode("td", null, [
                              _createVNode(_component_v_chip, {
                                size: "x-small",
                                variant: "tonal",
                                color: taskStatusColor(task.status)
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(taskStatusLabel(task.status)), 1)
                                ]),
                                _: 2
                              }, 1032, ["color"])
                            ]),
                            _createElementVNode("td", _hoisted_33, _toDisplayString(formatTime(task.submitted_at)), 1),
                            _createElementVNode("td", _hoisted_34, [
                              ["failed", "timed_out"].includes(task.status) ? (_openBlock(), _createBlock(_component_v_btn, {
                                key: 0,
                                icon: "",
                                variant: "text",
                                size: "small",
                                color: "primary",
                                loading: retryingBtih.value === task.btih,
                                onClick: ($event) => retryTask(task)
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_v_icon, { icon: "mdi-replay" }),
                                  _createVNode(_component_v_tooltip, {
                                    activator: "parent",
                                    location: "top"
                                  }, {
                                    default: _withCtx(() => [..._cache[36] || (_cache[36] = [
                                      _createTextVNode("重试任务", -1)
                                    ])]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              }, 8, ["loading", "onClick"])) : _createCommentVNode("", true),
                              config.offline_allow_cancel && task.source === "115_direct" && ["submitted", "downloading", "pending_organize"].includes(task.status) ? (_openBlock(), _createBlock(_component_v_btn, {
                                key: 1,
                                icon: "",
                                variant: "text",
                                size: "small",
                                color: "error",
                                onClick: ($event) => cancelTask(task)
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_v_icon, { icon: "mdi-cancel" }),
                                  _createVNode(_component_v_tooltip, {
                                    activator: "parent",
                                    location: "top"
                                  }, {
                                    default: _withCtx(() => [..._cache[37] || (_cache[37] = [
                                      _createTextVNode("取消任务并恢复订阅", -1)
                                    ])]),
                                    _: 1
                                  })
                                ]),
                                _: 1
                              }, 8, ["onClick"])) : _createCommentVNode("", true)
                            ])
                          ]);
                        }), 128))
                      ])
                    ]),
                    _: 1
                  })
                ], 512), [
                  [_vShow, tasksExpanded.value]
                ])
              ]),
              _: 1
            })
          ]),
          _: 1
        })) : _createCommentVNode("", true),
        _createVNode(_component_v_dialog, {
          modelValue: clearTasksDialog.value,
          "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => clearTasksDialog.value = $event),
          "max-width": "480",
          persistent: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: "mdi-alert-outline",
                      color: "error",
                      class: "mr-2"
                    }),
                    _cache[40] || (_cache[40] = _createTextVNode("确认清除任务记录 ", -1))
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _createElementVNode("p", null, "将清除 " + _toDisplayString(terminalTaskCount.value) + " 条已结束的本地磁力下载任务记录。", 1),
                    activeTaskCount.value ? (_openBlock(), _createElementBlock("p", _hoisted_35, "当前有 " + _toDisplayString(activeTaskCount.value) + " 条任务仍在处理，服务器会拒绝此次清除。", 1)) : _createCommentVNode("", true),
                    _cache[41] || (_cache[41] = _createElementVNode("p", { class: "text-medium-emphasis" }, "不会删除 115 文件，不会取消离线下载，也不会修改订阅。", -1))
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, { class: "px-6 pb-4" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      disabled: clearingTasks.value,
                      onClick: _cache[4] || (_cache[4] = ($event) => clearTasksDialog.value = false)
                    }, {
                      default: _withCtx(() => [..._cache[42] || (_cache[42] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode(_component_v_btn, {
                      color: "error",
                      variant: "flat",
                      loading: clearingTasks.value,
                      onClick: clearTasksConfirmed
                    }, {
                      default: _withCtx(() => [..._cache[43] || (_cache[43] = [
                        _createTextVNode("确认清除", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode(_component_v_dialog, {
          modelValue: forceTimelineDialog.value,
          "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => forceTimelineDialog.value = $event),
          "max-width": "520",
          persistent: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, { class: "d-flex align-center" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: "mdi-alert-outline",
                      color: "error",
                      class: "mr-2"
                    }),
                    _cache[44] || (_cache[44] = _createTextVNode("强制清理订阅诊断记录 ", -1))
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _cache[45] || (_cache[45] = _createElementVNode("p", null, "此操作只删除本地订阅处理诊断记录，包括进行中的显示状态。", -1)),
                    _cache[46] || (_cache[46] = _createElementVNode("p", { class: "text-medium-emphasis" }, "不会取消下载、删除 115 文件、清除磁力任务或修改订阅。", -1)),
                    _createVNode(_component_v_text_field, {
                      modelValue: forceTimelineConfirmation.value,
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => forceTimelineConfirmation.value = $event),
                      label: "请输入：强制清理诊断记录",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": "",
                      class: "mt-3"
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, { class: "px-6 pb-4" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      disabled: forceClearingTimeline.value,
                      onClick: closeForceTimelineDialog
                    }, {
                      default: _withCtx(() => [..._cache[47] || (_cache[47] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode(_component_v_btn, {
                      color: "error",
                      variant: "flat",
                      loading: forceClearingTimeline.value,
                      disabled: forceTimelineConfirmation.value !== FORCE_TIMELINE_CONFIRMATION,
                      onClick: forceClearTimeline
                    }, {
                      default: _withCtx(() => [..._cache[48] || (_cache[48] = [
                        _createTextVNode("确认强制清理", -1)
                      ])]),
                      _: 1
                    }, 8, ["loading", "disabled"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode(_component_v_card, {
          variant: "outlined",
          rounded: "lg"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, { class: "d-flex align-center px-4 py-3" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-magnify",
                  color: "primary",
                  class: "mr-2"
                }),
                _cache[49] || (_cache[49] = _createTextVNode("手动搜索 ", -1)),
                _createVNode(_component_v_spacer),
                _createElementVNode("span", _hoisted_36, _toDisplayString(_unref(frontendVersion)) + " / " + _toDisplayString(runtime.plugin_version || "后端版本未知"), 1)
              ]),
              _: 1
            }),
            _createVNode(_component_v_divider),
            _createVNode(_component_v_card_text, { class: "manual-search-body" }, {
              default: _withCtx(() => [
                versionMismatch.value ? (_openBlock(), _createBlock(_component_v_alert, {
                  key: 0,
                  type: "warning",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  default: _withCtx(() => [..._cache[50] || (_cache[50] = [
                    _createTextVNode(" 插件后端与前端资源版本不一致，请刷新 MoviePilot 插件资源缓存。 ", -1)
                  ])]),
                  _: 1
                })) : _createCommentVNode("", true),
                _createElementVNode("div", _hoisted_37, [
                  _createElementVNode("div", _hoisted_38, [
                    _cache[51] || (_cache[51] = _createElementVNode("span", { class: "manual-filter-label" }, "搜索范围", -1)),
                    _createElementVNode("div", _hoisted_39, [
                      (_openBlock(), _createElementBlock(_Fragment, null, _renderList(MANUAL_SOURCE_FILTERS, (item) => {
                        return _createElementVNode("button", {
                          key: item.value,
                          type: "button",
                          class: _normalizeClass(["manual-filter-button", { active: manualSource.value === item.value }]),
                          onClick: ($event) => manualSource.value = item.value
                        }, _toDisplayString(item.title), 11, _hoisted_40);
                      }), 64))
                    ])
                  ]),
                  _cache[53] || (_cache[53] = _createElementVNode("label", {
                    for: "tg115-manual-keyword",
                    class: "manual-input-label"
                  }, "搜索关键字（影片名 + 年份）", -1)),
                  _createElementVNode("div", _hoisted_41, [
                    _withDirectives(_createElementVNode("input", {
                      id: "tg115-manual-keyword",
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => manualKeyword.value = $event),
                      class: "manual-search-input",
                      type: "search",
                      autocomplete: "off",
                      "data-testid": "manual-search-input",
                      onKeyup: _withKeys(runManualSearch, ["enter"])
                    }, null, 544), [
                      [_vModelText, manualKeyword.value]
                    ]),
                    _createElementVNode("button", {
                      class: "manual-search-button",
                      type: "button",
                      "data-testid": "manual-search-button",
                      disabled: manualSearching.value,
                      onClick: runManualSearch
                    }, _toDisplayString(manualSearching.value ? "搜索中…" : "搜索"), 9, _hoisted_42)
                  ]),
                  _createElementVNode("div", _hoisted_43, [
                    _cache[52] || (_cache[52] = _createElementVNode("span", { class: "manual-filter-label" }, "资源", -1)),
                    _createElementVNode("div", _hoisted_44, [
                      (_openBlock(), _createElementBlock(_Fragment, null, _renderList(MANUAL_RESOURCE_FILTERS, (item) => {
                        return _createElementVNode("button", {
                          key: item.value,
                          type: "button",
                          class: _normalizeClass(["manual-filter-button", { active: manualResourceType.value === item.value }]),
                          onClick: ($event) => setManualResourceType(item.value)
                        }, _toDisplayString(item.title), 11, _hoisted_45);
                      }), 64))
                    ]),
                    manualResults.value.length ? (_openBlock(), _createElementBlock("span", _hoisted_46, _toDisplayString(manualFilteredResults.value.length) + "/" + _toDisplayString(manualResults.value.length) + " 条", 1)) : _createCommentVNode("", true)
                  ]),
                  manualResourceType.value !== "all" ? (_openBlock(), _createElementBlock("div", _hoisted_47, [
                    _createElementVNode("span", _hoisted_48, _toDisplayString(manualResourceType.value === "magnet" ? "画质" : "网盘"), 1),
                    _createElementVNode("div", _hoisted_49, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(manualDetailFilters.value, (item) => {
                        return _openBlock(), _createElementBlock("button", {
                          key: item.value,
                          type: "button",
                          class: _normalizeClass(["manual-filter-button", { active: manualDetailFilter.value === item.value }]),
                          onClick: ($event) => manualDetailFilter.value = item.value
                        }, _toDisplayString(item.title), 11, _hoisted_50);
                      }), 128))
                    ])
                  ])) : _createCommentVNode("", true),
                  manualSourceSummary.value ? (_openBlock(), _createElementBlock("div", _hoisted_51, _toDisplayString(manualSourceSummary.value), 1)) : _createCommentVNode("", true),
                  manualMessage.value ? (_openBlock(), _createElementBlock("div", {
                    key: 2,
                    class: _normalizeClass(["manual-message", manualOk.value ? "success" : "error"])
                  }, _toDisplayString(manualMessage.value), 3)) : _createCommentVNode("", true),
                  manualSearching.value ? (_openBlock(), _createElementBlock("div", _hoisted_52, "搜索中…")) : manualFilteredResults.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_53, [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(manualFilteredResults.value, (item) => {
                      return _openBlock(), _createElementBlock("article", {
                        key: item.result_id,
                        class: "manual-result-card"
                      }, [
                        _createElementVNode("div", _hoisted_54, [
                          _createElementVNode("span", _hoisted_55, _toDisplayString(manualPanLabel(item.pan_type)), 1),
                          _createElementVNode("span", _hoisted_56, _toDisplayString(manualSourceLabel(item.source)), 1),
                          item.resolution !== "unknown" ? (_openBlock(), _createElementBlock("span", _hoisted_57, _toDisplayString(manualQualityLabel(item)), 1)) : _createCommentVNode("", true),
                          item.has_chinese_subtitle ? (_openBlock(), _createElementBlock("span", _hoisted_58, "中文字幕")) : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("strong", _hoisted_59, _toDisplayString(item.display_name || item.title), 1),
                        item.meta ? (_openBlock(), _createElementBlock("div", _hoisted_60, _toDisplayString(item.meta), 1)) : _createCommentVNode("", true),
                        _createElementVNode("div", _hoisted_61, _toDisplayString(item.text || item.title), 1),
                        _createElementVNode("div", _hoisted_62, [
                          _createElementVNode("button", {
                            type: "button",
                            class: "manual-link-button",
                            onPointerdown: _withModifiers(($event) => startManualCopy(item), ["stop", "prevent"]),
                            onClick: _withModifiers(($event) => handleManualCopyClick(item), ["stop", "prevent"])
                          }, "复制链接", 40, _hoisted_63),
                          _createElementVNode("button", {
                            type: "button",
                            class: "manual-link-button",
                            onClick: _withModifiers(($event) => openManualResult(item), ["stop", "prevent"])
                          }, "打开链接", 8, _hoisted_64),
                          ["115", "magnet"].includes(item.pan_type) ? (_openBlock(), _createElementBlock("button", {
                            key: 0,
                            type: "button",
                            class: "manual-action-button",
                            onClick: ($event) => item.pan_type === "115" ? openManualTransferDialog(item) : openManualProcessDialog(item)
                          }, _toDisplayString(item.pan_type === "magnet" ? "离线到115" : "转存"), 9, _hoisted_65)) : _createCommentVNode("", true)
                        ])
                      ]);
                    }), 128))
                  ])) : manualSearched.value && !manualSearching.value ? (_openBlock(), _createElementBlock("div", _hoisted_66, _toDisplayString(manualResults.value.length ? "当前筛选条件下没有资源，可切换筛选查看" : "所有可用来源均未找到符合条件的资源"), 1)) : _createCommentVNode("", true)
                ]),
                _createElementVNode("div", _hoisted_67, " 前端构建 " + _toDisplayString(_unref(frontendBuildId)) + " · " + _toDisplayString(_unref(frontendBuildTime)), 1)
              ]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_v_dialog, {
          modelValue: manualProcessDialog.value,
          "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => manualProcessDialog.value = $event),
          "max-width": "520",
          persistent: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, null, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, null, {
                  default: _withCtx(() => [..._cache[54] || (_cache[54] = [
                    _createTextVNode("确认正式操作", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _cache[55] || (_cache[55] = _createElementVNode("div", { class: "text-body-2 mb-3" }, "请选择对应的 MoviePilot 订阅。提交前仍会执行规则和媒体身份确认。", -1)),
                    _createVNode(_component_v_select, {
                      modelValue: manualSubscribeId.value,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => manualSubscribeId.value = $event),
                      items: manualSubscriptions.value,
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
                      disabled: !!manualTransferring.value,
                      onClick: closeManualProcessDialog
                    }, {
                      default: _withCtx(() => [..._cache[56] || (_cache[56] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      disabled: !manualSubscribeId.value,
                      loading: !!manualTransferring.value,
                      onClick: submitManualResult
                    }, {
                      default: _withCtx(() => [..._cache[57] || (_cache[57] = [
                        _createTextVNode("确认提交", -1)
                      ])]),
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
        _createVNode(_component_v_dialog, {
          modelValue: manualTransferDialog.value,
          "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => manualTransferDialog.value = $event),
          "max-width": "560",
          persistent: ""
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { rounded: "lg" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, { class: "d-flex align-center px-4 py-3" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_icon, {
                      icon: "mdi-folder-open",
                      class: "mr-2"
                    }),
                    _cache[58] || (_cache[58] = _createTextVNode("转存到 115 ", -1))
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_divider),
                _createVNode(_component_v_card_text, { class: "manual-directory-body" }, {
                  default: _withCtx(() => [
                    manualTransferUseDefault.value ? (_openBlock(), _createElementBlock("div", _hoisted_68, [
                      _cache[59] || (_cache[59] = _createElementVNode("div", null, "将使用插件设置中绑定的 115 默认目录。", -1)),
                      _createElementVNode("button", {
                        type: "button",
                        class: "manual-link-button",
                        onClick: chooseManualTransferDirectory
                      }, "选择其他目录")
                    ])) : (_openBlock(), _createElementBlock("div", _hoisted_69, [
                      _createElementVNode("button", {
                        type: "button",
                        class: "manual-link-button",
                        disabled: manualTransferLoading.value,
                        onClick: useManualTransferDefault
                      }, "使用默认目录", 8, _hoisted_70),
                      _createElementVNode("button", {
                        type: "button",
                        class: "manual-link-button",
                        disabled: manualTransferLoading.value,
                        onClick: navigateManualTransferRoot
                      }, "根目录", 8, _hoisted_71),
                      _createElementVNode("span", _hoisted_72, _toDisplayString(manualTransferPathText.value), 1),
                      manualTransferPath.value.length > 1 ? (_openBlock(), _createElementBlock("button", {
                        key: 0,
                        type: "button",
                        class: "manual-link-button",
                        disabled: manualTransferLoading.value,
                        onClick: navigateManualTransferUp
                      }, "上一级", 8, _hoisted_73)) : _createCommentVNode("", true)
                    ])),
                    !manualTransferUseDefault.value && manualTransferLoading.value ? (_openBlock(), _createElementBlock("div", _hoisted_74, "目录加载中…")) : !manualTransferUseDefault.value && manualTransferDirectories.value.length ? (_openBlock(), _createElementBlock("div", _hoisted_75, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(manualTransferDirectories.value, (directory) => {
                        return _openBlock(), _createElementBlock("button", {
                          key: directory.cid,
                          type: "button",
                          class: "manual-directory-item",
                          onClick: ($event) => navigateManualTransferInto(directory)
                        }, "📁 " + _toDisplayString(directory.name), 9, _hoisted_76);
                      }), 128))
                    ])) : !manualTransferUseDefault.value ? (_openBlock(), _createElementBlock("div", _hoisted_77, "当前目录没有子目录，可直接转存到这里")) : _createCommentVNode("", true)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_divider),
                _createVNode(_component_v_card_actions, { class: "px-4 py-3" }, {
                  default: _withCtx(() => [
                    _createElementVNode("span", _hoisted_78, "目标：" + _toDisplayString(manualTransferUseDefault.value ? "绑定的默认目录" : manualTransferPathText.value), 1),
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      disabled: manualTransferSubmitting.value,
                      onClick: closeManualTransferDialog
                    }, {
                      default: _withCtx(() => [..._cache[60] || (_cache[60] = [
                        _createTextVNode("取消", -1)
                      ])]),
                      _: 1
                    }, 8, ["disabled"]),
                    _createVNode(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      loading: manualTransferSubmitting.value,
                      onClick: submitManualTransfer
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(manualTransferUseDefault.value ? "转存到默认目录" : "转存到此目录"), 1)
                      ]),
                      _: 1
                    }, 8, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"]),
        _createVNode(_component_v_dialog, {
          modelValue: manualCopyDialog.value,
          "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => manualCopyDialog.value = $event),
          "max-width": "620"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card, { rounded: "lg" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_card_title, null, {
                  default: _withCtx(() => [..._cache[61] || (_cache[61] = [
                    _createTextVNode("手动复制链接", -1)
                  ])]),
                  _: 1
                }),
                _createVNode(_component_v_card_text, null, {
                  default: _withCtx(() => [
                    _cache[62] || (_cache[62] = _createElementVNode("div", { class: "text-body-2 mb-3" }, "自动复制被当前浏览器拒绝。可长按或选择下面完整链接后手动复制。", -1)),
                    _createElementVNode("textarea", {
                      ref_key: "manualCopyInput",
                      ref: manualCopyInput,
                      class: "manual-copy-textarea",
                      value: manualCopyUrl.value,
                      readonly: "",
                      "aria-label": "完整资源链接",
                      onFocus: selectManualCopyText
                    }, null, 40, _hoisted_79)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_card_actions, { class: "px-4 pb-4" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_v_spacer),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      onClick: selectManualCopyText
                    }, {
                      default: _withCtx(() => [..._cache[63] || (_cache[63] = [
                        _createTextVNode("全选", -1)
                      ])]),
                      _: 1
                    }),
                    _createVNode(_component_v_btn, {
                      color: "primary",
                      variant: "flat",
                      onClick: retryManualCopy
                    }, {
                      default: _withCtx(() => [..._cache[64] || (_cache[64] = [
                        _createTextVNode("再次复制", -1)
                      ])]),
                      _: 1
                    }),
                    _createVNode(_component_v_btn, {
                      variant: "text",
                      onClick: _cache[12] || (_cache[12] = ($event) => manualCopyDialog.value = false)
                    }, {
                      default: _withCtx(() => [..._cache[65] || (_cache[65] = [
                        _createTextVNode("关闭", -1)
                      ])]),
                      _: 1
                    })
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
          "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => snack.value = $event),
          color: snackColor.value,
          timeout: 2500,
          location: "top"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(snackText.value), 1)
          ]),
          _: 1
        }, 8, ["modelValue", "color"])
      ]);
    };
  }
};
const Page = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-c28c3b42"]]);

export { Page as default };
