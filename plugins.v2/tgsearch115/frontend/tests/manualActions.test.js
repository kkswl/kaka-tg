import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildManualTransferPayload,
  copyTextWithFallback,
  fallbackCopyText,
  getResourceLink,
  isCopyableResourceUrl,
  normalizeResourceUrl,
  openResourceLink,
} from '../src/manualActions.js'

function fakeDocument({ copied = true } = {}) {
  const state = { appended: 0, removed: 0, selected: false, value: '' }
  const textarea = {
    style: {},
    setAttribute() {},
    focus() {},
    select() { state.selected = true },
    setSelectionRange() {},
    remove() { state.removed += 1 },
    set value(value) { state.value = value },
    get value() { return state.value },
  }
  return {
    state,
    document: {
      body: { appendChild() { state.appended += 1 } },
      createElement(tag) { assert.equal(tag, 'textarea'); return textarea },
      execCommand(command) { assert.equal(command, 'copy'); return copied },
    },
  }
}

test('uses Clipboard API first and preserves the complete URL', async () => {
  const calls = []
  const url = 'https://115.com/s/example?password=abcd'
  const ok = await copyTextWithFallback(url, {
    navigatorRef: { clipboard: { writeText: async (value) => calls.push(value) } },
    documentRef: null,
    isSecureContext: true,
  })
  assert.equal(ok, true)
  assert.deepEqual(calls, [url])
})

test('uses Clipboard API when an embedded local HTTP page exposes it', async () => {
  const calls = []
  const ok = await copyTextWithFallback('magnet:?xt=urn:btih:0123456789abcdef', {
    navigatorRef: { clipboard: { writeText: async (value) => calls.push(value) } },
    documentRef: null,
  })
  assert.equal(ok, true)
  assert.equal(calls.length, 1)
})

test('uses the fallback after an insecure local HTTP Clipboard rejection', async () => {
  const { document, state } = fakeDocument()
  let clipboardCalled = false
  const ok = await copyTextWithFallback('magnet:?xt=urn:btih:0123456789abcdef', {
    navigatorRef: { clipboard: { writeText: async () => { clipboardCalled = true; throw new Error('denied') } } },
    documentRef: document,
  })
  assert.equal(ok, true)
  assert.equal(clipboardCalled, true)
  assert.equal(state.selected, true)
})

test('uses textarea synchronously on local HTTP even when Clipboard rejection is delayed', async () => {
  const { document, state } = fakeDocument()
  let rejectClipboard
  const pendingClipboard = new Promise((_, reject) => { rejectClipboard = reject })
  const promise = copyTextWithFallback('magnet:?xt=urn:btih:0123456789abcdef', {
    navigatorRef: { clipboard: { writeText: () => pendingClipboard } },
    documentRef: document,
    windowRef: { isSecureContext: false },
  })
  assert.equal(await promise, true)
  assert.equal(state.selected, true)
  rejectClipboard(new Error('denied'))
})

test('falls back to a temporary textarea when Clipboard API rejects', async () => {
  const { document, state } = fakeDocument()
  const url = 'https://115.com/s/example?password=abcd'
  const ok = await copyTextWithFallback(url, {
    navigatorRef: { clipboard: { writeText: async () => { throw new Error('denied') } } },
    documentRef: document,
    isSecureContext: true,
  })
  assert.equal(ok, true)
  assert.equal(state.value, url)
  assert.equal(state.appended, 1)
  assert.equal(state.removed, 1)
  assert.equal(state.selected, true)
})

test('selects complete links from all supported result fields', () => {
  const magnet = 'magnet:?xt=urn:btih:0123456789abcdef'
  assert.equal(getResourceLink({ title: 'ignored', magnet }), magnet)
  assert.equal(getResourceLink({ download_url: 'https://115.com/s/example?password=abcd' }), 'https://115.com/s/example?password=abcd')
  assert.equal(getResourceLink({ url: 'not a link' }), '')
})

