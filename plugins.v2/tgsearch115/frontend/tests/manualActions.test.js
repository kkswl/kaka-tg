import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildManualTransferPayload,
  clipboardEnvironment,
  copyTextSecure,
  getResourceLink,
  isCopyableResourceUrl,
  normalizeResourceUrl,
  openResourceLink,
} from '../src/manualActions.js'

test('copies the complete URL only through secure Clipboard API', async () => {
  const calls = []
  const url = 'https://115.example/s/resource?password=code'
  const result = await copyTextSecure(url, {
    navigatorRef: { userAgent: 'Chrome/140.0', clipboard: { writeText: async (value) => calls.push(value) } },
    windowRef: { isSecureContext: true, location: { protocol: 'https:' } },
  })
  assert.equal(result.success, true)
  assert.equal(result.reason, 'copied')
  assert.deepEqual(calls, [url])
})

test('insecure HTTP never invokes Clipboard API', async () => {
  const calls = []
  const result = await copyTextSecure('https://115.example/s/resource', {
    navigatorRef: { clipboard: { writeText: async (value) => calls.push(value) } },
    windowRef: { isSecureContext: false, location: { protocol: 'http:' } },
  })
  assert.equal(result.success, false)
  assert.equal(result.reason, 'insecure_context')
  assert.deepEqual(calls, [])
})

test('missing Clipboard API returns an explicit safe reason', async () => {
  const result = await copyTextSecure('https://115.example/s/resource', {
    navigatorRef: { userAgent: 'Edg/140.0' },
    windowRef: { isSecureContext: true, location: { protocol: 'https:' } },
  })
  assert.equal(result.success, false)
  assert.equal(result.reason, 'clipboard_unavailable')
})

test('Clipboard rejection is not reported as success', async () => {
  const result = await copyTextSecure('magnet:?xt=urn:btih:0123456789abcdef', {
    navigatorRef: { clipboard: { writeText: async () => { throw new Error('denied') } } },
    windowRef: { isSecureContext: true, location: { protocol: 'https:' } },
  })
  assert.equal(result.success, false)
  assert.equal(result.reason, 'permission_denied')
})

test('empty or display-only values never call Clipboard API', async () => {
  const calls = []
  for (const value of ['', '点击查看']) {
    const result = await copyTextSecure(value, {
      navigatorRef: { clipboard: { writeText: async (text) => calls.push(text) } },
      windowRef: { isSecureContext: true, location: { protocol: 'https:' } },
    })
    assert.equal(result.reason, 'invalid_url')
  }
  assert.deepEqual(calls, [])
})

test('ten sequential clicks produce ten completed writes without auxiliary state', async () => {
  const calls = []
  const options = {
    navigatorRef: { clipboard: { writeText: async (value) => calls.push(value) } },
    windowRef: { isSecureContext: true, location: { protocol: 'https:' } },
  }
  for (let index = 0; index < 10; index += 1) {
    const result = await copyTextSecure('https://115.example/s/resource', options)
    assert.equal(result.success, true)
  }
  assert.equal(calls.length, 10)
})

test('environment diagnostics contain capabilities but no resource data', () => {
  const environment = clipboardEnvironment({
    navigatorRef: { userAgent: 'Mozilla/5.0 Edg/140.0', clipboard: { writeText() {} } },
    windowRef: { isSecureContext: true, location: { protocol: 'https:' } },
  })
  assert.deepEqual(environment, {
    protocol: 'https:',
    secure_context: true,
    clipboard_available: true,
    write_text_available: true,
    browser: 'Edge 140',
  })
  assert.equal(JSON.stringify(environment).includes('115.example'), false)
})

test('selects complete links from every supported resource field', () => {
  const values = {
    share_url: 'https://115.example/s/share', resource_url: 'https://115.example/s/resource',
    magnet: 'magnet:?xt=urn:btih:0123456789abcdef', download_url: 'https://115.example/s/download',
    enclosure: 'https://115.example/s/enclosure', page_url: 'https://115.example/s/page',
    url: 'https://115.example/s/url', link: 'https://115.example/s/link',
  }
  for (const [field, value] of Object.entries(values)) assert.equal(getResourceLink({ [field]: value }), value)
  assert.equal(getResourceLink({ title: 'https://display-only.example' }), '')
})

test('decodes nested URL delimiters without using display text', () => {
  const escaped = 'https://115.example/s/resource?password=code&amp;amp;foo=bar'
  assert.equal(normalizeResourceUrl(escaped), 'https://115.example/s/resource?password=code&foo=bar')
  assert.equal(getResourceLink({ resource_url: escaped }), 'https://115.example/s/resource?password=code&foo=bar')
})

test('accepts complete web and magnet links but rejects display text', () => {
  assert.equal(isCopyableResourceUrl('https://115.example/s/resource'), true)
  assert.equal(isCopyableResourceUrl('magnet:?xt=urn:btih:0123456789abcdef'), true)
  assert.equal(isCopyableResourceUrl('点击查看'), false)
  assert.equal(isCopyableResourceUrl(''), false)
})

test('opens links without sharing state with the copy operation', () => {
  const opened = []
  assert.equal(openResourceLink('https://115.example/s/resource', { windowRef: { open: (...args) => { opened.push(args); return {} } } }), true)
  assert.deepEqual(opened[0], ['https://115.example/s/resource', '_blank', 'noopener,noreferrer'])
})

test('manual transfer payload behavior is unchanged', () => {
  const url = 'https://115.example/s/resource?password=code'
  assert.deepEqual(buildManualTransferPayload(url, '123', true), { confirm: true, share_url: url })
  assert.deepEqual(buildManualTransferPayload(url, '123', false), { confirm: true, share_url: url, target: '123' })
})
