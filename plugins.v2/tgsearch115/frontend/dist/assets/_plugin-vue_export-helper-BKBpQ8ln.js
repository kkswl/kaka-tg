const RESOURCE_FILTERS = [
  { title: '全部', value: 'all' },
  { title: '磁力', value: 'magnet' },
  { title: '网盘', value: 'pan' },
  { title: '115', value: '115' },
];

const QUALITY_FILTERS = [
  { title: '全部画质', value: 'all' },
  { title: '4K', value: '4k' },
  { title: '1080P', value: '1080p' },
  { title: '高帧率', value: 'hfr' },
  { title: '排除 HDR', value: 'no_hdr' },
];

function resultText(result) {
  return [result?.display_name, result?.title, result?.meta, result?.text]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function filterSearchResults(results, resourceFilter, qualityFilter) {
  return (Array.isArray(results) ? results : []).filter((result) => {
    const panType = String(result?.pan_type || 'other').toLowerCase();
    if (resourceFilter === 'magnet' && panType !== 'magnet') return false
    if (resourceFilter === 'pan' && panType === 'magnet') return false
    if (resourceFilter === '115' && panType !== '115') return false

    const text = resultText(result);
    if (qualityFilter === '4k' && !/(?:\b4k\b|2160p|\buhd\b)/i.test(text)) return false
    if (qualityFilter === '1080p' && !/1080[pi]?/i.test(text)) return false
    if (qualityFilter === 'hfr' && !/(?:\b(?:50|60|90|120)\s*fps\b|(?:50|60|90|120)\s*帧(?:率)?|\bhfr\b|高帧率)/i.test(text)) return false
    if (qualityFilter === 'no_hdr' && /(?:\bhdr(?:10\+?)?\b|dolby\s*vision|\bdv\b|dovi|杜比视界)/i.test(text)) return false
    return true
  })
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

export { QUALITY_FILTERS as Q, RESOURCE_FILTERS as R, _export_sfc as _, filterSearchResults as f };
