import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, f as filterSearchResults, M as ManualSearch } from './ManualSearch-DGjtKvZV.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createElementVNode:_createElementVNode,createTextVNode:_createTextVNode,withCtx:_withCtx,withModifiers:_withModifiers,withKeys:_withKeys,normalizeClass:_normalizeClass,openBlock:_openBlock,createElementBlock:_createElementBlock,createCommentVNode:_createCommentVNode,renderList:_renderList,Fragment:_Fragment,createBlock:_createBlock,vShow:_vShow,withDirectives:_withDirectives,unref:_unref} = await importShared('vue');


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
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_20 = { class: "task-title" };
const _hoisted_21 = { class: "text-caption text-medium-emphasis" };
const _hoisted_22 = { class: "text-caption text-medium-emphasis" };
const _hoisted_23 = {
  key: 0,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_24 = { key: 0 };
const _hoisted_25 = {
  key: 1,
  class: "text-caption text-error"
};
const _hoisted_26 = { class: "text-caption" };
const _hoisted_27 = { class: "text-right" };
const _hoisted_28 = {
  key: 0,
  class: "text-warning"
};

const {computed,getCurrentInstance,onMounted,onUnmounted,reactive,ref} = await importShared('vue');

const CACHE_KEY = 'tg115_search_cache';

const _sfc_main = {
  __name: 'Page',
  props: {
  pluginId: { type: String, default: 'TgSearch115' },
  api: { type: Object, default: null },
},
  emits: ['close', 'back'],
  setup(__props, { emit: __emit }) {

const props = __props;
const emit = __emit;
const instance = getCurrentInstance();

function closePage() {
  try {
    if (instance?.vnode?.props?.onClose) {
      emit('close');
      return
    }
    if (instance?.vnode?.props?.onBack) {
      emit('back');
      return
    }
  } catch {}
  try {
    window.history.back();
  } catch {}
}

const PID = computed(() => props.pluginId || 'TgSearch115');

// ---- 配置 / 状态 ----
const config = reactive({ enabled: false, tg_search_enabled: true, p115_cookie: '', offline_allow_cancel: false, tg_channels: [] });
const runtime = reactive({
  scheduler: { running: false, last_run: '', next_run: '', scanned_count: 0, queue_size: 0 },
  recognition: { waiting: 0, active: 0, max_active: 0, last_wait_seconds: 0, retries: 0, identity_unavailable: 0, stopping: false },
  sources: {},
  tg: { enabled: true, configured_channels: 0, enabled_channels: 0, status: 'empty' },
  pansou: { enabled: false, last_request: '', last_success: '', last_error: '', result_count: 0, type_counts: {}, cache_hits: 0, deduplicated: 0, rule_passed: 0, identity_checked: 0, safe_candidates: 0 },
  tasks: [],
});
const diagnosticsExpanded = ref(false);
const timeline = reactive({ total: 0, active_count: 0, terminal_count: 0, items: [] });
const clearingTimeline = ref(false);
const sourceHealth = ref({});
const healthLabels = computed(() => Object.entries(sourceHealth.value || {}).map(([source, item]) => `${({ tg: 'TG', site: '观影', pansou: 'PanSou', juying: '聚影' })[source] || source} ${item.score}分`).join(' · '));
const statusLoading = ref(false);
const statusExpanded = ref(false);
const statusText = computed(() => {
  const tgState = runtime.tg?.status === 'disabled'
    ? '已关闭'
    : runtime.tg?.status === 'empty'
      ? '已启用但无频道'
      : '已启用';
  return `${config.enabled ? '运行中' : '已停用'} · TG ${tgState} · 115 ${loginOk.value ? '已登录' : '未登录'} · PanSou ${runtime.pansou.enabled ? '已启用' : '未启用'}`
});
const tasksExpanded = ref(false);
const retryingBtih = ref('');
const clearingTasks = ref(false);
const clearTasksDialog = ref(false);
const ACTIVE_TASK_STATUSES = new Set(['waiting', 'submitted', 'downloading', 'pending_organize']);
const terminalTaskCount = computed(() => runtime.tasks.filter(task => !ACTIVE_TASK_STATUSES.has(task.status)).length);
const activeTaskCount = computed(() => runtime.tasks.filter(task => ACTIVE_TASK_STATUSES.has(task.status)).length);
let statusTimer = null;
const sourceStates = computed(() => Object.entries(runtime.sources || {}).map(([name, state]) => ({ name, ...state })));
const channelCount = computed(() => (Array.isArray(config.tg_channels) ? config.tg_channels.length : 0));
const loginOk = computed(() => {
  const c = String(config.p115_cookie || '');
  return c.length > 0 && ['UID', 'CID', 'SEID'].every((k) => c.includes(k + '='))
});

// ---- 搜索 ----
// 搜索结果持久化：保存到 localStorage，下次进详情页自动恢复，新搜索覆盖
function loadCache() {
  try {
    const c = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
    return c && Array.isArray(c.results) ? c : null
  } catch { return null }
}
const _init = loadCache();
ref(_init ? _init.keyword : '');
ref('all');
const resourceFilter = ref(_init?.resource_filter || 'all');
const qualityFilter = ref(_init?.quality_filter || 'all');
const results = ref(_init ? _init.results : []);
ref(_init ? _init.offset || 0 : 0);
ref(_init ? !!_init.has_more : false);
ref(false);
ref(false);
ref(_init ? `已恢复上次搜索「${_init.keyword}」的结果（${_init.results.length} 条）` : '');
ref(!!_init);
ref(-1);
computed(() => results.value.some(
  (r) => r.pan_type === '115' || r.pan_type === 'magnet',
));
computed(() => filterSearchResults(
  results.value,
  resourceFilter.value,
  qualityFilter.value,
));
// snackbar
const snack = ref(false);
const snackColor = ref('');
const snackText = ref('');
function formatTime(value) {
  if (!value) return '尚未运行'
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}
function taskStatusLabel(status) {
  return {
    waiting: '等待中', submitted: '已提交', downloading: '下载中', pending_organize: '待整理',
    completed: '已完成', failed: '失败', timed_out: '超时', cancelled: '已取消',
  }[status] || status || '未知'
}
function taskStatusColor(status) {
  return {
    waiting: 'info', submitted: 'info', downloading: 'primary', pending_organize: 'warning',
    completed: 'success', failed: 'error', timed_out: 'warning', cancelled: 'grey',
  }[status] || 'grey'
}
function timelineStatus(status) { return ({ running: '处理中', waiting_organize: '等待整理', completed: '已完成', recovered: '已恢复', failed: '失败', skipped: '已跳过' })[status] || status || '未知' }
function timelineColor(status) { return ({ running: 'primary', waiting_organize: 'warning', completed: 'success', recovered: 'info', failed: 'error', skipped: 'grey' })[status] || 'grey' }
async function clearTimeline() {
  if (!props.api?.post) { showSnack('诊断接口未就绪，请重新加载插件页面后重试', 'error'); return }
  const terminalCount = Number(timeline.terminal_count || 0);
  if (!terminalCount) { showSnack('没有可清理的终态诊断记录', 'info'); return }
  if (!window.confirm(`仅删除本地终态诊断记录；不会删除 115 文件、不会取消下载、不会修改订阅。\n将清理当前列表中的 ${terminalCount} 条终态记录，是否继续？`)) return
  clearingTimeline.value = true;
  try {
    const res = await props.api.post(`plugin/${PID.value}/runtime/timeline/clear`, { confirm: true });
    const raw = res?.data || res;
    const data = raw?.data?.success !== undefined ? raw.data : raw;
    showSnack(data?.message || '清除失败', data?.success ? 'success' : 'error');
    if (data?.success) await loadRuntimeStatus();
  } catch (error) {
    const message = error?.response?.data?.message;
    showSnack(message || '清除诊断记录请求失败，可重试', 'error');
  } finally { clearingTimeline.value = false; }
}

async function loadRuntimeStatus() {
  if (!props.api?.get) return
  statusLoading.value = true;
  try {
    const res = await props.api.get(`plugin/${PID.value}/runtime/status`);
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res;
    if (data?.success) {
      Object.assign(runtime.scheduler, data.scheduler || {});
      Object.assign(runtime.recognition, data.recognition || {});
      runtime.sources = data.sources || {};
      Object.assign(runtime.pansou, data.pansou || {});
      runtime.tasks = Array.isArray(data.tasks) ? data.tasks : [];
      Object.assign(timeline, data.timeline || { total: 0, active_count: 0, terminal_count: 0, items: [] });
      sourceHealth.value = data.source_health || {};
    }
  } catch {
    // Status refresh is non-blocking; search actions continue to work.
  } finally {
    statusLoading.value = false;
  }
}

async function retryTask(task) {
  if (!props.api?.post || !task?.btih) return
  retryingBtih.value = task.btih;
  try {
    const res = await props.api.post(`plugin/${PID.value}/tasks/retry`, { btih: task.btih });
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res;
    showSnack(data?.message || (data?.success ? '订阅已恢复' : '重试失败'), data?.success ? 'success' : 'error');
    await loadRuntimeStatus();
  } catch (e) {
    showSnack('重试异常：' + (e?.message || e), 'error');
  } finally {
    retryingBtih.value = '';
  }
}
async function cancelTask(task) {
  if (!props.api?.post || !task?.btih) return
  try {
    const res = await props.api.post(`plugin/${PID.value}/tasks/cancel`, { btih: task.btih });
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res;
    showSnack(data?.message || '取消失败', data?.success ? 'success' : 'error');
    await loadRuntimeStatus();
  } catch (e) {
    showSnack('取消异常：' + (e?.message || e), 'error');
  }
}

function openClearTasksDialog() {
  if (clearingTasks.value) return
  clearTasksDialog.value = true;
}

async function clearTasksConfirmed() {
  if (!props.api?.post || clearingTasks.value) return
  clearingTasks.value = true;
  try {
    const res = await props.api.post(`plugin/${PID.value}/tasks/clear`, { confirm: true });
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res;
    showSnack(data?.message || '清除失败', data?.success ? 'success' : 'error');
    if (data?.success) {
      clearTasksDialog.value = false;
      await loadRuntimeStatus();
    }
  } catch (e) {
    showSnack(e?.response?.data?.message || e?.message || '清除任务记录失败', 'error');
  } finally {
    clearingTasks.value = false;
  }
}

function showSnack(text, color) {
  snackText.value = text;
  snackColor.value = color;
  snack.value = true;
}

onMounted(async () => {
  if (!props.api?.get) return
  try {
    const res = await props.api.get(`plugin/${PID.value}/config/get`);
    const cfg = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res;
    if (cfg && typeof cfg === 'object') Object.assign(config, cfg);
  } catch {
    // 静默
  }
  await loadRuntimeStatus();
  statusTimer = setInterval(loadRuntimeStatus, 30000);
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
  _resolveComponent("v-text-field");
  _resolveComponent("v-btn-toggle");
  _resolveComponent("v-card-item");
  const _component_v_snackbar = _resolveComponent("v-snackbar");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
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
          onClick: _cache[0] || (_cache[0] = $event => (statusExpanded.value = !statusExpanded.value)),
          onKeydown: _cache[1] || (_cache[1] = _withKeys($event => (statusExpanded.value = !statusExpanded.value), ["enter"]))
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_icon, {
              icon: "mdi-robot-outline",
              color: "primary",
              class: "mr-2"
            }),
            _cache[12] || (_cache[12] = _createTextVNode(" 运行状态 ", -1)),
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
                  default: _withCtx(() => [...(_cache[11] || (_cache[11] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_icon, {
              icon: statusExpanded.value ? 'mdi-chevron-up' : 'mdi-chevron-down'
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
                          _cache[13] || (_cache[13] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TG 频道数", -1)),
                          _createElementVNode("div", _hoisted_3, _toDisplayString(channelCount.value), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[14] || (_cache[14] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "115 登录", -1)),
                          _createElementVNode("div", {
                            class: _normalizeClass(["text-h6", loginOk.value ? 'text-success' : 'text-medium-emphasis'])
                          }, _toDisplayString(loginOk.value ? '已登录' : '未登录'), 3)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
                          _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "订阅处理", -1),
                          _createElementVNode("div", { class: "text-h6" }, "插件来源优先", -1)
                        ]))]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[16] || (_cache[16] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "上次周期扫描", -1)),
                          _createElementVNode("div", _hoisted_4, _toDisplayString(formatTime(runtime.scheduler.last_run)), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[17] || (_cache[17] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "下次周期扫描", -1)),
                          _createElementVNode("div", _hoisted_5, _toDisplayString(formatTime(runtime.scheduler.next_run)), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[18] || (_cache[18] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "队列 / 本轮订阅", -1)),
                          _createElementVNode("div", _hoisted_6, _toDisplayString(runtime.scheduler.queue_size || 0) + " / " + _toDisplayString(runtime.scheduler.scanned_count || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[19] || (_cache[19] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TMDB 识别队列", -1)),
                          _createElementVNode("div", _hoisted_7, "等待 " + _toDisplayString(runtime.recognition.waiting || 0) + " / 活动 " + _toDisplayString(runtime.recognition.active || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[20] || (_cache[20] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TMDB 最大并发", -1)),
                          _createElementVNode("div", _hoisted_8, _toDisplayString(runtime.recognition.max_active || 0) + " / 1", 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[21] || (_cache[21] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "识别恢复", -1)),
                          _createElementVNode("div", _hoisted_9, "重试 " + _toDisplayString(runtime.recognition.retries || 0) + " / 暂不可用 " + _toDisplayString(runtime.recognition.identity_unavailable || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[22] || (_cache[22] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "PanSou", -1)),
                          _createElementVNode("div", _hoisted_10, _toDisplayString(runtime.pansou.enabled ? '已启用' : '未启用') + " · 最近 " + _toDisplayString(runtime.pansou.result_count || 0) + " 条", 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[23] || (_cache[23] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "PanSou 处理", -1)),
                          _createElementVNode("div", _hoisted_11, "去重 " + _toDisplayString(runtime.pansou.deduplicated || 0) + " / 规则 " + _toDisplayString(runtime.pansou.rule_passed || 0) + " / 安全 " + _toDisplayString(runtime.pansou.safe_candidates || 0), 1)
                        ]),
                        _: 1
                      }),
                      _createVNode(_component_v_col, {
                        cols: "12",
                        md: "4"
                      }, {
                        default: _withCtx(() => [
                          _cache[24] || (_cache[24] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "PanSou 最近状态", -1)),
                          _createElementVNode("div", _hoisted_12, _toDisplayString(formatTime(runtime.pansou.last_success)) + " · 缓存 " + _toDisplayString(runtime.pansou.cache_hits || 0), 1),
                          (runtime.pansou.last_error)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_13, _toDisplayString(runtime.pansou.last_error), 1))
                            : _createCommentVNode("", true)
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  (sourceStates.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_14, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sourceStates.value, (source) => {
                          return (_openBlock(), _createBlock(_component_v_chip, {
                            key: source.name,
                            size: "small",
                            variant: "tonal",
                            color: source.cooldown_seconds > 0 ? 'warning' : 'success'
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(source.name) + " · " + _toDisplayString(source.cooldown_seconds > 0 ? `冷却 ${source.cooldown_seconds}s` : '可用'), 1)
                            ]),
                            _: 2
                          }, 1032, ["color"]))
                        }), 128))
                      ]))
                    : _createCommentVNode("", true)
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
          onClick: _cache[2] || (_cache[2] = $event => (diagnosticsExpanded.value = !diagnosticsExpanded.value))
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_icon, {
              icon: "mdi-chart-timeline-variant",
              color: "primary",
              class: "mr-2"
            }),
            _cache[26] || (_cache[26] = _createTextVNode("订阅处理诊断 ", -1)),
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
              color: "error",
              loading: clearingTimeline.value,
              "aria-label": "清理订阅终态诊断记录",
              onClick: _withModifiers(clearTimeline, ["stop"])
            }, {
              default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                _createTextVNode("清理状态记录", -1)
              ]))]),
              _: 1
            }, 8, ["loading"]),
            _createVNode(_component_v_icon, {
              icon: diagnosticsExpanded.value ? 'mdi-chevron-up' : 'mdi-chevron-down'
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
                  (healthLabels.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_15, _toDisplayString(healthLabels.value), 1))
                    : _createCommentVNode("", true),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(timeline.items, (run) => {
                    return (_openBlock(), _createElementBlock("div", {
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
                          (run.year)
                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                _createTextVNode("（" + _toDisplayString(run.year) + "）", 1)
                              ], 64))
                            : _createCommentVNode("", true),
                          (run.season !== null && run.season !== undefined)
                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                _createTextVNode(" S" + _toDisplayString(String(run.season).padStart(2, '0')), 1)
                              ], 64))
                            : _createCommentVNode("", true)
                        ]),
                        _createElementVNode("span", _hoisted_17, _toDisplayString(run.stage), 1)
                      ]),
                      _createElementVNode("div", _hoisted_18, _toDisplayString(run.events?.map(e => e.summary).filter(Boolean).join(' → ') || run.reason || '等待诊断事件'), 1)
                    ]))
                  }), 128)),
                  (!timeline.items?.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_19, "尚无订阅处理诊断记录"))
                    : _createCommentVNode("", true)
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
    (runtime.tasks.length)
      ? (_openBlock(), _createBlock(_component_v_card, {
          key: 0,
          variant: "outlined",
          rounded: "lg",
          class: "mb-4"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_v_card_title, {
              class: "d-flex align-center px-4 py-3 task-toggle",
              onClick: _cache[3] || (_cache[3] = $event => (tasksExpanded.value = !tasksExpanded.value))
            }, {
              default: _withCtx(() => [
                _createVNode(_component_v_icon, {
                  icon: "mdi-cloud-sync-outline",
                  color: "primary",
                  class: "mr-2"
                }),
                _cache[30] || (_cache[30] = _createTextVNode(" 磁力下载任务 ", -1)),
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
                    _cache[28] || (_cache[28] = _createTextVNode("清除记录 ", -1)),
                    _createVNode(_component_v_tooltip, {
                      activator: "parent",
                      location: "top"
                    }, {
                      default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                        _createTextVNode("清除已结束的本地任务记录", -1)
                      ]))]),
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
                      default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                        _createTextVNode("刷新任务状态", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _: 1
                }, 8, ["loading"]),
                _createVNode(_component_v_icon, {
                  icon: tasksExpanded.value ? 'mdi-chevron-up' : 'mdi-chevron-down'
                }, null, 8, ["icon"])
              ]),
              _: 1
            }),
            _createVNode(_component_v_expand_transition, null, {
              default: _withCtx(() => [
                _withDirectives(_createElementVNode("div", null, [
                  _createVNode(_component_v_divider),
                  _cache[34] || (_cache[34] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "115 直接磁力状态来自插件脱敏台账；手动取消只对可识别的当前任务可用", -1)),
                  _createVNode(_component_v_table, { density: "compact" }, {
                    default: _withCtx(() => [
                      _cache[33] || (_cache[33] = _createElementVNode("thead", null, [
                        _createElementVNode("tr", null, [
                          _createElementVNode("th", null, "资源"),
                          _createElementVNode("th", null, "状态"),
                          _createElementVNode("th", null, "提交时间"),
                          _createElementVNode("th", { class: "text-right" }, "操作")
                        ])
                      ], -1)),
                      _createElementVNode("tbody", null, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(runtime.tasks, (task) => {
                          return (_openBlock(), _createElementBlock("tr", {
                            key: `${task.btih}-${task.submitted_at}`
                          }, [
                            _createElementVNode("td", null, [
                              _createElementVNode("div", _hoisted_20, _toDisplayString(task.title), 1),
                              _createElementVNode("div", _hoisted_21, "115 直接磁力 · task " + _toDisplayString(String(task.task_id || '').slice(0, 12)) + "...", 1),
                              _createElementVNode("div", _hoisted_22, "BTIH " + _toDisplayString(String(task.btih || '').slice(0, 12)) + "...", 1),
                              (task.target_cid)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_23, [
                                    _createTextVNode(" 115 目标 cid " + _toDisplayString(task.target_cid), 1),
                                    (task.download_name)
                                      ? (_openBlock(), _createElementBlock("span", _hoisted_24, " · " + _toDisplayString(task.download_name), 1))
                                      : _createCommentVNode("", true)
                                  ]))
                                : _createCommentVNode("", true),
                              (task.error_message)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_25, _toDisplayString(task.error_message), 1))
                                : _createCommentVNode("", true)
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
                            _createElementVNode("td", _hoisted_26, _toDisplayString(formatTime(task.submitted_at)), 1),
                            _createElementVNode("td", _hoisted_27, [
                              (['failed', 'timed_out'].includes(task.status))
                                ? (_openBlock(), _createBlock(_component_v_btn, {
                                    key: 0,
                                    icon: "",
                                    variant: "text",
                                    size: "small",
                                    color: "primary",
                                    loading: retryingBtih.value === task.btih,
                                    onClick: $event => (retryTask(task))
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_icon, { icon: "mdi-replay" }),
                                      _createVNode(_component_v_tooltip, {
                                        activator: "parent",
                                        location: "top"
                                      }, {
                                        default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                                          _createTextVNode("重试任务", -1)
                                        ]))]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }, 8, ["loading", "onClick"]))
                                : _createCommentVNode("", true),
                              (config.offline_allow_cancel && task.source === '115_direct' && ['submitted', 'downloading', 'pending_organize'].includes(task.status))
                                ? (_openBlock(), _createBlock(_component_v_btn, {
                                    key: 1,
                                    icon: "",
                                    variant: "text",
                                    size: "small",
                                    color: "error",
                                    onClick: $event => (cancelTask(task))
                                  }, {
                                    default: _withCtx(() => [
                                      _createVNode(_component_v_icon, { icon: "mdi-cancel" }),
                                      _createVNode(_component_v_tooltip, {
                                        activator: "parent",
                                        location: "top"
                                      }, {
                                        default: _withCtx(() => [...(_cache[32] || (_cache[32] = [
                                          _createTextVNode("取消任务并恢复订阅", -1)
                                        ]))]),
                                        _: 1
                                      })
                                    ]),
                                    _: 1
                                  }, 8, ["onClick"]))
                                : _createCommentVNode("", true)
                            ])
                          ]))
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
        }))
      : _createCommentVNode("", true),
    _createVNode(_component_v_dialog, {
      modelValue: clearTasksDialog.value,
      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((clearTasksDialog).value = $event)),
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
                _cache[35] || (_cache[35] = _createTextVNode("确认清除任务记录 ", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_text, null, {
              default: _withCtx(() => [
                _createElementVNode("p", null, "将清除 " + _toDisplayString(terminalTaskCount.value) + " 条已结束的本地磁力下载任务记录。", 1),
                (activeTaskCount.value)
                  ? (_openBlock(), _createElementBlock("p", _hoisted_28, "当前有 " + _toDisplayString(activeTaskCount.value) + " 条任务仍在处理，服务器会拒绝此次清除。", 1))
                  : _createCommentVNode("", true),
                _cache[36] || (_cache[36] = _createElementVNode("p", { class: "text-medium-emphasis" }, "不会删除 115 文件，不会取消离线下载，也不会修改订阅。", -1))
              ]),
              _: 1
            }),
            _createVNode(_component_v_card_actions, { class: "px-6 pb-4" }, {
              default: _withCtx(() => [
                _createVNode(_component_v_spacer),
                _createVNode(_component_v_btn, {
                  variant: "text",
                  disabled: clearingTasks.value,
                  onClick: _cache[4] || (_cache[4] = $event => (clearTasksDialog.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_v_btn, {
                  color: "error",
                  variant: "flat",
                  loading: clearingTasks.value,
                  onClick: clearTasksConfirmed
                }, {
                  default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                    _createTextVNode("确认清除", -1)
                  ]))]),
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
            _cache[39] || (_cache[39] = _createTextVNode("手动搜索 ", -1))
          ]),
          _: 1
        }),
        _createVNode(_component_v_divider),
        _createVNode(_component_v_card_text, null, {
          default: _withCtx(() => [
            _createVNode(ManualSearch, {
              "plugin-id": PID.value,
              api: props.api
            }, null, 8, ["plugin-id", "api"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createCommentVNode("", true),
    _createVNode(_component_v_snackbar, {
      modelValue: snack.value,
      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((snack).value = $event)),
      color: snackColor.value,
      timeout: 2500,
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
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-00093145"]]);

export { Page as default };
