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
  return String(value || '').trim()
    .replace(/&amp;/gi, '&')
    .replace(/&#38;|&#x26;/gi, '&')
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

export function fallbackCopyText(text, documentRef = globalThis.document, windowRef = globalThis.window, anchorElement = null) {
  if (!documentRef?.createElement || !documentRef?.body?.appendChild) return false
  const scrollX = Number(windowRef?.scrollX) || 0
  const scrollY = Number(windowRef?.scrollY) || 0
  // MoviePilot places the plugin inside its own scrolling container. Restoring
  // only window.scrollY is insufficient there: focusing a temporary textarea
  // can move the host container to its end on mobile WebViews.
  const scrollStates = []
  const seen = new Set()
  const rememberAncestors = (start) => {
    let parent = start
    while (parent) {
      if (!seen.has(parent) && typeof parent.scrollTop === 'number') {
        seen.add(parent)
        scrollStates.push({ element: parent, left: parent.scrollLeft || 0, top: parent.scrollTop || 0 })
      }
      parent = parent.parentElement
    }
  }
  // pointerdown.prevent used to leave activeElement on an unrelated host
  // control. The click handler now passes its real button so the actual
  // MoviePilot scroll container is always recorded, even on mobile WebViews.
  rememberAncestors(anchorElement)
  rememberAncestors(documentRef.activeElement)
  const scrollingElement = documentRef.scrollingElement
  if (scrollingElement && !seen.has(scrollingElement)) {
    scrollStates.push({ element: scrollingElement, left: scrollingElement.scrollLeft || 0, top: scrollingElement.scrollTop || 0 })
  }
  const textarea = documentRef.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  // Keep the selectable node inside the viewport. iOS/WebView can refuse a
  // selection on a control positioned thousands of pixels off-screen.
  textarea.style.left = '0'
  textarea.style.top = '0'
  textarea.style.width = '1px'
  textarea.style.height = '1px'
  textarea.style.overflow = 'hidden'
  textarea.style.fontSize = '16px'
  textarea.style.opacity = '0.01'
  textarea.style.zIndex = '-1'
  textarea.style.pointerEvents = 'none'
  documentRef.body.appendChild(textarea)
  let copied = false
  try {
    try { textarea.focus({ preventScroll: true }) } catch { textarea.focus() }
    textarea.select()
    if (typeof textarea.setSelectionRange === 'function') textarea.setSelectionRange(0, text.length)
    copied = documentRef.execCommand?.('copy') === true
  } catch {
    copied = false
  } finally {
    try { textarea.remove() } catch { documentRef.body.removeChild?.(textarea) }
    try { anchorElement?.focus?.({ preventScroll: true }) } catch { /* Focus restoration is best effort. */ }
    const restoreScroll = () => {
      for (const state of scrollStates) {
        try {
          state.element.scrollLeft = state.left
          state.element.scrollTop = state.top
        } catch { /* Container restoration is best effort. */ }
      }
      try {
        windowRef?.scrollTo?.(scrollX, scrollY)
      } catch { /* Scroll restoration is best effort. */ }
    }
    restoreScroll()
    // Some mobile WebViews apply focus scrolling after execCommand returns.
    // Restore once more on the next frame without delaying the copy result.
    try { windowRef?.requestAnimationFrame?.(restoreScroll) } catch { /* Best effort. */ }
  }
  return copied
}

export async function copyTextWithFallback(text, options = {}) {
  const navigatorRef = options.navigatorRef ?? globalThis.navigator
  const documentRef = options.documentRef ?? globalThis.document
  const windowRef = options.windowRef ?? globalThis.window
  const anchorElement = options.anchorElement ?? null
  const secureContext = options.isSecureContext ?? windowRef?.isSecureContext ?? false
  // Local-IP MoviePilot is HTTP. A WebView may expose Clipboard API but reject
  // it asynchronously after the user gesture has expired. Start that API
  // first, then complete the textarea route synchronously while the gesture is
  // still live. Both paths copy exactly the same text and neither navigates.
  if (navigatorRef?.clipboard?.writeText) {
    let clipboardPromise
    try {
      clipboardPromise = navigatorRef.clipboard.writeText(text)
    } catch {
      clipboardPromise = null
    }
    if (!secureContext) {
      const fallbackCopied = fallbackCopyText(text, documentRef, windowRef, anchorElement)
      if (fallbackCopied) {
        Promise.resolve(clipboardPromise).catch(() => undefined)
        return true
      }
    }
    try {
      await clipboardPromise
      return true
    } catch {
      // Secure contexts only reach this fallback after clipboard rejection.
    }
  }
  return fallbackCopyText(text, documentRef, windowRef, anchorElement)
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
