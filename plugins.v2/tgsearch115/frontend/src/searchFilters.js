export const RESOURCE_FILTERS = [
  { title: '全部', value: 'all' },
  { title: '磁力', value: 'magnet' },
  { title: '网盘', value: 'pan' },
  { title: '115', value: '115' },
]

export const QUALITY_FILTERS = [
  { title: '全部画质', value: 'all' },
  { title: '4K', value: '4k' },
  { title: '1080P', value: '1080p' },
  { title: '高帧率', value: 'hfr' },
  { title: '排除 HDR', value: 'no_hdr' },
]

export const MAGNET_FILTERS = [
  { title: '全部', value: 'all' },
  { title: '720P', value: '720p' },
  { title: '1080P', value: '1080p' },
  { title: '中字1080P', value: 'chs1080p' },
  { title: '4K', value: '4k' },
  { title: '中字4K', value: 'chs4k' },
  { title: '原盘', value: 'remux' },
  { title: '未知', value: 'unknown' },
]

export const PAN_FILTERS = [
  { title: '全部', value: 'all' },
  { title: '迅雷网盘', value: 'xunlei' },
  { title: '百度网盘', value: 'baidu' },
  { title: '夸克网盘', value: 'quark' },
  { title: '天翼网盘', value: 'cloud189' },
  { title: '115网盘', value: '115' },
  { title: 'UC网盘', value: 'uc' },
  { title: '阿里网盘', value: 'aliyun' },
  { title: '123网盘', value: '123' },
  { title: '其他', value: 'other' },
]

function resultText(result) {
  return [result?.display_name, result?.title, result?.meta, result?.text]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

// Compatibility path for results restored from a pre-v4.7.51 browser cache.
// New API results always carry normalized fields produced by resource_metadata.py.
function legacyMetadata(result) {
  const text = resultText(result)
  const panType = String(result?.pan_type || '').toLowerCase()
  const is4k = /(?<![\w\d])(?:4\s*k|2160[pi]?|3840\s*[x×]\s*2160|uhd)(?![\w\d])/i.test(text)
  const is1080 = !is4k && /(?<![\w\d])(?:1080[pi]?|1920\s*[x×]\s*1080)(?![\w\d])/i.test(text)
  const is720 = !is4k && !is1080 && /(?<![\w\d])(?:720[pi]?|1280\s*[x×]\s*720)(?![\w\d])/i.test(text)
  const subtitle = /(?:中文字幕|中字|简体中文|繁体中文|简繁|\bchs\b|\bcht\b|\.(?:chs|cht)\.(?:srt|ass|sub)|chinese\s+subtitles?)/i.test(text)
  const isRemux = /(?<![\w])(?:remux|原盘|bdmv|blu[\s-]?ray\s+iso|uhd\s+blu[\s-]?ray\s+原盘)(?![\w])/i.test(text)
  const resolution = is4k ? '4k' : is1080 ? '1080p' : is720 ? '720p' : 'unknown'
  return {
    resource_kind: panType === 'magnet' ? 'magnet' : 'pan',
    pan_type: panType || 'other',
    resolution,
    has_chinese_subtitle: subtitle,
    is_remux: isRemux,
    quality_class: isRemux ? 'remux' : subtitle && resolution === '4k' ? 'chs4k' : subtitle && resolution === '1080p' ? 'chs1080p' : resolution,
  }
}

export function searchResultMetadata(result) {
  if (result && ['magnet', 'pan'].includes(result.resource_kind) && result.quality_class) return result
  return { ...result, ...legacyMetadata(result) }
}

export function filterSearchResults(results, resourceFilter, qualityFilter) {
  return (Array.isArray(results) ? results : []).filter((result) => {
    const metadata = searchResultMetadata(result)
    const panType = String(metadata.pan_type || 'other').toLowerCase()
    if (resourceFilter === 'magnet' && metadata.resource_kind !== 'magnet') return false
    if (resourceFilter === 'pan' && metadata.resource_kind !== 'pan') return false
    if (resourceFilter === '115' && panType !== '115') return false

    if (resourceFilter === 'pan' && qualityFilter !== 'all' && panType !== qualityFilter) return false
    if (resourceFilter === 'magnet' && qualityFilter !== 'all' && metadata.quality_class !== qualityFilter) return false
    // Legacy configuration page filters still use these values. Keep them structured too.
    if (qualityFilter === '4k' && metadata.resolution !== '4k') return false
    if (qualityFilter === '1080p' && metadata.resolution !== '1080p') return false
    const text = resultText(result)
    if (qualityFilter === 'hfr' && !/(?:\b(?:50|60|90|120)\s*fps\b|(?:50|60|90|120)\s*帧(?:率)?|\bhfr\b|高帧率)/i.test(text)) return false
    if (qualityFilter === 'no_hdr' && /(?:\bhdr(?:10\+?)?\b|dolby\s*vision|\bdv\b|dovi|杜比视界)/i.test(text)) return false
    return true
  })
}
