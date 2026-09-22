import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildManualTransferPayload,
  copyTextWithFallback,
  fallbackCopyText,
  isCopyableResourceUrl,
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
  })
  assert.equal(ok, true)
  assert.deepEqual(calls, [url])
})

test('falls back to a temporary textarea when Clipboard API rejects', async () => {
  const { document, state } = fakeDocument()
  const url = 'https://115.com/s/example?password=abcd'
  const ok = await copyTextWithFallback(url, {
    navigatorRef: { clipboard: { writeText: async () => { throw new Error('denied') } } },
    documentRef: document,
  })
  assert.equal(ok, true)
  assert.equal(state.value, url)
  assert.equal(state.appended, 1)
  assert.equal(state.removed, 1)
  assert.equal(state.selected, true)
})

test('fallback reports failure and still removes its temporary node', () => {
  const { document, state } = fakeDocument({ copied: false })
  assert.equal(fallbackCopyText('https://115.com/s/example', document), false)
  assert.equal(state.removed, 1)
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
