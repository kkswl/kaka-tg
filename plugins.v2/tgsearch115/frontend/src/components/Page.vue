<!--
  Page.vue -- 插件详情页（被 MoviePilot 前端通过 Module Federation 加载到插件详情 Tab）。
  上方运行状态概览；下方手动搜索（TG 频道 + 资源站），结果用响应式卡片网格展示。
  props 由 MP 注入：pluginId、api。
-->
<template>
  <div class="tg115-page">
    <!-- ============ 状态概览 ============ -->
    <v-card variant="outlined" rounded="lg" class="mb-3">
      <v-card-title
        class="d-flex align-center px-4 py-3 status-toggle"
        role="button"
        tabindex="0"
        :aria-expanded="statusExpanded"
        aria-label="展开或收起运行状态"
        @click="statusExpanded = !statusExpanded"
        @keydown.enter="statusExpanded = !statusExpanded"
      >
        <v-icon icon="mdi-robot-outline" color="primary" class="mr-2" />
        运行状态
        <span class="text-caption text-medium-emphasis ml-3 status-summary">
          {{ statusText }}
        </span>
        <v-spacer />
        <v-btn icon variant="text" size="small" aria-label="关闭" @click.stop="closePage">
          <v-icon icon="mdi-close" />
          <v-tooltip activator="parent" location="top">关闭</v-tooltip>
        </v-btn>
        <v-icon :icon="statusExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </v-card-title>
      <v-expand-transition>
        <div v-show="statusExpanded">
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
            <div class="text-caption text-medium-emphasis">订阅处理</div>
            <div class="text-h6">插件来源优先</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">上次周期扫描</div>
            <div class="text-body-2">{{ formatTime(runtime.scheduler.last_run) }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">下次周期扫描</div>
            <div class="text-body-2">{{ formatTime(runtime.scheduler.next_run) }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">队列 / 本轮订阅</div>
            <div class="text-body-2">{{ runtime.scheduler.queue_size || 0 }} / {{ runtime.scheduler.scanned_count || 0 }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">TMDB 识别队列</div>
            <div class="text-body-2">等待 {{ runtime.recognition.waiting || 0 }} / 活动 {{ runtime.recognition.active || 0 }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">TMDB 最大并发</div>
            <div class="text-body-2">{{ runtime.recognition.max_active || 0 }} / 1</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">识别恢复</div>
            <div class="text-body-2">重试 {{ runtime.recognition.retries || 0 }} / 暂不可用 {{ runtime.recognition.identity_unavailable || 0 }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">PanSou</div>
            <div class="text-body-2">{{ runtime.pansou.enabled ? '已启用' : '未启用' }} · 最近 {{ runtime.pansou.result_count || 0 }} 条</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">PanSou 处理</div>
            <div class="text-body-2">去重 {{ runtime.pansou.deduplicated || 0 }} / 规则 {{ runtime.pansou.rule_passed || 0 }} / 安全 {{ runtime.pansou.safe_candidates || 0 }}</div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="text-caption text-medium-emphasis">PanSou 最近状态</div>
            <div class="text-body-2">{{ formatTime(runtime.pansou.last_success) }} · 缓存 {{ runtime.pansou.cache_hits || 0 }}</div>
            <div v-if="runtime.pansou.last_error" class="text-caption text-warning">{{ runtime.pansou.last_error }}</div>
          </v-col>
        </v-row>
        <div v-if="sourceStates.length" class="d-flex flex-wrap ga-2 mt-3">
          <v-chip
            v-for="source in sourceStates"
            :key="source.name"
            size="small"
            variant="tonal"
            :color="source.cooldown_seconds > 0 ? 'warning' : 'success'"
          >{{ source.name }} · {{ source.cooldown_seconds > 0 ? `冷却 ${source.cooldown_seconds}s` : '可用' }}</v-chip>
        </div>
      </v-card-text>
        </div>
      </v-expand-transition>
    </v-card>

    <v-card variant="outlined" rounded="lg" class="mb-3">
      <v-card-title class="d-flex align-center px-4 py-3 task-toggle" @click="diagnosticsExpanded = !diagnosticsExpanded">
        <v-icon icon="mdi-chart-timeline-variant" color="primary" class="mr-2" />订阅处理诊断
        <v-chip size="x-small" variant="tonal" class="ml-2">{{ timeline.total || 0 }}</v-chip><v-spacer />
        <v-btn size="x-small" variant="text" :loading="clearingTimeline" aria-label="清理已结束的订阅诊断记录" @click.stop="clearTimeline">清理已结束</v-btn>
        <v-btn size="x-small" variant="text" color="error" :loading="forceClearingTimeline" aria-label="强制清理全部订阅诊断记录" @click.stop="openForceTimelineDialog">强制清理</v-btn>
        <v-icon :icon="diagnosticsExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </v-card-title>
      <v-expand-transition><div v-show="diagnosticsExpanded"><v-divider /><v-card-text class="px-4 py-3">
        <div v-if="healthLabels" class="text-caption text-medium-emphasis mb-3">{{ healthLabels }}</div>
        <div v-for="run in timeline.items" :key="run.run_id" class="mb-3">
          <div class="d-flex align-center ga-2 flex-wrap"><v-chip size="x-small" :color="timelineColor(run.status)">{{ timelineStatus(run.status) }}</v-chip><strong>{{ run.title }}<template v-if="run.year">（{{ run.year }}）</template><template v-if="run.season !== null && run.season !== undefined"> S{{ String(run.season).padStart(2, '0') }}</template></strong><span class="text-caption">{{ run.stage }}</span></div>
          <div class="text-caption text-medium-emphasis mt-1">{{ run.events?.map(e => e.summary).filter(Boolean).join(' → ') || run.reason || '等待诊断事件' }}</div>
          <div v-if="run.organize_wait_reason" class="text-caption text-warning mt-1">当前：{{ run.organize_wait_reason }}</div>
          <div v-if="run.btih_prefix || run.last_reconcile_at" class="text-caption text-medium-emphasis mt-1">
            <span v-if="run.btih_prefix">BTIH {{ run.btih_prefix }}…</span>
            <span v-if="run.last_reconcile_at"> · 最近检查 {{ formatTime(run.last_reconcile_at) }}</span>
            <span v-if="run.status === 'waiting_organize'"> · 已等待 {{ formatWaitDuration(run.started_at) }}</span>
          </div>
        </div><div v-if="!timeline.items?.length" class="text-caption text-medium-emphasis">尚无订阅处理诊断记录</div>
      </v-card-text></div></v-expand-transition>
    </v-card>

    <v-card v-if="runtime.tasks.length" variant="outlined" rounded="lg" class="mb-4">
      <v-card-title class="d-flex align-center px-4 py-3 task-toggle" @click="tasksExpanded = !tasksExpanded">
        <v-icon icon="mdi-cloud-sync-outline" color="primary" class="mr-2" />
        磁力下载任务
        <v-chip size="x-small" variant="tonal" class="ml-2">{{ runtime.tasks.length }}</v-chip>
        <v-spacer />
        <v-btn
          size="small"
          variant="outlined"
          color="error"
          prepend-icon="mdi-delete-sweep-outline"
          aria-label="清除已结束的磁力下载任务记录"
          :loading="clearingTasks"
          @click.stop="openClearTasksDialog"
        >清除记录
          <v-tooltip activator="parent" location="top">清除已结束的本地任务记录</v-tooltip>
        </v-btn>
        <v-btn icon variant="text" size="small" :loading="statusLoading" @click.stop="loadRuntimeStatus">
          <v-icon icon="mdi-refresh" />
          <v-tooltip activator="parent" location="top">刷新任务状态</v-tooltip>
        </v-btn>
        <v-icon :icon="tasksExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'" />
      </v-card-title>
      <v-expand-transition>
      <div v-show="tasksExpanded">
      <v-divider />
      <div class="text-caption text-medium-emphasis">115 直接磁力状态来自插件脱敏台账；手动取消只对可识别的当前任务可用</div>
      <v-table density="compact">
        <thead>
          <tr><th>资源</th><th>状态</th><th>提交时间</th><th class="text-right">操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="task in runtime.tasks" :key="`${task.btih}-${task.submitted_at}`">
            <td>
              <div class="task-title">{{ task.title }}</div>
              <div class="text-caption text-medium-emphasis">115 直接磁力 · task {{ String(task.task_id || '').slice(0, 12) }}...</div>
              <div class="text-caption text-medium-emphasis">BTIH {{ String(task.btih || '').slice(0, 12) }}...</div>
              <div v-if="task.target_cid" class="text-caption text-medium-emphasis">
                115 目标 cid {{ task.target_cid }}<span v-if="task.download_name"> · {{ task.download_name }}</span>
              </div>
              <div v-if="task.error_message" class="text-caption text-error">{{ task.error_message }}</div>
              <div v-if="task.organize_wait_reason" class="text-caption text-warning">{{ task.organize_wait_reason }}</div>
              <div v-if="task.last_reconcile_at" class="text-caption text-medium-emphasis">最近对账 {{ formatTime(task.last_reconcile_at) }}</div>
            </td>
            <td><v-chip size="x-small" variant="tonal" :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</v-chip></td>
            <td class="text-caption">{{ formatTime(task.submitted_at) }}</td>
            <td class="text-right">
              <v-btn
                v-if="['failed', 'timed_out'].includes(task.status)"
                icon variant="text" size="small" color="primary"
                :loading="retryingBtih === task.btih"
                @click="retryTask(task)"
              >
                <v-icon icon="mdi-replay" />
                <v-tooltip activator="parent" location="top">重试任务</v-tooltip>
              </v-btn>
              <v-btn
                v-if="config.offline_allow_cancel && task.source === '115_direct' && ['submitted', 'downloading', 'pending_organize'].includes(task.status)"
                icon variant="text" size="small" color="error"
                @click="cancelTask(task)"
              >
                <v-icon icon="mdi-cancel" />
                <v-tooltip activator="parent" location="top">取消任务并恢复订阅</v-tooltip>
              </v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
      </div>
      </v-expand-transition>
    </v-card>

    <v-dialog v-model="clearTasksDialog" max-width="480" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-alert-outline" color="error" class="mr-2" />确认清除任务记录
        </v-card-title>
        <v-card-text>
          <p>将清除 {{ terminalTaskCount }} 条已结束的本地磁力下载任务记录。</p>
          <p v-if="activeTaskCount" class="text-warning">当前有 {{ activeTaskCount }} 条任务仍在处理，服务器会拒绝此次清除。</p>
          <p class="text-medium-emphasis">不会删除 115 文件，不会取消离线下载，也不会修改订阅。</p>
        </v-card-text>
        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" :disabled="clearingTasks" @click="clearTasksDialog = false">取消</v-btn>
          <v-btn color="error" variant="flat" :loading="clearingTasks" @click="clearTasksConfirmed">确认清除</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="forceTimelineDialog" max-width="520" persistent>
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon icon="mdi-alert-outline" color="error" class="mr-2" />强制清理订阅诊断记录
        </v-card-title>
        <v-card-text>
          <p>此操作只删除本地订阅处理诊断记录，包括进行中的显示状态。</p>
          <p class="text-medium-emphasis">不会取消下载、删除 115 文件、清除磁力任务或修改订阅。</p>
          <v-text-field
            v-model="forceTimelineConfirmation"
            label="请输入：强制清理诊断记录"
            variant="outlined"
            density="comfortable"
            hide-details
            class="mt-3"
          />
        </v-card-text>
        <v-card-actions class="px-6 pb-4">
          <v-spacer />
          <v-btn variant="text" :disabled="forceClearingTimeline" @click="closeForceTimelineDialog">取消</v-btn>
          <v-btn
            color="error"
            variant="flat"
            :loading="forceClearingTimeline"
            :disabled="forceTimelineConfirmation !== FORCE_TIMELINE_CONFIRMATION"
            @click="forceClearTimeline"
          >确认强制清理</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ============ 手动搜索 ============ -->
    <v-card variant="outlined" rounded="lg">
      <v-card-title class="d-flex align-center px-4 py-3">
        <v-icon icon="mdi-magnify" color="primary" class="mr-2" />手动搜索
        <v-spacer />
        <span class="text-caption text-medium-emphasis">{{ frontendVersion }} / {{ runtime.plugin_version || '后端版本未知' }}</span>
      </v-card-title>
      <v-divider />
      <v-card-text class="manual-search-body">
        <v-alert v-if="versionMismatch" type="warning" variant="tonal" density="compact" class="mb-3">
          插件后端与前端资源版本不一致，请刷新 MoviePilot 插件资源缓存。
        </v-alert>
        <div class="manual-search-shell" data-testid="manual-search-root">
          <div class="manual-filter-row mb-2" data-testid="manual-source-filter">
            <span class="manual-filter-label">搜索范围</span>
            <div class="manual-button-group">
              <button
                v-for="item in MANUAL_SOURCE_FILTERS"
                :key="item.value"
                type="button"
                class="manual-filter-button"
                :class="{ active: manualSource === item.value }"
                @click="manualSource = item.value"
              >{{ item.title }}</button>
            </div>
          </div>
          <label for="tg115-manual-keyword" class="manual-input-label">搜索关键字（影片名 + 年份）</label>
          <div class="manual-search-toolbar" data-testid="manual-search-controls">
            <input
              id="tg115-manual-keyword"
              v-model="manualKeyword"
              class="manual-search-input"
              type="search"
              autocomplete="off"
              data-testid="manual-search-input"
              @keyup.enter="runManualSearch"
            />
            <button
              class="manual-search-button"
              type="button"
              data-testid="manual-search-button"
              :disabled="manualSearching"
              @click="runManualSearch"
            >{{ manualSearching ? '搜索中…' : '搜索' }}</button>
          </div>

          <div class="manual-filter-row mt-3 mb-2" data-testid="manual-resource-filter">
            <span class="manual-filter-label">资源</span>
            <div class="manual-button-group">
              <button
                v-for="item in MANUAL_RESOURCE_FILTERS"
                :key="item.value"
                type="button"
                class="manual-filter-button"
                :class="{ active: manualResourceType === item.value }"
                @click="setManualResourceType(item.value)"
              >{{ item.title }}</button>
            </div>
            <span v-if="manualResults.length" class="manual-count">{{ manualFilteredResults.length }}/{{ manualResults.length }} 条</span>
          </div>
          <div v-if="manualResourceType !== 'all'" class="manual-filter-row mb-3" data-testid="manual-detail-filter">
            <span class="manual-filter-label">{{ manualResourceType === 'magnet' ? '画质' : '网盘' }}</span>
            <div class="manual-button-group">
              <button
                v-for="item in manualDetailFilters"
                :key="item.value"
                type="button"
                class="manual-filter-button"
                :class="{ active: manualDetailFilter === item.value }"
                @click="manualDetailFilter = item.value"
              >{{ item.title }}</button>
            </div>
          </div>

          <div v-if="manualSourceSummary" class="manual-source-summary">{{ manualSourceSummary }}</div>
          <div v-if="manualMessage" class="manual-message" :class="manualOk ? 'success' : 'error'">{{ manualMessage }}</div>
          <div v-if="manualSearching" class="manual-loading" role="status" aria-live="polite">搜索中…</div>
          <div v-else-if="manualFilteredResults.length" class="manual-result-grid" data-testid="manual-search-results">
            <article v-for="item in manualFilteredResults" :key="item.result_id" class="manual-result-card">
              <div class="manual-result-badges">
                <span class="manual-badge">{{ manualPanLabel(item.pan_type) }}</span>
                <span class="manual-badge">{{ manualSourceLabel(item.source) }}</span>
                <span v-if="item.resolution !== 'unknown'" class="manual-badge">{{ manualQualityLabel(item) }}</span>
                <span v-if="item.has_chinese_subtitle" class="manual-badge success">中文字幕</span>
              </div>
              <strong class="manual-result-title">{{ item.display_name || item.title }}</strong>
              <div v-if="item.meta" class="manual-result-meta">{{ item.meta }}</div>
              <div class="manual-result-text">{{ item.text || item.title }}</div>
              <div class="manual-result-actions">
                <button type="button" class="manual-link-button" @click.stop.prevent="copyManualResult(item)">复制链接</button>
                <button type="button" class="manual-link-button" @click.stop.prevent="openManualResult(item)">打开链接</button>
                <button
                  v-if="['115', 'magnet'].includes(item.pan_type)"
                  type="button"
                  class="manual-action-button"
                  @click="item.pan_type === '115' ? openManualTransferDialog(item) : openManualProcessDialog(item)"
                >{{ item.pan_type === 'magnet' ? '离线到115' : '转存' }}</button>
              </div>
            </article>
          </div>
          <div v-else-if="manualSearched && !manualSearching" class="manual-empty-state">
            {{ manualResults.length ? '当前筛选条件下没有资源，可切换筛选查看' : '所有可用来源均未找到符合条件的资源' }}
          </div>
        </div>
        <div class="frontend-build-info text-caption text-medium-emphasis mt-2">
          前端构建 {{ frontendBuildId }} · {{ frontendBuildTime }}
        </div>
      </v-card-text>
    </v-card>

    <v-dialog v-model="manualProcessDialog" max-width="520" persistent>
      <v-card>
        <v-card-title>确认正式操作</v-card-title>
        <v-card-text>
          <div class="text-body-2 mb-3">请选择对应的 MoviePilot 订阅。提交前仍会执行规则和媒体身份确认。</div>
          <v-select
            v-model="manualSubscribeId"
            :items="manualSubscriptions"
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
          <v-btn variant="text" :disabled="!!manualTransferring" @click="closeManualProcessDialog">取消</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!manualSubscribeId" :loading="!!manualTransferring" @click="submitManualResult">确认提交</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="manualTransferDialog" max-width="560" persistent>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center px-4 py-3">
          <v-icon icon="mdi-folder-open" class="mr-2" />转存到 115
        </v-card-title>
        <v-divider />
        <v-card-text class="manual-directory-body">
          <div v-if="manualTransferUseDefault" class="manual-default-target">
            <div>将使用插件设置中绑定的 115 默认目录。</div>
            <button type="button" class="manual-link-button" @click="chooseManualTransferDirectory">选择其他目录</button>
          </div>
          <div v-else class="manual-directory-toolbar">
            <button type="button" class="manual-link-button" :disabled="manualTransferLoading" @click="useManualTransferDefault">使用默认目录</button>
            <button type="button" class="manual-link-button" :disabled="manualTransferLoading" @click="navigateManualTransferRoot">根目录</button>
            <span class="text-caption text-medium-emphasis">{{ manualTransferPathText }}</span>
            <button
              v-if="manualTransferPath.length > 1"
              type="button"
              class="manual-link-button"
              :disabled="manualTransferLoading"
              @click="navigateManualTransferUp"
            >上一级</button>
          </div>
          <div v-if="!manualTransferUseDefault && manualTransferLoading" class="manual-loading" role="status">目录加载中…</div>
          <div v-else-if="!manualTransferUseDefault && manualTransferDirectories.length" class="manual-directory-list">
            <button
              v-for="directory in manualTransferDirectories"
              :key="directory.cid"
              type="button"
              class="manual-directory-item"
              @click="navigateManualTransferInto(directory)"
            >📁 {{ directory.name }}</button>
          </div>
          <div v-else-if="!manualTransferUseDefault" class="manual-empty-state">当前目录没有子目录，可直接转存到这里</div>
        </v-card-text>
        <v-divider />
        <v-card-actions class="px-4 py-3">
          <span class="text-caption text-medium-emphasis">目标：{{ manualTransferUseDefault ? '绑定的默认目录' : manualTransferPathText }}</span>
          <v-spacer />
          <v-btn variant="text" :disabled="manualTransferSubmitting" @click="closeManualTransferDialog">取消</v-btn>
          <v-btn color="primary" variant="flat" :loading="manualTransferSubmitting" @click="submitManualTransfer">{{ manualTransferUseDefault ? '转存到默认目录' : '转存到此目录' }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snack" :color="snackColor" :timeout="2500" location="top">{{ snackText }}</v-snackbar>
  </div>
</template>

<script setup>
import { computed, getCurrentInstance, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import {
  buildManualTransferPayload,
  copyTextWithFallback,
  getResourceLink,
  isCopyableResourceUrl,
  openResourceLink,
} from '../manualActions.js'

const FRONTEND_VERSION = '4.8.26'
const FRONTEND_BUILD_ID = typeof __TG115_BUILD_ID__ === 'string' ? __TG115_BUILD_ID__ : 'v4.8.26'
const FRONTEND_BUILD_TIME = typeof __TG115_BUILD_TIME__ === 'string' ? __TG115_BUILD_TIME__ : 'unknown'

const props = defineProps({
  pluginId: { type: String, default: 'TgSearch115' },
  api: { type: Object, default: null },
})
const emit = defineEmits(['close', 'back'])
const instance = getCurrentInstance()
const frontendVersion = FRONTEND_VERSION
const frontendBuildId = FRONTEND_BUILD_ID
const frontendBuildTime = FRONTEND_BUILD_TIME

function unwrapApiResponse(response) {
  let value = response
  const seen = new Set()
  for (let depth = 0; depth < 4; depth += 1) {
    if (!value || typeof value !== 'object' || !value.data || typeof value.data !== 'object' || seen.has(value.data)) break
    seen.add(value.data)
    value = value.data
  }
  return value
}

const MANUAL_CACHE_KEY = 'TgSearch115:manual-search:v2'
const MANUAL_SOURCE_FILTERS = [
  { title: '全部', value: 'all' }, { title: 'TG', value: 'tg' },
  { title: '观影', value: 'site' }, { title: 'PanSou', value: 'pansou' },
  { title: '聚影', value: 'juying' },
]
const MANUAL_RESOURCE_FILTERS = [
  { title: '全部', value: 'all' }, { title: '磁力', value: 'magnet' }, { title: '网盘', value: 'pan' },
]
const MANUAL_MAGNET_FILTERS = [
  { title: '全部', value: 'all' }, { title: '720P', value: '720p' },
  { title: '1080P', value: '1080p' }, { title: '中字1080P', value: 'chs1080p' },
  { title: '4K', value: '4k' }, { title: '中字4K', value: 'chs4k' },
  { title: '原盘', value: 'remux' }, { title: '未知', value: 'unknown' },
]
const MANUAL_PAN_FILTERS = [
  { title: '全部', value: 'all' }, { title: '迅雷网盘', value: 'xunlei' },
  { title: '百度网盘', value: 'baidu' }, { title: '夸克网盘', value: 'quark' },
  { title: '天翼网盘', value: 'cloud189' }, { title: '115网盘', value: '115' },
  { title: 'UC网盘', value: 'uc' }, { title: '阿里网盘', value: 'aliyun' },
  { title: '123网盘', value: '123' }, { title: '其他', value: 'other' },
]
const manualKeyword = ref('')
const manualSource = ref('all')
const manualResourceType = ref('all')
const manualDetailFilter = ref('all')
const manualSearching = ref(false)
const manualSearched = ref(false)
const manualResults = ref([])
const manualSourceStatus = ref({})
const manualSourceStats = ref({})
const manualMessage = ref('')
const manualOk = ref(false)
const manualProcessDialog = ref(false)
const manualSelectedResult = ref(null)
const manualSubscriptions = ref([])
const manualSubscribeId = ref(null)
const manualTransferring = ref('')
const manualTransferDialog = ref(false)
const manualTransferResult = ref(null)
const manualTransferPath = ref([{ cid: '0', name: '根目录' }])
const manualTransferDirectories = ref([])
const manualTransferLoading = ref(false)
const manualTransferSubmitting = ref(false)
const manualTransferUseDefault = ref(true)
const manualCacheAvailable = ref(true)
const manualDetailFilters = computed(() => manualResourceType.value === 'magnet' ? MANUAL_MAGNET_FILTERS : MANUAL_PAN_FILTERS)
const manualTransferPathText = computed(() => {
  const names = manualTransferPath.value.slice(1).map((part) => part.name)
  return names.length ? `/${names.join('/')}` : '/'
})
const manualFilteredResults = computed(() => {
  try {
    return manualResults.value.filter((item) => {
      if (manualResourceType.value === 'magnet' && item.resource_kind !== 'magnet') return false
      if (manualResourceType.value === 'pan' && item.resource_kind !== 'pan') return false
      if (manualDetailFilter.value === 'all') return true
      if (manualResourceType.value === 'magnet') return item.quality_class === manualDetailFilter.value
      if (manualResourceType.value === 'pan') return item.pan_type === manualDetailFilter.value
      return true
    })
  } catch {
    return []
  }
})
const manualSourceSummary = computed(() => {
  try {
    return Object.entries(manualSourceStatus.value || {}).map(([name, state]) => {
      const label = manualSourceLabel(name)
      if (state?.status === 'success' || state?.status === 'partial_success') return `${label} ${Number(state.count || 0)} 条`
      if (state?.status === 'disabled') return `${label} 已关闭`
      return `${label} ${String(state?.message || '请求失败')}`
    }).join(' · ')
  } catch {
    return ''
  }
})

function manualSafeText(value, fallback = '') {
  if (value === null || value === undefined) return fallback
  try { return String(value) } catch { return fallback }
}

function normalizeManualResult(value, index) {
  const item = value && typeof value === 'object' && !Array.isArray(value) ? value : { title: manualSafeText(value) }
  const panType = manualSafeText(item.pan_type, 'other').toLowerCase() || 'other'
  const resourceKind = ['magnet', 'pan'].includes(item.resource_kind) ? item.resource_kind : panType === 'magnet' ? 'magnet' : 'pan'
  const title = manualSafeText(item.title || item.display_name, '未命名资源').slice(0, 500)
  const resolution = manualSafeText(item.resolution, 'unknown').toLowerCase() || 'unknown'
  const qualityClass = manualSafeText(item.quality_class, 'unknown').toLowerCase() || 'unknown'
  return {
    result_id: `manual-${index}-${manualSafeText(item.source, 'unknown')}-${panType}`,
    title,
    display_name: manualSafeText(item.display_name || title, title).slice(0, 500),
    source: manualSafeText(item.source, 'unknown'),
    upstream_source: manualSafeText(item.upstream_source),
    pan_type: panType,
    resource_kind: resourceKind,
    text: manualSafeText(item.text || title, title).slice(0, 2000),
    meta: manualSafeText(item.meta).slice(0, 500),
    resolution,
    quality_class: qualityClass,
    has_chinese_subtitle: item.has_chinese_subtitle === true,
    receive_code: manualSafeText(item.receive_code).slice(0, 16),
    share_url: getResourceLink(item),
  }
}

function manualSessionStore() {
  if (!manualCacheAvailable.value) return null
  try { return window.sessionStorage } catch { manualCacheAvailable.value = false; return null }
}
function persistManualSession() {
  if (!manualSearched.value) return
  try {
    manualSessionStore()?.setItem(MANUAL_CACHE_KEY, JSON.stringify({
      keyword: manualKeyword.value, source: manualSource.value,
      resourceType: manualResourceType.value, detailFilter: manualDetailFilter.value,
      results: manualResults.value.slice(0, 500), sourceStatus: manualSourceStatus.value,
      sourceStats: manualSourceStats.value, message: manualMessage.value, ok: manualOk.value,
    }))
  } catch { manualCacheAvailable.value = false }
}
function restoreManualSession() {
  try {
    const raw = manualSessionStore()?.getItem(MANUAL_CACHE_KEY)
    if (!raw) return
    const cached = JSON.parse(raw)
    if (!cached || !Array.isArray(cached.results)) return
    manualKeyword.value = manualSafeText(cached.keyword)
    manualSource.value = manualSafeText(cached.source, 'all')
    manualResourceType.value = manualSafeText(cached.resourceType, 'all')
    manualDetailFilter.value = manualSafeText(cached.detailFilter, 'all')
    manualResults.value = cached.results.slice(0, 500).map(normalizeManualResult)
    manualSourceStatus.value = cached.sourceStatus && typeof cached.sourceStatus === 'object' ? cached.sourceStatus : {}
    manualSourceStats.value = cached.sourceStats && typeof cached.sourceStats === 'object' ? cached.sourceStats : {}
    manualMessage.value = manualSafeText(cached.message)
    manualOk.value = cached.ok === true
    manualSearched.value = true
  } catch {
    try { manualSessionStore()?.removeItem(MANUAL_CACHE_KEY) } catch { manualCacheAvailable.value = false }
  }
}
function setManualResourceType(value) {
  manualResourceType.value = value
  manualDetailFilter.value = 'all'
}

async function runManualSearch() {
  const value = manualSafeText(manualKeyword.value).trim()
  if (!value) { manualMessage.value = '请输入搜索关键字'; manualOk.value = false; return }
  if (!props.api?.get) { manualMessage.value = '搜索 API 未就绪'; manualOk.value = false; return }
  manualSearching.value = true
  manualSearched.value = true
  manualMessage.value = ''
  manualResults.value = []
  manualSourceStatus.value = {}
  manualSourceStats.value = {}
  try {
    const data = unwrapApiResponse(await props.api.get(`plugin/${PID.value}/search?keyword=${encodeURIComponent(value)}&source=${manualSource.value}`))
    if (!data || typeof data !== 'object') throw new TypeError('invalid-response')
    const sourceItems = Array.isArray(data.items) ? data.items : Array.isArray(data.results) ? data.results : Array.isArray(data.resources) ? data.resources : []
    manualResults.value = sourceItems.map(normalizeManualResult)
    manualSourceStatus.value = data.source_status && typeof data.source_status === 'object' ? data.source_status : {}
    manualSourceStats.value = data.source_stats && typeof data.source_stats === 'object' ? data.source_stats : {}
    manualOk.value = data.success !== false
    manualMessage.value = manualSafeText(data.warning || data.message || (manualOk.value ? `找到 ${manualResults.value.length} 条资源` : '搜索失败，可重试'))
  } catch (error) {
    manualResults.value = []
    manualOk.value = false
    manualMessage.value = safeRequestError(error, '搜索请求失败，可重试')
  } finally {
    manualSearching.value = false
    persistManualSession()
  }
}

function manualSourceLabel(value) { return ({ tg: 'TG', site: '观影', pansou: 'PanSou', juying: '聚影' })[value] || value || '未知' }
function manualPanLabel(value) { return ({ '115': '115网盘', quark: '夸克网盘', baidu: '百度网盘', aliyun: '阿里网盘', xunlei: '迅雷网盘', cloud189: '天翼网盘', uc: 'UC网盘', '123': '123网盘', magnet: '磁力' })[value] || '其他' }
function manualQualityLabel(item) { return ({ '4k': '4K', '1080p': '1080P', '720p': '720P' })[item?.resolution] || '未知' }
function manualFullUrl(item) {
  let url = getResourceLink(item)
  if (item?.pan_type === '115' && item?.receive_code && !/[?&](password|receive_code|pwd)=/.test(url)) url += `${url.includes('?') ? '&' : '?'}password=${item.receive_code}`
  return url
}
async function copyManualResult(item) {
  const url = manualFullUrl(item).trim()
  if (!isCopyableResourceUrl(url)) {
    showSnack('该资源没有有效链接', 'warning')
    return
  }
  try {
    const copied = await copyTextWithFallback(url)
    showSnack(copied ? '链接已复制' : '复制失败，请手动复制', copied ? 'success' : 'error')
  } catch {
    showSnack('复制失败，请手动复制', 'error')
  }
}
function openManualResult(item) {
  const url = manualFullUrl(item).trim()
  if (!isCopyableResourceUrl(url)) {
    showSnack('该资源没有有效链接', 'warning')
    return
  }
  if (!openResourceLink(url)) showSnack('链接无法打开，请检查浏览器弹窗或磁力关联设置', 'warning')
}

async function loadManualTransferDirectories(cid) {
  if (!props.api?.get) {
    showSnack('目录服务不可用', 'error')
    return
  }
  manualTransferLoading.value = true
  manualTransferDirectories.value = []
  try {
    const response = await props.api.get(`plugin/${PID.value}/dirs?cid=${encodeURIComponent(cid)}`)
    const data = unwrapApiResponse(response)
    if (data?.success) manualTransferDirectories.value = Array.isArray(data.dirs) ? data.dirs : []
    else showSnack(manualSafeText(data?.message, '获取目录失败'), 'error')
  } catch (error) {
    const data = unwrapApiResponse(error?.response?.data)
    showSnack(manualSafeText(data?.message, safeRequestError(error, '获取目录失败')), 'error')
  } finally {
    manualTransferLoading.value = false
  }
}

async function openManualTransferDialog(item) {
  const url = manualFullUrl(item).trim()
  if (!isCopyableResourceUrl(url) || item?.pan_type !== '115') {
    showSnack('该资源没有有效的 115 分享链接', 'warning')
    return
  }
  manualTransferResult.value = item
  manualTransferPath.value = [{ cid: '0', name: '根目录' }]
  manualTransferUseDefault.value = true
  manualTransferDirectories.value = []
  manualTransferDialog.value = true
}

function closeManualTransferDialog() {
  if (manualTransferSubmitting.value) return
  manualTransferDialog.value = false
  manualTransferResult.value = null
  manualTransferDirectories.value = []
}

async function navigateManualTransferInto(directory) {
  const cid = manualSafeText(directory?.cid).trim()
  const name = manualSafeText(directory?.name).trim()
  if (!cid || !name) return
  manualTransferPath.value.push({ cid, name })
  await loadManualTransferDirectories(cid)
}

async function chooseManualTransferDirectory() {
  manualTransferUseDefault.value = false
  manualTransferPath.value = [{ cid: '0', name: '根目录' }]
  await loadManualTransferDirectories('0')
}

function useManualTransferDefault() {
  manualTransferUseDefault.value = true
  manualTransferDirectories.value = []
}

async function navigateManualTransferUp() {
  if (manualTransferPath.value.length > 1) manualTransferPath.value.pop()
  await loadManualTransferDirectories(manualTransferPath.value.at(-1)?.cid || '0')
}

async function navigateManualTransferRoot() {
  manualTransferPath.value = [{ cid: '0', name: '根目录' }]
  await loadManualTransferDirectories('0')
}

async function submitManualTransfer() {
  const item = manualTransferResult.value
  if (!item || !props.api?.post || manualTransferSubmitting.value) return
  const shareUrl = manualFullUrl(item).trim()
  if (!isCopyableResourceUrl(shareUrl) || item.pan_type !== '115') {
    showSnack('该资源没有有效的 115 分享链接', 'warning')
    return
  }
  manualTransferSubmitting.value = true
  try {
    const payload = buildManualTransferPayload(
      shareUrl,
      manualTransferPath.value.at(-1)?.cid || '0',
      manualTransferUseDefault.value,
    )
    const response = await props.api.post(`plugin/${PID.value}/manual/transfer`, payload)
    const data = unwrapApiResponse(response)
    const success = data?.success === true
    showSnack(manualSafeText(data?.message, success ? '转存成功' : '转存失败'), success ? 'success' : 'error')
    if (success) {
      manualTransferSubmitting.value = false
      closeManualTransferDialog()
    }
  } catch (error) {
    const data = unwrapApiResponse(error?.response?.data)
    showSnack(manualSafeText(data?.message, safeRequestError(error, '转存请求失败，请重试')), 'error')
  } finally {
    manualTransferSubmitting.value = false
  }
}
async function loadManualSubscriptions() {
  if (!props.api?.get) return
  try {
    const data = unwrapApiResponse(await props.api.get(`plugin/${PID.value}/manual/subscriptions`))
    manualSubscriptions.value = Array.isArray(data?.items) ? data.items : []
  } catch { manualSubscriptions.value = [] }
}
async function openManualProcessDialog(item) {
  manualSelectedResult.value = item
  manualSubscribeId.value = null
  if (!manualSubscriptions.value.length) await loadManualSubscriptions()
  manualProcessDialog.value = true
}
function closeManualProcessDialog() {
  manualProcessDialog.value = false
  manualSelectedResult.value = null
  manualSubscribeId.value = null
}
async function submitManualResult() {
  const item = manualSelectedResult.value
  if (!item || !manualSubscribeId.value || !props.api?.post) return
  manualTransferring.value = item.result_id
  try {
    const data = unwrapApiResponse(await props.api.post(`plugin/${PID.value}/manual/process`, {
      subscribe_id: manualSubscribeId.value,
      confirm: true,
      candidate: {
        share_url: manualFullUrl(item), receive_code: item.receive_code || '',
        title: item.title || item.display_name || '', text: item.text || '',
        pan_type: item.pan_type || '', source: item.source || '',
      },
    }))
    const success = data?.success === true || data?.code === 0
    showSnack(manualSafeText(data?.message, success ? '任务提交成功' : '提交失败'), success ? 'success' : 'error')
    if (success) closeManualProcessDialog()
  } catch (error) {
    showSnack(safeRequestError(error, '提交请求失败，可重试'), 'error')
  } finally { manualTransferring.value = '' }
}

watch([manualSource, manualResourceType, manualDetailFilter], persistManualSession)
restoreManualSession()

function closePage() {
  try {
    if (instance?.vnode?.props?.onClose) {
      emit('close')
      return
    }
    if (instance?.vnode?.props?.onBack) {
      emit('back')
      return
    }
  } catch {}
  try {
    window.history.back()
  } catch {}
}

const PID = computed(() => props.pluginId || 'TgSearch115')

// ---- 配置 / 状态 ----
const config = reactive({ enabled: false, tg_search_enabled: true, p115_cookie: '', offline_allow_cancel: false, tg_channels: [] })
const runtime = reactive({
  plugin_version: '',
  scheduler: { running: false, last_run: '', next_run: '', scanned_count: 0, queue_size: 0 },
  recognition: { waiting: 0, active: 0, max_active: 0, last_wait_seconds: 0, retries: 0, identity_unavailable: 0, stopping: false },
  sources: {},
  tg: { enabled: true, configured_channels: 0, enabled_channels: 0, status: 'empty' },
  pansou: { enabled: false, last_request: '', last_success: '', last_error: '', result_count: 0, type_counts: {}, cache_hits: 0, deduplicated: 0, rule_passed: 0, identity_checked: 0, safe_candidates: 0 },
  tasks: [],
})
const diagnosticsExpanded = ref(false)
const timeline = reactive({ total: 0, active_count: 0, terminal_count: 0, items: [] })
const clearingTimeline = ref(false)
const forceClearingTimeline = ref(false)
const forceTimelineDialog = ref(false)
const forceTimelineConfirmation = ref('')
const FORCE_TIMELINE_CONFIRMATION = '强制清理诊断记录'
const sourceHealth = ref({})
const healthLabels = computed(() => Object.entries(sourceHealth.value || {}).map(([source, item]) => `${({ tg: 'TG', site: '观影', pansou: 'PanSou', juying: '聚影' })[source] || source} ${item.score}分`).join(' · '))
const statusLoading = ref(false)
const statusExpanded = ref(false)
const statusText = computed(() => {
  const tgState = runtime.tg?.status === 'disabled'
    ? '已关闭'
    : runtime.tg?.status === 'empty'
      ? '已启用但无频道'
      : '已启用'
  return `${config.enabled ? '运行中' : '已停用'} · TG ${tgState} · 115 ${loginOk.value ? '已登录' : '未登录'} · PanSou ${runtime.pansou.enabled ? '已启用' : '未启用'}`
})
const versionMismatch = computed(() => !!runtime.plugin_version && runtime.plugin_version !== FRONTEND_VERSION)
const tasksExpanded = ref(false)
const retryingBtih = ref('')
const clearingTasks = ref(false)
const clearTasksDialog = ref(false)
const ACTIVE_TASK_STATUSES = new Set(['waiting', 'submitted', 'downloading', 'pending_organize'])
const terminalTaskCount = computed(() => runtime.tasks.filter(task => !ACTIVE_TASK_STATUSES.has(task.status)).length)
const activeTaskCount = computed(() => runtime.tasks.filter(task => ACTIVE_TASK_STATUSES.has(task.status)).length)
let statusTimer = null
const sourceStates = computed(() => Object.entries(runtime.sources || {}).map(([name, state]) => ({ name, ...state })))
const channelCount = computed(() => (Array.isArray(config.tg_channels) ? config.tg_channels.length : 0))
const loginOk = computed(() => {
  const c = String(config.p115_cookie || '')
  return c.length > 0 && ['UID', 'CID', 'SEID'].every((k) => c.includes(k + '='))
})

// snackbar
const snack = ref(false)
const snackColor = ref('')
const snackText = ref('')

function formatTime(value) {
  if (!value) return '尚未运行'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}
function formatWaitDuration(value) {
  const started = new Date(value || '')
  if (Number.isNaN(started.getTime())) return '未知'
  const minutes = Math.max(0, Math.floor((Date.now() - started.getTime()) / 60000))
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  return `${hours} 小时 ${minutes % 60} 分钟`
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
  const terminalCount = Number(timeline.terminal_count || 0)
  if (!terminalCount) { showSnack('没有可清理的终态诊断记录', 'info'); return }
  if (!window.confirm(`仅删除本地终态诊断记录；不会删除 115 文件、不会取消下载、不会修改订阅。\n将清理当前列表中的 ${terminalCount} 条终态记录，是否继续？`)) return
  clearingTimeline.value = true
  try {
    const res = await props.api.post(`plugin/${PID.value}/runtime/timeline/clear`, { confirm: true })
    const raw = res?.data || res
    const data = raw?.data?.success !== undefined ? raw.data : raw
    showSnack(data?.message || '清除失败', data?.success ? 'success' : 'error')
    if (data?.success) await loadRuntimeStatus()
  } catch (error) {
    const message = error?.response?.data?.message
    showSnack(message || '清除诊断记录请求失败，可重试', 'error')
  } finally { clearingTimeline.value = false }
}

function openForceTimelineDialog() {
  if (forceClearingTimeline.value) return
  forceTimelineConfirmation.value = ''
  forceTimelineDialog.value = true
}

function closeForceTimelineDialog() {
  if (forceClearingTimeline.value) return
  forceTimelineDialog.value = false
  forceTimelineConfirmation.value = ''
}

async function forceClearTimeline() {
  if (!props.api?.post || forceClearingTimeline.value) return
  if (forceTimelineConfirmation.value !== FORCE_TIMELINE_CONFIRMATION) {
    showSnack('请输入完整确认文字', 'warning')
    return
  }
  forceClearingTimeline.value = true
  try {
    const response = await props.api.post(`plugin/${PID.value}/runtime/timeline/clear`, {
      confirm: true,
      force: true,
      confirmation_text: FORCE_TIMELINE_CONFIRMATION,
    })
    const data = unwrapApiResponse(response)
    showSnack(data?.message || (data?.success ? '诊断记录已清理' : '强制清理失败'), data?.success ? 'success' : 'error')
    if (data?.success) {
      forceTimelineDialog.value = false
      forceTimelineConfirmation.value = ''
      await loadRuntimeStatus()
    }
  } catch (error) {
    showSnack(safeRequestError(error, '强制清理请求失败'), 'error')
  } finally {
    forceClearingTimeline.value = false
    if (!forceTimelineDialog.value) forceTimelineConfirmation.value = ''
  }
}

async function loadRuntimeStatus() {
  if (!props.api?.get) return
  statusLoading.value = true
  try {
    const res = await props.api.get(`plugin/${PID.value}/runtime/status`)
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    if (data?.success) {
      runtime.plugin_version = String(data.plugin_version || '')
      Object.assign(runtime.scheduler, data.scheduler || {})
      Object.assign(runtime.recognition, data.recognition || {})
      runtime.sources = data.sources || {}
      Object.assign(runtime.pansou, data.pansou || {})
      runtime.tasks = Array.isArray(data.tasks) ? data.tasks : []
      Object.assign(timeline, data.timeline || { total: 0, active_count: 0, terminal_count: 0, items: [] })
      sourceHealth.value = data.source_health || {}
    }
  } catch {
    // Status refresh is non-blocking; search actions continue to work.
  } finally {
    statusLoading.value = false
  }
}

async function retryTask(task) {
  if (!props.api?.post || !task?.btih) return
  retryingBtih.value = task.btih
  try {
    const res = await props.api.post(`plugin/${PID.value}/tasks/retry`, { btih: task.btih })
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    showSnack(data?.message || (data?.success ? '订阅已恢复' : '重试失败'), data?.success ? 'success' : 'error')
    await loadRuntimeStatus()
  } catch (e) {
    showSnack(safeRequestError(e, '重试请求失败'), 'error')
  } finally {
    retryingBtih.value = ''
  }
}
async function cancelTask(task) {
  if (!props.api?.post || !task?.btih) return
  try {
    const res = await props.api.post(`plugin/${PID.value}/tasks/cancel`, { btih: task.btih })
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    showSnack(data?.message || '取消失败', data?.success ? 'success' : 'error')
    await loadRuntimeStatus()
  } catch (e) {
    showSnack(safeRequestError(e, '取消请求失败'), 'error')
  }
}

function openClearTasksDialog() {
  if (clearingTasks.value) return
  clearTasksDialog.value = true
}

async function clearTasksConfirmed() {
  if (!props.api?.post || clearingTasks.value) return
  clearingTasks.value = true
  try {
    const res = await props.api.post(`plugin/${PID.value}/tasks/clear`, { confirm: true })
    const data = res && typeof res === 'object' && 'data' in res && ('success' in res || 'code' in res) ? res.data : res
    showSnack(data?.message || '清除失败', data?.success ? 'success' : 'error')
    if (data?.success) {
      clearTasksDialog.value = false
      await loadRuntimeStatus()
    }
  } catch (e) {
    showSnack(safeRequestError(e, '清除任务记录失败'), 'error')
  } finally {
    clearingTasks.value = false
  }
}

function showSnack(text, color) {
  snackText.value = text
  snackColor.value = color
  snack.value = true
}

function safeRequestError(error, fallback) {
  const status = Number(error?.response?.status || error?.status || 0)
  if (status >= 400 && status <= 599) return `${fallback}（HTTP ${status}）`
  const code = String(error?.code || '').toUpperCase()
  if (code.includes('TIMEOUT') || code === 'ECONNABORTED') return `${fallback}（请求超时）`
  return fallback
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
  await loadRuntimeStatus()
  statusTimer = setInterval(loadRuntimeStatus, 30000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style scoped>
.tg115-page {
  max-width: 1280px;
  margin: 0 auto;
}
.manual-search-body {
  display: block;
  visibility: visible;
  width: 100%;
  min-width: 0;
  min-height: 260px;
  height: auto;
  overflow: visible;
}
.manual-search-shell { display:block; visibility:visible; width:100%; min-width:0; min-height:220px; height:auto; overflow:visible; }
.manual-input-label { display:block; margin:10px 0 6px; font-size:.875rem; }
.manual-search-toolbar { display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:8px; width:100%; min-width:0; }
.manual-search-input { display:block; width:100%; min-width:0; min-height:44px; padding:8px 12px; border:1px solid rgba(var(--v-border-color),.8); border-radius:6px; background:transparent; color:inherit; }
.manual-search-button,.manual-action-button { min-height:44px; padding:8px 20px; border:0; border-radius:6px; background:rgb(var(--v-theme-primary)); color:rgb(var(--v-theme-on-primary)); cursor:pointer; }
.manual-search-button:disabled,.manual-action-button:disabled { opacity:.6; cursor:default; }
.manual-filter-row { display:flex; align-items:center; gap:8px; min-width:0; flex-wrap:wrap; }
.manual-filter-label { flex:0 0 auto; font-size:.75rem; color:rgba(var(--v-theme-on-surface),.62); }
.manual-button-group { display:flex; flex-wrap:wrap; gap:4px; min-width:0; }
.manual-filter-button,.manual-link-button { min-height:32px; padding:5px 10px; border:1px solid rgba(var(--v-border-color),.7); border-radius:5px; background:transparent; color:inherit; cursor:pointer; }
.manual-filter-button.active { border-color:rgb(var(--v-theme-primary)); background:rgba(var(--v-theme-primary),.13); color:rgb(var(--v-theme-primary)); }
.manual-count,.manual-badge { font-size:.72rem; padding:2px 7px; border-radius:10px; background:rgba(var(--v-theme-primary),.12); }
.manual-badge.success { color:rgb(var(--v-theme-success)); background:rgba(var(--v-theme-success),.12); }
.manual-source-summary,.manual-message { margin-top:10px; padding:8px 10px; border-radius:6px; font-size:.8rem; }
.manual-source-summary { border:1px solid rgba(var(--v-border-color),.6); }
.manual-message.success { color:rgb(var(--v-theme-success)); }
.manual-message.error { color:rgb(var(--v-theme-error)); }
.manual-loading,.manual-empty-state { padding:28px 12px; text-align:center; color:rgba(var(--v-theme-on-surface),.62); }
.manual-result-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:10px; margin-top:12px; }
.manual-result-card { display:flex; flex-direction:column; gap:7px; min-width:0; padding:12px; border:1px solid rgba(var(--v-border-color),.7); border-radius:8px; }
.manual-result-badges,.manual-result-actions { display:flex; flex-wrap:wrap; align-items:center; gap:5px; }
.manual-result-title,.manual-result-meta,.manual-result-text { overflow-wrap:anywhere; }
.manual-result-meta { color:rgb(var(--v-theme-primary)); font-size:.76rem; }
.manual-result-text { display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; font-size:.78rem; color:rgba(var(--v-theme-on-surface),.66); }
.manual-result-actions { justify-content:flex-start; gap:6px; flex-wrap:wrap; margin-top:auto; padding-top:5px; }
.manual-link-button { border:0; }
.manual-directory-body { max-height:55vh; overflow-y:auto; padding:10px 14px; }
.manual-directory-toolbar { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.manual-default-target { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; min-height:48px; }
.manual-directory-list { display:grid; gap:5px; margin-top:8px; }
.manual-directory-item { width:100%; min-height:40px; padding:8px 10px; border:0; border-radius:6px; background:transparent; color:inherit; text-align:left; cursor:pointer; }
.manual-directory-item:hover,.manual-directory-item:focus-visible { background:rgba(var(--v-theme-primary),.1); outline:none; }
.frontend-build-info { overflow-wrap:anywhere; }
.result-card {
  min-height: 180px;
}
.task-toggle { cursor: pointer; }
.dry-run-controls { max-width: 560px; }
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
.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.filter-label {
  flex: 0 0 32px;
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.62);
}
.filter-toggle {
  max-width: calc(100% - 40px);
  overflow-x: auto;
}
.filter-empty {
  padding: 28px 12px;
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-size: 0.875rem;
}
.task-title {
  max-width: 520px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 600px) {
  .manual-search-body { min-height:280px; padding:16px; }
  .manual-search-toolbar { grid-template-columns:minmax(0, 1fr); }
  .manual-search-button { width:100%; }
  .manual-result-grid { grid-template-columns:minmax(0,1fr); }
  .filter-row { flex-wrap:wrap; }
  .filter-toggle { max-width:100%; }
}
</style>
