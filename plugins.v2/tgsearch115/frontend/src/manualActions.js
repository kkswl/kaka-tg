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

export function fallbackCopyText(text, documentRef = globalThis.document) {
  if (!documentRef?.createElement || !documentRef?.body?.appendChild) return false
  const textarea = documentRef.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
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
  }
  return copied
}

export async function copyTextWithFallback(text, options = {}) {
  const navigatorRef = options.navigatorRef ?? globalThis.navigator
  const documentRef = options.documentRef ?? globalThis.document
  if (navigatorRef?.clipboard?.writeText) {
    try {
      await navigatorRef.clipboard.writeText(text)
      return true
    } catch {
      // HTTP/local-IP pages often expose Clipboard API but reject writes.
    }
  }
  return fallbackCopyText(text, documentRef)
}

export function buildManualTransferPayload(shareUrl, target, useDefault = true) {
  const payload = { confirm: true, share_url: String(shareUrl || '').trim() }
  if (!useDefault) payload.target = String(target || '0').trim() || '0'
  return payload
}
