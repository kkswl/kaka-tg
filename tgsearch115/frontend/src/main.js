// 本地 dev 预览入口（挂载 Page 组件）。
// 注意：本地 dev 不会加载 MoviePilot 全局 Vuetify，组件会无样式；仅供结构预览。
// 真实环境由 MP 前端通过 Module Federation 加载 Config / Page，Vuetify 由主应用提供。
import { createApp } from 'vue'
import Page from './components/Page.vue'

createApp(Page).mount('#app')
