/* ui.js — 共享交互助手：滚动 reveal、数字 count-up、debounce、图表 resize 注册 */
window.UI = (function () {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function debounce(fn, ms) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms || 150);
    };
  }

  /* 给带 [data-reveal] 的区块加进场动画 */
  function reveal() {
    const els = document.querySelectorAll('[data-reveal]');
    if (reduced || !('IntersectionObserver' in window)) {
      els.forEach(e => e.classList.add('revealed'));
      return;
    }
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if (en.isIntersecting) { en.target.classList.add('revealed'); io.unobserve(en.target); }
      });
    }, { threshold: 0.06, rootMargin: '0px 0px -40px 0px' });
    els.forEach(e => io.observe(e));
  }

  /* 数字滚动：el 目标元素，val 数值，opts {dec:小数位, suffix:后缀} */
  function countUp(el, val, opts) {
    opts = opts || {};
    const dec = opts.dec || 0, suffix = opts.suffix || '';
    if (val === null || val === undefined || val === '' || isNaN(Number(val))) {
      el.textContent = (val === null || val === undefined) ? '—' : val;
      return;
    }
    const target = Number(val);
    if (reduced) { el.textContent = target.toFixed(dec) + suffix; return; }
    const dur = 900, t0 = performance.now();
    (function step(t) {
      const p = Math.min(1, (t - t0) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(dec) + suffix;
      if (p < 1) requestAnimationFrame(step);
    })(t0);
  }

  /* ECharts 实例注册：自动响应窗口尺寸变化 */
  const charts = [];
  function reg(instance) { charts.push(instance); return instance; }
  window.addEventListener('resize', debounce(() => charts.forEach(c => c.resize()), 200));

  return { debounce, reveal, countUp, reg, reduced };
})();
