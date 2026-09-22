// Runs before first paint (kept as a separate file so the app's CSP can forbid inline scripts).
;(function () {
  var pref = 'system'
  try {
    pref = localStorage.getItem('fuseline.theme') || 'system'
  } catch {
    /* storage unavailable */
  }
  var dark = pref === 'dark' || (pref === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
})()
