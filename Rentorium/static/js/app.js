/* =====================================================================
   Rentorium front end. Plain JavaScript, no library, no build step.
   Everything degrades: with JS off, every form and link still works.
   ===================================================================== */
(function () {
  'use strict';

  var root = document.documentElement;

  /* theme */
  window.toggleTheme = function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('rent-theme', next); } catch (e) {}
    var b = document.getElementById('themeBtn');
    if (b) b.textContent = next === 'dark' ? '☀️' : '🌙';
  };

  /* mobile nav */
  window.toggleNav = function () {
    var n = document.getElementById('navLinks');
    if (n) n.classList.toggle('open');
  };

  /* dropdowns */
  function wireMenus() {
    document.querySelectorAll('.menu > button').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var menu = btn.parentNode;
        var wasOpen = menu.classList.contains('open');
        document.querySelectorAll('.menu.open').forEach(function (m) {
          m.classList.remove('open');
        });
        if (!wasOpen) menu.classList.add('open');
      });
    });
    document.addEventListener('click', function () {
      document.querySelectorAll('.menu.open').forEach(function (m) {
        m.classList.remove('open');
      });
    });
  }

  /* modals */
  window.openModal = function (id) {
    var m = document.getElementById(id);
    if (!m) return;
    m.classList.add('open');
    var f = m.querySelector('input:not([type=hidden]),select,textarea');
    if (f) setTimeout(function () { f.focus(); }, 40);
  };
  window.closeModal = function (id) {
    var m = document.getElementById(id);
    if (m) m.classList.remove('open');
  };
  function wireModals() {
    document.querySelectorAll('.modal').forEach(function (m) {
      m.addEventListener('click', function (e) { if (e.target === m) m.classList.remove('open'); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal.open').forEach(function (m) { m.classList.remove('open'); });
      }
    });
  }

  /* confirm before */
  function wireConfirm() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
      var handler = function (e) {
        if (!window.confirm(el.dataset.confirm)) { e.preventDefault(); e.stopPropagation(); }
      };
      if (el.tagName === 'FORM') el.addEventListener('submit', handler);
      else el.addEventListener('click', handler);
    });
  }

  /* favourite toggle */
  /* Posts in the background so the page does not jump. Falls back to a
     normal form post when fetch is unavailable. */
  function wireFavourites() {
    document.querySelectorAll('form[data-fav]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.fetch) return;
        e.preventDefault();
        var btn = form.querySelector('button');
        fetch(form.action, {
          method: 'POST',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          body: new FormData(form),
          credentials: 'same-origin'
        }).then(function (r) { return r.json(); }).then(function (data) {
          if (btn) {
            btn.textContent = data.saved ? '♥' : '♡';
            btn.title = data.saved ? 'Saved' : 'Save this property';
            btn.style.color = data.saved ? '#E03131' : '';
          }
          var counter = document.getElementById('favCount');
          if (counter && typeof data.count === 'number') counter.textContent = data.count;
        }).catch(function () { form.submit(); });
      });
    });
  }

  /* gallery */
  window.swapImage = function (src, el) {
    var main = document.getElementById('galleryMain');
    if (!main) return;
    var old = main.src;
    main.src = src;
    if (el && el.querySelector('img')) el.querySelector('img').src = old;
  };

  /* password strength */
  function wireStrength() {
    document.querySelectorAll('[data-strength]').forEach(function (input) {
      var meter = document.getElementById(input.dataset.strength);
      if (!meter) return;
      var bar = meter.querySelector('span');
      input.addEventListener('input', function () {
        var v = input.value, s = 0;
        if (v.length >= 8) s++;
        if (v.length >= 12) s++;
        if (/[A-Z]/.test(v) && /[a-z]/.test(v)) s++;
        if (/\d/.test(v)) s++;
        if (/[^A-Za-z0-9]/.test(v)) s++;
        bar.style.width = [0, 20, 40, 60, 80, 100][s] + '%';
        bar.style.background =
          ['#E1E8ED', '#E03131', '#F08C00', '#F5C518', '#00B98E', '#00916F'][s];
      });
    });
  }

  /* filter form niceties */
  function wireFilters() {
    /* show only the extra filters that belong to the chosen property type */
    var typeSelect = document.getElementById('id_property_type');
    function sync() {
      if (!typeSelect) return;
      var value = typeSelect.value;
      document.querySelectorAll('[data-only-for]').forEach(function (box) {
        var wanted = box.dataset.onlyFor.split(',');
        box.classList.toggle('hide', value !== '' && wanted.indexOf(value) === -1);
      });
    }
    if (typeSelect) { typeSelect.addEventListener('change', sync); sync(); }

    /* auto submit when a select changes, so the page feels live */
    document.querySelectorAll('form[data-autosubmit] select').forEach(function (el) {
      el.addEventListener('change', function () { el.form.submit(); });
    });
  }

  /* one submit per form */
  function wireOnce() {
    document.querySelectorAll('form[data-once]').forEach(function (f) {
      f.addEventListener('submit', function () {
        var b = f.querySelector('button[type=submit]');
        if (b) setTimeout(function () { b.disabled = true; b.textContent = 'Please wait…'; }, 10);
      });
    });
  }

  /* dismiss toasts */
  function wireToasts() {
    document.querySelectorAll('.toasts .alert').forEach(function (t, i) {
      t.addEventListener('click', function () { t.remove(); });
      setTimeout(function () {
        t.style.transition = 'opacity .4s';
        t.style.opacity = '0';
        setTimeout(function () { t.remove(); }, 400);
      }, 5000 + i * 400);
    });
  }

  /* image upload live preview */
  function wirePreview() {
    document.querySelectorAll('[data-preview]').forEach(function (input) {
      var box = document.getElementById(input.dataset.preview);
      if (!box) return;
      input.addEventListener('change', function () {
        box.innerHTML = '';
        Array.prototype.slice.call(input.files, 0, 8).forEach(function (file) {
          if (!/^image\//.test(file.type)) return;
          var img = document.createElement('img');
          img.style.cssText = 'width:88px;height:66px;object-fit:cover;border-radius:8px';
          img.src = URL.createObjectURL(file);
          box.appendChild(img);
        });
      });
    });
  }

  /* scroll a thread to end */
  function wireThread() {
    var t = document.getElementById('thread');
    if (t) t.scrollTop = t.scrollHeight;
  }

  /* copy a link */
  window.copyText = function (text, btn) {
    var done = function () {
      if (!btn) return;
      var old = btn.textContent;
      btn.textContent = 'Copied';
      setTimeout(function () { btn.textContent = old; }, 1400);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
    else {
      var t = document.createElement('textarea');
      t.value = text; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
      document.body.removeChild(t);
    }
  };

  /* price hint */
  function wirePriceHint() {
    var price = document.getElementById('id_Price');
    var area = document.getElementById('id_Total_area_in_sqft');
    var out = document.getElementById('priceHint');
    if (!price || !area || !out) return;
    function draw() {
      var p = parseFloat(price.value || '0'), a = parseFloat(area.value || '0');
      out.textContent = (p > 0 && a > 0)
        ? 'That works out to ৳ ' + (p / a).toFixed(2) + ' per square foot.'
        : '';
    }
    price.addEventListener('input', draw);
    area.addEventListener('input', draw);
    draw();
  }

  document.addEventListener('DOMContentLoaded', function () {
    wireMenus(); wireModals(); wireConfirm(); wireFavourites(); wireStrength();
    wireFilters(); wireOnce(); wireToasts(); wirePreview();
    wireThread(); wirePriceHint();
  });
})();
