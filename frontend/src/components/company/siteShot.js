function withProtocol(url) {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`
}

export function siteShot(url, { width = 800, crop = 1500 } = {}) {
  if (!url) return null
  return `https://image.thum.io/get/width/${width}/crop/${crop}/${withProtocol(url)}`
}

export function hostOf(url) {
  if (!url) return ''
  try {
    return new URL(withProtocol(url)).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}
