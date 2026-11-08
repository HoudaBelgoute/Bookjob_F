(() => {
  const attachPointerMotion = () => {
    document.querySelectorAll('.dash-hero:not([data-motion-ready])').forEach((hero) => {
      hero.dataset.motionReady = 'true'
      hero.addEventListener('pointermove', (event) => {
        const bounds = hero.getBoundingClientRect()
        const offsetX = (event.clientX - bounds.left) / bounds.width - 0.5
        const offsetY = (event.clientY - bounds.top) / bounds.height - 0.5
        hero.querySelectorAll('.dash-star').forEach((star, index) => {
          const strength = (index + 1) * 7
          star.style.translate = `${offsetX * strength}px ${offsetY * strength}px`
        })
      })
      hero.addEventListener('pointerleave', () => {
        hero.querySelectorAll('.dash-star').forEach((star) => {
          star.style.translate = ''
        })
      })
    })
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', attachPointerMotion, { once: true })
  } else {
    attachPointerMotion()
  }
})()
