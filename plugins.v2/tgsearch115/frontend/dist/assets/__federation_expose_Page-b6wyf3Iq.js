import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,createElementVNode:_createElementVNode,normalizeClass:_normalizeClass,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "tg115-page" };
const _hoisted_2 = { class: "text-h6" };
const _hoisted_3 = { class: "text-h6" };

const {computed,onMounted,reactive} = await importShared('vue');



const _sfc_main = {
  __name: 'Page',
  props: {
  pluginId: { type: String, default: 'TgSearch115' },
  api: { type: Object, default: null },
},
  setup(__props) {

const props = __props;

const config = reactive({ enabled: false, p115_cookie: '', delay_seconds: 0, tg_channels: [] });
const channelCount = computed(() => (Array.isArray(config.tg_channels) ? config.tg_channels.length : 0));
const loginOk = computed(() => {
  const c = String(config.p115_cookie || '');
  return c.length > 0 && ['UID', 'CID', 'SEID'].every((k) => c.includes(k + '='))
});

onMounted(async () => {
  if (!props.api?.get) return
  try {
    const res = await props.api.get(`plugin/${props.pluginId || 'TgSearch115'}/config/get`);
    const cfg = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res;
    if (cfg && typeof cfg === 'object') Object.assign(config, cfg);
  } catch (e) {
    // 静默：详情页加载失败不影响主应用
  }
});

return (_ctx, _cache) => {
  const _component_v_icon = _resolveComponent("v-icon");
  const _component_v_spacer = _resolveComponent("v-spacer");
  const _component_v_chip = _resolveComponent("v-chip");
  const _component_v_card_title = _resolveComponent("v-card-title");
  const _component_v_divider = _resolveComponent("v-divider");
  const _component_v_col = _resolveComponent("v-col");
  const _component_v_row = _resolveComponent("v-row");
  const _component_v_alert = _resolveComponent("v-alert");
  const _component_v_card_text = _resolveComponent("v-card-text");
  const _component_v_card = _resolveComponent("v-card");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_v_card, {
      variant: "outlined",
      rounded: "lg",
      class: "mb-4"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_v_card_title, { class: "d-flex align-center px-4 py-3" }, {
          default: _withCtx(() => [
            _createVNode(_component_v_icon, {
              icon: "mdi-robot-outline",
              color: "primary",
              class: "mr-2"
            }),
            _cache[0] || (_cache[0] = _createTextVNode(" 拦截mp订阅 ", -1)),
            _createVNode(_component_v_spacer),
            _createVNode(_component_v_chip, {
              color: config.enabled ? 'success' : 'grey',
              variant: "tonal",
              size: "small"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(config.enabled ? '运行中' : '已停用'), 1)
              ]),
              _: 1
            }, 8, ["color"])
          ]),
          _: 1
        }),
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
                    _cache[1] || (_cache[1] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "TG 频道数", -1)),
                    _createElementVNode("div", _hoisted_2, _toDisplayString(channelCount.value), 1)
                  ]),
                  _: 1
                }),
                _createVNode(_component_v_col, {
                  cols: "12",
                  md: "4"
                }, {
                  default: _withCtx(() => [
                    _cache[2] || (_cache[2] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "115 登录", -1)),
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
                  default: _withCtx(() => [
                    _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "触发延迟", -1)),
                    _createElementVNode("div", _hoisted_3, _toDisplayString(config.delay_seconds || 0) + " 秒", 1)
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_v_alert, {
              type: "info",
              variant: "tonal",
              class: "mt-4",
              text: "订阅新增时优先到 TG 频道搜索 115 资源，命中并转存成功后自动完成订阅；未命中或转存失败则平滑回退到 MoviePilot 默认搜索。"
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const Page = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-865d1ee3"]]);

export { Page as default };
