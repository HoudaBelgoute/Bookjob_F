export function normalizeWhatsAppNumber(value) {
  let number = String(value || '').replace(/\D/g, '')
  if (number.startsWith('00')) number = number.slice(2)
  if (number.startsWith('2120')) number = `212${number.slice(4)}`
  else if (number.startsWith('0')) number = `212${number.slice(1)}`
  else if (number.length === 9) number = `212${number}`
  return /^212[5-7]\d{8}$/.test(number) ? number : ''
}

export function buildWhatsAppUrl(phone, message) {
  const number = normalizeWhatsAppNumber(phone)
  if (!number) return ''
  const url = new URL(`https://wa.me/${number}`)
  if (message) url.searchParams.set('text', message)
  return url.toString()
}
