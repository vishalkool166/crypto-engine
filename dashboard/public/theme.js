/* Blocking head script prevents a light/dark flash; works with script-src 'self'. */
(function () {
  var preference = null;
  try { preference = localStorage.getItem('signal-engine-theme'); } catch (_) {}
  var dark = preference === 'dark';
  document.documentElement.classList.toggle('dark', dark);
})();
