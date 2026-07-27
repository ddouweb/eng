// 音标格式化：Word.phonetic 存的是裸 IPA，展示时包 /.../。
// 浏览器端无 eng_to_ipa 词典（Python lib），故无本地回退——依赖后端预存的 phonetic
// （ECDICT 词均有）。蓝本：frontend/components/phonetics.py。
export function formatPhonetic(p: string | null | undefined): string {
  if (!p) return ''
  const s = p.trim()
  if (!s) return ''
  return s.startsWith('/') || s.startsWith('[') ? s : `/${s}/`
}