test('decodes URL delimiters without converting display text into a link', () => {
  const url = 'https://115.com/s/example?password=abcd&amp;foo=bar'
  assert.equal(normalizeResourceUrl(url), 'https://115.com/s/example?password=abcd&foo=bar')
  assert.equal(getResourceLink({ resource_url: url }), 'https://115.com/s/example?password=abcd&foo=bar')
  assert.equal(getResourceLink({ title: 'https&#58;//not-a-resource' }), '')
})

test('opens web links in a protected new tab and magnet links through an anchor', () => {
  const opened = []
  assert.equal(openResourceLink('https://115.com/s/example', { windowRef: { open: (...args) => { opened.push(args); return {} } } }), true)
  assert.deepEqual(opened[0], ['https://115.com/s/example', '_blank', 'noopener,noreferrer'])
  const state = { appended: 0, removed: 0, clicked: false }
  const anchor = { style: {}, click() { state.clicked = true }, remove() { state.removed += 1 } }
  const document = { body: { appendChild() { state.appended += 1 } }, createElement() { return anchor } }
  assert.equal(openResourceLink('magnet:?xt=urn:btih:0123456789abcdef', { documentRef: document }), true)
  assert.equal(state.clicked, true)
  assert.equal(state.removed, 1)
})

test('fallback reports failure and still removes its temporary node', () => {
  const { document, state } = fakeDocument({ copied: false })
  assert.equal(fallbackCopyText('https://115.com/s/example', document), false)
  assert.equal(state.removed, 1)
})

test('returns false when both Clipboard API and textarea fallback are unavailable', async () => {
  const ok = await copyTextWithFallback('https://115.com/s/example', {
    navigatorRef: { clipboard: { writeText: async () => { throw new Error('denied') } } },
    documentRef: null,
  })
  assert.equal(ok, false)
})

test('fallback restores the scroll position after focusing the temporary field', () => {
  const { document } = fakeDocument()
  const restored = []
  const windowRef = { scrollX: 12, scrollY: 345, scrollTo: (...args) => restored.push(args) }
  assert.equal(fallbackCopyText('https://115.com/s/example', document, windowRef), true)
  assert.deepEqual(restored, [[12, 345]])
})

test('fallback restores the MoviePilot scroll container as well as the window', () => {
  const { document } = fakeDocument()
  const host = { scrollLeft: 4, scrollTop: 210, parentElement: null }
  const button = { scrollLeft: 0, scrollTop: 0, parentElement: host }
  document.activeElement = button
  document.scrollingElement = host
  document.execCommand = () => {
    host.scrollTop = 9999
    return true
  }
  assert.equal(fallbackCopyText('https://115.com/s/example', document), true)
  assert.equal(host.scrollTop, 210)
  assert.equal(host.scrollLeft, 4)
})

test('fallback uses the clicked button ancestors when activeElement belongs elsewhere', () => {
  const { document } = fakeDocument()
  const host = { scrollLeft: 2, scrollTop: 180, parentElement: null }
  const clickedButton = { scrollLeft: 0, scrollTop: 0, parentElement: host, focus() {} }
  document.activeElement = { scrollLeft: 0, scrollTop: 0, parentElement: null }
  document.execCommand = () => {
    host.scrollTop = 9000
    return true
  }
  assert.equal(fallbackCopyText('https://115.com/s/example', document, {}, clickedButton), true)
  assert.equal(host.scrollTop, 180)
  assert.equal(host.scrollLeft, 2)
})

test('accepts complete web and magnet links but rejects empty or display text', () => {
  assert.equal(isCopyableResourceUrl('https://115.com/s/example?password=abcd'), true)
  assert.equal(isCopyableResourceUrl('magnet:?xt=urn:btih:0123456789abcdef'), true)
  assert.equal(isCopyableResourceUrl(''), false)
  assert.equal(isCopyableResourceUrl('影片标题'), false)
})

test('omits target for the bound default directory and includes an explicitly selected cid', () => {
  const url = 'https://115.com/s/example?password=abcd'
  assert.deepEqual(buildManualTransferPayload(url, '123', true), {
    confirm: true,
    share_url: url,
  })
  assert.deepEqual(buildManualTransferPayload(url, '123', false), {
    confirm: true,
    share_url: url,
    target: '123',
  })
})
