export function isCopyableResourceUrl(value) {
  const text = normalizeResourceUrl(value)
  if (!text) return false
  if (/^magnet:\?xt=urn:btih:[a-z0-9]+/i.test(text)) return true
  try {
    const parsed = new URL(text)
    return ['http:', 'https:'].includes(parsed.protocol) && Boolean(parsed.hostname)
  } catch {
    return false
  }
}

export function normalizeResourceUrl(value) {
  // APIs sometimes serialize query delimiters as HTML entities.  Decode only
  // delimiters that are valid in a URL; never use the display title as a
  // fallback and never encode an already-complete resource URL again.
  let text = String(value || '').trim()
  // Some source payloads are escaped more than once (`&amp;amp;`). Decode
  // only the URL delimiter and cap the loop so arbitrary HTML is untouched.
  for (let index = 0; index < 3; index += 1) {
    const decoded = text.replace(/&amp;/gi, '&').replace(/&#38;|&#x26;/gi, '&')
    if (decoded === text) break
    text = decoded
  }
  return text
}

export function getResourceLink(resource) {
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
  ]
  for (const candidate of candidates) {
    const text = normalizeResourceUrl(candidate)
    if (isCopyableResourceUrl(text)) return text
  }
  return ''
}

function browserNameAndMajor(userAgent = '') {
  const value = String(userAgent || '')
  const match = value.match(/Edg\/(\d+)/i) || value.match(/Chrome\/(\d+)/i) || value.match(/Firefox\/(\d+)/i)
  if (!match) return '未知'
  const name = /Edg\//i.test(value) ? 'Edge' : /Firefox\//i.test(value) ? 'Firefox' : 'Chrome'
  return `${name} ${match[1]}`
}

export function clipboardEnvironment(options = {}) {
  const navigatorRef = options.navigatorRef ?? globalThis.navigator
  const windowRef = options.windowRef ?? globalThis.window
  return {
    protocol: String(windowRef?.location?.protocol || 'unknown:'),
    secure_context: windowRef?.isSecureContext === true,
    clipboard_available: Boolean(navigatorRef?.clipboard),
    write_text_available: typeof navigatorRef?.clipboard?.writeText === 'function',
    browser: browserNameAndMajor(navigatorRef?.userAgent),
  }
}

export async function copyTextSecure(text, options = {}) {
  const navigatorRef = options.navigatorRef ?? globalThis.navigator
  const environment = clipboardEnvironment(options)
  if (!isCopyableResourceUrl(text)) return { success: false, reason: 'invalid_url', environment }
  if (!environment.secure_context) return { success: false, reason: 'insecure_context', environment }
  if (!environment.write_text_available) return { success: false, reason: 'clipboard_unavailable', environment }
  try {
    await navigatorRef.clipboard.writeText(String(text || ''))
    return { success: true, reason: 'copied', environment }
  } catch {
    return { success: false, reason: 'permission_denied', environment }
  }
}

export function openResourceLink(url, options = {}) {
  const text = String(url || '').trim()
  if (!isCopyableResourceUrl(text)) return false
  const windowRef = options.windowRef ?? globalThis.window
  const documentRef = options.documentRef ?? globalThis.document
  if (/^magnet:\?/i.test(text)) {
    if (!documentRef?.createElement || !documentRef?.body?.appendChild) return false
    const anchor = documentRef.createElement('a')
    anchor.href = text
    anchor.style.display = 'none'
    documentRef.body.appendChild(anchor)
    try {
      anchor.click()
      return true
    } catch {
      return false
    } finally {
      try { anchor.remove() } catch { documentRef.body.removeChild?.(anchor) }
    }
  }
  const opened = windowRef?.open?.(text, '_blank', 'noopener,noreferrer')
  if (opened) {
    try { opened.opener = null } catch { /* Cross-window assignment is best effort. */ }
    return true
  }
  return false
}

export function buildManualTransferPayload(shareUrl, target, useDefault = true) {
  const payload = { confirm: true, share_url: String(shareUrl || '').trim() }
  if (!useDefault) payload.target = String(target || '0').trim() || '0'
  return payload
}
