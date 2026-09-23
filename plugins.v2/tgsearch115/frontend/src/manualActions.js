export function isCopyableResourceUrl(value) {
  const text = String(value || '').trim()
  if (!text) return false
  if (/^magnet:\?xt=urn:btih:[a-z0-9]+/i.test(text)) return true
  try {
    const parsed = new URL(text)
    return ['http:', 'https:'].includes(parsed.protocol) && Boolean(parsed.hostname)
  } catch {
    return false
  }
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
    const text = String(candidate || '').trim()
    if (isCopyableResourceUrl(text)) return text
  }
  return ''
}

export function fallbackCopyText(text, documentRef = globalThis.document, windowRef = globalThis.window) {
  if (!documentRef?.createElement || !documentRef?.body?.appendChild) return false
  const scrollX = Number(windowRef?.scrollX) || 0
  const scrollY = Number(windowRef?.scrollY) || 0
  const textarea = documentRef.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '0'
  textarea.style.top = '0'
  textarea.style.width = '1px'
  textarea.style.height = '1px'
  textarea.style.overflow = 'hidden'
  textarea.style.fontSize = '12pt'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  documentRef.body.appendChild(textarea)
  let copied = false
  try {
    textarea.focus()
    textarea.select()
    if (typeof textarea.setSelectionRange === 'function') textarea.setSelectionRange(0, text.length)
    copied = documentRef.execCommand?.('copy') === true
  } catch {
    copied = false
  } finally {
    try { textarea.remove() } catch { documentRef.body.removeChild?.(textarea) }
    try { windowRef?.scrollTo?.(scrollX, scrollY) } catch { /* Scroll restoration is best effort. */ }
  }
  return copied
}

export async function copyTextWithFallback(text, options = {}) {
  const navigatorRef = options.navigatorRef ?? globalThis.navigator
  const documentRef = options.documentRef ?? globalThis.document
  const windowRef = options.windowRef ?? globalThis.window
  // Some embedded/local-IP browsers expose Clipboard API despite a non-secure
  // origin. Invoke it immediately while the click gesture is active, then use
  // the legacy fallback only if the browser actually rejects the request.
  if (navigatorRef?.clipboard?.writeText) {
    try {
      await navigatorRef.clipboard.writeText(text)
      return true
    } catch {
      // HTTP/local-IP pages often expose Clipboard API but reject writes.
    }
  }
  return fallbackCopyText(text, documentRef, windowRef)
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
