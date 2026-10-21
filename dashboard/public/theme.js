/* Blocking head script prevents a light/dark flash; works with script-src 'self'. */
(function () {
  var preference = null;
  try { preference = localStorage.getItem('signal-engine-theme'); } catch (_) {}
  var dark = preference === 'dark' || (preference !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', dark);
})();
