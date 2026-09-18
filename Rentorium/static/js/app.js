/* =====================================================================
   Rentorium front end.
   Plain JavaScript, no library, no build step. Everything here is an
   enhancement: with scripting switched off every form still posts, every
   link still navigates, and every filter still applies.
   ===================================================================== */
(function () {
  'use strict';

  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) {
    return Array.prototype.slice.call((ctx || document).querySelectorAll(sel));
  }

  /* ---------------------------------------------------------------- *
     Theme
   * ---------------------------------------------------------------- */
  window.toggleTheme = function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    /* damp the transition for one frame so the whole page does not smear */
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('rent-theme', next); } catch (e) {}
  };

  /* ---------------------------------------------------------------- *
     Navigation
   * ---------------------------------------------------------------- */
  window.toggleNav = function () {
    var n = document.getElementById('navLinks');
    if (n) n.classList.toggle('open');
  };

  function wireNavShadow() {
    var nav = $('.nav');
    if (!nav) return;
    var on = false;
    function check() {
      var should = window.scrollY > 8;
      if (should !== on) { on = should; nav.classList.toggle('scrolled', should); }
    }
    check();
    window.addEventListener('scroll', check, { passive: true });
  }

  /* A thin bar across the top while the next page loads. Browsers give no
     feedback for a plain form post, which made the site feel unresponsive. */
  function wireProgress() {
    var bar = document.createElement('div');
    bar.id = 'navProgress';
    document.body.appendChild(bar);
    var timer = null;

    function start() {
      if (timer) return;
      bar.classList.add('on');
      var width = 0;
      bar.style.width = '0%';
      timer = setInterval(function () {
        width += (92 - width) * 0.09;
        bar.style.width = width.toFixed(1) + '%';
      }, 160);
    }
    window.__navStart = start;

    document.addEventListener('click', function (e) {
      var a = e.target.closest ? e.target.closest('a') : null;
      if (!a || a.target === '_blank' || e.metaKey || e.ctrlKey || e.shiftKey) return;
      var href = a.getAttribute('href') || '';
      if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return;
      if (a.hasAttribute('download')) return;
      if (a.host && a.host !== location.host) return;
      start();
    });
    document.addEventListener('submit', function (e) {
      if (e.target && e.target.method && e.target.method.toLowerCase() !== 'dialog') start();
    });
    window.addEventListener('pageshow', function () {
      if (timer) { clearInterval(timer); timer = null; }
      bar.style.width = '100%';
      setTimeout(function () { bar.classList.remove('on'); bar.style.width = '0%'; }, 320);
    });
  }

  /* ---------------------------------------------------------------- *
     Dropdown menus
   * ---------------------------------------------------------------- */
  function wireMenus() {
    $$('.menu > button').forEach(function (btn) {
      btn.setAttribute('aria-expanded', 'false');
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var menu = btn.parentNode;
        var wasOpen = menu.classList.contains('open');
        $$('.menu.open').forEach(function (m) {
          m.classList.remove('open');
          var b = $('button', m); if (b) b.setAttribute('aria-expanded', 'false');
        });
        if (!wasOpen) { menu.classList.add('open'); btn.setAttribute('aria-expanded', 'true'); }
      });
    });
    document.addEventListener('click', function () {
      $$('.menu.open').forEach(function (m) {
        m.classList.remove('open');
        var b = $('button', m); if (b) b.setAttribute('aria-expanded', 'false');
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        $$('.menu.open').forEach(function (m) { m.classList.remove('open'); });
      }
    });
  }

  /* ---------------------------------------------------------------- *
     Modals
   * ---------------------------------------------------------------- */
  var lastFocused = null;

  window.openModal = function (id) {
    var m = document.getElementById(id);
    if (!m) return;
    lastFocused = document.activeElement;
    m.classList.add('open');
    m.setAttribute('role', 'dialog');
    m.setAttribute('aria-modal', 'true');
    document.body.style.overflow = 'hidden';
    var f = m.querySelector('input:not([type=hidden]):not([disabled]),select,textarea,button');
    if (f) setTimeout(function () { f.focus(); }, 60);
  };
  window.closeModal = function (id) {
    var m = document.getElementById(id);
    if (!m) return;
    m.classList.remove('open');
    if (!$('.modal.open') && !$('.lightbox.open')) document.body.style.overflow = '';
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  };

  function wireModals() {
    $$('.modal').forEach(function (m) {
      m.addEventListener('click', function (e) { if (e.target === m) closeModal(m.id); });
    });
    /* keep tab inside an open dialog */
    document.addEventListener('keydown', function (e) {
      var open = $('.modal.open');
      if (!open) return;
      if (e.key === 'Escape') { closeModal(open.id); return; }
      if (e.key !== 'Tab') return;
      var f = $$('a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),' +
                 'select,textarea,[tabindex]:not([tabindex="-1"])', open)
              .filter(function (el) { return el.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  /* ---------------------------------------------------------------- *
     Confirm before a destructive action
   * ---------------------------------------------------------------- */
  function wireConfirm() {
    $$('[data-confirm]').forEach(function (el) {
      var handler = function (e) {
        if (!window.confirm(el.dataset.confirm)) { e.preventDefault(); e.stopPropagation(); }
      };
      if (el.tagName === 'FORM') el.addEventListener('submit', handler);
      else el.addEventListener('click', handler);
    });
  }

  /* ---------------------------------------------------------------- *
     Show / hide password
   * ---------------------------------------------------------------- */
  var EYE = '<svg class="ico-svg on" viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M2.6 12S6.2 5.6 12 5.6 21.4 12 21.4 12 17.8 18.4 12 18.4 2.6 12 2.6 12z"/>' +
    '<circle cx="12" cy="12" r="3.1"/></svg>' +
    '<svg class="ico-svg off" viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M4 4l16 16"/>' +
    '<path d="M9.6 5.9A9.7 9.7 0 0 1 12 5.6c5.8 0 9.4 6.4 9.4 6.4a17.4 17.4 0 0 1-3.5 4.3"/>' +
    '<path d="M6.3 7.7A17.2 17.2 0 0 0 2.6 12S6.2 18.4 12 18.4a9.5 9.5 0 0 0 3.4-.6"/>' +
    '<path d="M9.9 10a3.1 3.1 0 0 0 4.2 4.3"/></svg>';

  function wirePasswordEyes() {
    $$('input[type=password]').forEach(function (input) {
      if (input.dataset.noEye !== undefined) return;
      var wrap = document.createElement('div');
      wrap.className = 'pw-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'pw-toggle';
      btn.innerHTML = EYE;
      btn.setAttribute('aria-label', 'Show password');
      btn.title = 'Show password';
      btn.addEventListener('click', function () {
        var showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        btn.classList.toggle('shown', !showing);
        btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
        btn.title = btn.getAttribute('aria-label');
        input.focus();
        /* keep the caret at the end rather than jumping to the start */
        var v = input.value; input.value = ''; input.value = v;
      });
      wrap.appendChild(btn);
    });
  }

  /* ---------------------------------------------------------------- *
     Favourite and compare, without losing your place on the page
   * ---------------------------------------------------------------- */
  function postForm(form) {
    return fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
      credentials: 'same-origin'
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }

  function wireFavourites() {
    $$('form[data-fav]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.fetch) return;
        e.preventDefault();
        var btn = form.querySelector('button');
        postForm(form).then(function (data) {
          if (btn) {
            btn.classList.toggle('on', !!data.saved);
            btn.classList.remove('pop');
            void btn.offsetWidth;
            if (data.saved) btn.classList.add('pop');
            btn.title = data.saved ? 'Saved' : 'Save this property';
            btn.setAttribute('aria-pressed', data.saved ? 'true' : 'false');
          }
          var counter = document.getElementById('favCount');
          if (counter && typeof data.count === 'number') counter.textContent = data.count;
          var label = form.querySelector('[data-fav-label]');
          if (label) label.textContent = data.saved ? 'Saved' : 'Save';
          toast(data.saved ? 'Saved to your list.' : 'Removed from saved.', 'ok');
        }).catch(function () { form.submit(); });
      });
    });
  }

  function wireCompare() {
    $$('form[data-compare]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        if (!window.fetch) return;
        e.preventDefault();
        var btn = form.querySelector('button');
        postForm(form).then(function (data) {
          if (data.message) toast(data.message, data.added ? 'ok' : 'info');
          if (btn) {
            btn.classList.toggle('on', !!data.added);
            var text = btn.querySelector('[data-compare-label]');
            if (text) text.textContent = data.added ? 'Comparing' : 'Compare';
          }
          paintCompareBar(data.count);
        }).catch(function () { form.submit(); });
      });
    });
  }

  function paintCompareBar(count) {
    var bar = document.getElementById('compareBar');
    if (!bar) return;
    var label = bar.querySelector('[data-compare-count]');
    if (label) {
      label.textContent = count + ' propert' + (count === 1 ? 'y' : 'ies') + ' to compare';
    }
    bar.classList.toggle('hide', !count);
  }

  /* ---------------------------------------------------------------- *
     Toasts
   * ---------------------------------------------------------------- */
  function toastBox() {
    var box = $('.toasts');
    if (!box) {
      box = document.createElement('div');
      box.className = 'toasts no-print';
      document.body.appendChild(box);
    }
    return box;
  }

  function toast(text, kind) {
    var el = document.createElement('div');
    el.className = 'alert alert-' + (kind || 'info');
    el.innerHTML = '<span></span>';
    el.firstChild.textContent = text;
    toastBox().appendChild(el);
    dismissLater(el, 0);
  }
  window.toast = toast;

  function dismissLater(el, i) {
    el.addEventListener('click', function () { fade(el); });
    setTimeout(function () { fade(el); }, 5200 + i * 500);
  }
  function fade(el) {
    el.style.transition = 'opacity .35s, transform .35s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(24px)';
    setTimeout(function () { el.remove(); }, 360);
  }
  function wireToasts() {
    $$('.toasts .alert').forEach(dismissLater);
  }

  /* ---------------------------------------------------------------- *
     Photo lightbox
   * ---------------------------------------------------------------- */
  var lb = { images: [], at: 0, el: null };

  function buildLightbox() {
    var el = document.createElement('div');
    el.className = 'lightbox';
    el.id = 'lightbox';
    el.innerHTML =
      '<button class="lb-btn lb-close" type="button" aria-label="Close">' +
        '<svg class="ico-svg" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button>' +
      '<button class="lb-btn lb-prev" type="button" aria-label="Previous">' +
        '<svg class="ico-svg" viewBox="0 0 24 24"><path d="m14.5 5.5-6.5 6.5 6.5 6.5"/></svg></button>' +
      '<img alt="">' +
      '<button class="lb-btn lb-next" type="button" aria-label="Next">' +
        '<svg class="ico-svg" viewBox="0 0 24 24"><path d="m9.5 5.5 6.5 6.5-6.5 6.5"/></svg></button>' +
      '<div class="lb-count"></div>';
    document.body.appendChild(el);
    $('.lb-close', el).addEventListener('click', closeLightbox);
    $('.lb-prev', el).addEventListener('click', function (e) { e.stopPropagation(); step(-1); });
    $('.lb-next', el).addEventListener('click', function (e) { e.stopPropagation(); step(1); });
    el.addEventListener('click', function (e) { if (e.target === el) closeLightbox(); });
    lb.el = el;
    return el;
  }

  function paintLightbox() {
    var img = $('img', lb.el);
    img.style.animation = 'none';
    void img.offsetWidth;
    img.style.animation = '';
    img.src = lb.images[lb.at];
    $('.lb-count', lb.el).textContent = (lb.at + 1) + ' of ' + lb.images.length;
    var many = lb.images.length > 1;
    $('.lb-prev', lb.el).style.display = many ? '' : 'none';
    $('.lb-next', lb.el).style.display = many ? '' : 'none';
  }
  function step(d) {
    lb.at = (lb.at + d + lb.images.length) % lb.images.length;
    paintLightbox();
  }
  function closeLightbox() {
    if (lb.el) lb.el.classList.remove('open');
    if (!$('.modal.open')) document.body.style.overflow = '';
  }
  window.openLightbox = function (index) {
    if (!lb.images.length) return;
    if (!lb.el) buildLightbox();
    lb.at = Math.max(0, Math.min(index || 0, lb.images.length - 1));
    paintLightbox();
    lb.el.classList.add('open');
    document.body.style.overflow = 'hidden';
  };

  function wireGallery() {
    var gallery = $('[data-gallery]');
    if (!gallery) return;
    try { lb.images = JSON.parse(gallery.dataset.gallery); } catch (e) { lb.images = []; }
    if (!lb.images.length) return;
    $$('[data-photo]', gallery).forEach(function (el) {
      el.addEventListener('click', function () {
        openLightbox(parseInt(el.dataset.photo, 10) || 0);
      });
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
      });
    });
    document.addEventListener('keydown', function (e) {
      if (!lb.el || !lb.el.classList.contains('open')) return;
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowLeft') step(-1);
      if (e.key === 'ArrowRight') step(1);
    });
  }

  /* ---------------------------------------------------------------- *
     Password strength
   * ---------------------------------------------------------------- */
  function wireStrength() {
    $$('[data-strength]').forEach(function (input) {
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
          ['#CDC9BB', '#A62A21', '#B4761A', '#C9A227', '#2E9E6B', '#0F7A57'][s];
      });
    });
  }

  /* ---------------------------------------------------------------- *
     Filters
   * ---------------------------------------------------------------- */
  function wireFilters() {
    /* only show the extra fields that belong to the chosen property type */
    var typeSelect = document.getElementById('id_property_type');
    function sync() {
      if (!typeSelect) return;
      var value = typeSelect.value;
      $$('[data-only-for]').forEach(function (box) {
        var wanted = box.dataset.onlyFor.split(',');
        box.classList.toggle('hide', value !== '' && wanted.indexOf(value) === -1);
      });
    }
    if (typeSelect) { typeSelect.addEventListener('change', sync); sync(); }

    $$('form[data-autosubmit] select').forEach(function (el) {
      el.addEventListener('change', function () {
        if (window.__navStart) window.__navStart();
        el.form.submit();
      });
    });

    /* on a phone the filters live in a sheet, not above the results */
    var panel = document.getElementById('filterPanel');
    if (!panel) return;
    var backdrop = document.createElement('div');
    backdrop.className = 'drawer-backdrop';
    document.body.appendChild(backdrop);

    function open() {
      panel.classList.add('open');
      backdrop.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
    function close() {
      panel.classList.remove('open');
      backdrop.classList.remove('open');
      document.body.style.overflow = '';
    }
    window.openFilters = open;
    window.closeFilters = close;
    backdrop.addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && panel.classList.contains('open')) close();
    });
  }

  /* ---------------------------------------------------------------- *
     Small conveniences
   * ---------------------------------------------------------------- */
  function wireOnce() {
    $$('form[data-once]').forEach(function (f) {
      f.addEventListener('submit', function () {
        var b = f.querySelector('button[type=submit]');
        if (b) setTimeout(function () {
          b.disabled = true;
          b.dataset.was = b.innerHTML;
          b.textContent = 'Please wait…';
        }, 10);
      });
    });
  }

  function wirePreview() {
    $$('[data-preview]').forEach(function (input) {
      var box = document.getElementById(input.dataset.preview);
      if (!box) return;
      input.addEventListener('change', function () {
        box.innerHTML = '';
        Array.prototype.slice.call(input.files, 0, 8).forEach(function (file) {
          if (!/^image\//.test(file.type)) return;
          var img = document.createElement('img');
          img.style.cssText =
            'width:92px;height:69px;object-fit:cover;border-radius:10px;' +
            'border:1px solid var(--border)';
          img.src = URL.createObjectURL(file);
          box.appendChild(img);
        });
      });
    });
  }

  function wireThread() {
    var t = document.getElementById('thread');
    if (t) t.scrollTop = t.scrollHeight;
  }

  window.copyText = function (text, btn) {
    var done = function () {
      toast('Link copied.', 'ok');
      if (!btn) return;
      var old = btn.innerHTML;
      btn.textContent = 'Copied';
      setTimeout(function () { btn.innerHTML = old; }, 1500);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
    else {
      var t = document.createElement('textarea');
      t.value = text; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
      document.body.removeChild(t);
    }
  };

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

  /* ---------------------------------------------------------------- *
     Reveal on scroll
   * ---------------------------------------------------------------- */
  function wireReveal() {
    var targets = $$('.reveal');
    if (!targets.length) return;

    /* Arm the hidden pre-state, and promise to disarm it. After this window
       anything still unrevealed is simply shown, so a missed observer
       callback can never leave a blank page. */
    root.classList.add('armed');
    var disarm = setTimeout(function () { root.classList.remove('armed'); }, 5000);
    if (reduced || !('IntersectionObserver' in window)) {
      targets.forEach(function (el) { el.classList.add('in'); });
      clearTimeout(disarm);
      root.classList.remove('armed');
      return;
    }
    /* Belt and braces: if anything goes wrong with the observer, nothing on
       the page should stay invisible. */
    setTimeout(function () {
      targets.forEach(function (el) {
        var box = el.getBoundingClientRect();
        if (box.top < window.innerHeight * 1.4) el.classList.add('in');
      });
    }, 1200);
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('in');
        io.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });

    targets.forEach(function (el, i) {
      /* stagger anything that sits in the same grid */
      if (!el.style.getPropertyValue('--d')) {
        var within = el.parentNode ? Array.prototype.indexOf.call(el.parentNode.children, el) : i;
        el.style.setProperty('--d', Math.min(within, 7) * 55 + 'ms');
      }
      io.observe(el);
    });

    /* A second, cheaper sweep on scroll. Nothing that has been scrolled past
       may stay invisible, whatever the observer did or did not deliver — a
       fast flick, a jump to an anchor, a restored scroll position. */
    var pending = false;
    function sweep() {
      pending = false;
      var bottom = window.innerHeight;
      for (var i = targets.length - 1; i >= 0; i--) {
        var el = targets[i];
        if (el.classList.contains('in')) { targets.splice(i, 1); continue; }
        if (el.getBoundingClientRect().top < bottom) {
          el.classList.add('in');
          io.unobserve(el);
          targets.splice(i, 1);
        }
      }
      if (!targets.length) {
        window.removeEventListener('scroll', onScroll);
        clearTimeout(disarm);
        root.classList.remove('armed');
      }
    }
    function onScroll() {
      if (pending) return;
      pending = true;
      requestAnimationFrame(sweep);
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
  }

  /* ---------------------------------------------------------------- *
     The load veil. Markup sits at the top of the body and is only ever
     visible with scripting on; this lifts it as soon as the document is
     ready, and the stylesheet lifts it anyway after three seconds so a
     script that never arrives cannot leave the page behind a sheet.
   * ---------------------------------------------------------------- */
  function wireVeil() {
    var v = document.getElementById('veil');
    if (!v) return;
    function lift() {
      v.classList.add('gone');
      setTimeout(function () { if (v.parentNode) v.parentNode.removeChild(v); }, 700);
    }
    /* long enough to read as a deliberate transition, short enough not to
       be a wait; if the page is still loading, hold until it is not. */
    if (document.readyState === 'complete') setTimeout(lift, 260);
    else window.addEventListener('load', function () { setTimeout(lift, 200); });
    setTimeout(lift, 2200);   /* never hold the page hostage to one image */
  }

  /* ---------------------------------------------------------------- *
     Hero stage — photographs crossfade, each drifting while it shows.
   * ---------------------------------------------------------------- */
  function wireStage() {
    $$('.stage').forEach(function (stage) {
      var slides = $$('figure', stage);
      if (slides.length < 2) return;

      var dots = $('.stage-dots', stage);
      var i = slides.findIndex ? slides.findIndex(function (s) {
        return s.classList.contains('on');
      }) : 0;
      if (i < 0) { i = 0; slides[0].classList.add('on'); }

      var pips = [];
      if (dots) {
        slides.forEach(function (s, n) {
          var b = document.createElement('button');
          b.type = 'button';
          b.setAttribute('aria-label', 'Show picture ' + (n + 1));
          b.addEventListener('click', function () { go(n, true); });
          dots.appendChild(b);
          pips.push(b);
        });
      }

      function go(n, manual) {
        n = (n + slides.length) % slides.length;
        if (n === i) return;
        slides[i].classList.remove('on');
        i = n;
        slides[i].classList.add('on');
        /* restart the drift on the picture that is now showing */
        var img = $('img', slides[i]);
        if (img) { img.style.animation = 'none'; void img.offsetWidth; img.style.animation = ''; }
        pips.forEach(function (b, k) {
          b.setAttribute('aria-current', k === i ? 'true' : 'false');
        });
        if (manual) rest();
      }
      pips.forEach(function (b, k) {
        b.setAttribute('aria-current', k === i ? 'true' : 'false');
      });

      var prev = $('.stage-nav [data-prev]', stage);
      var next = $('.stage-nav [data-next]', stage);
      if (prev) prev.addEventListener('click', function () { go(i - 1, true); });
      if (next) next.addEventListener('click', function () { go(i + 1, true); });

      if (reduced) return;
      var timer = null;
      function tick() { go(i + 1); }
      function rest() { stop(); timer = setInterval(tick, 5200); }
      function stop() { if (timer) { clearInterval(timer); timer = null; } }
      rest();
      stage.addEventListener('mouseenter', stop);
      stage.addEventListener('mouseleave', rest);
      stage.addEventListener('focusin', stop);
      stage.addEventListener('focusout', rest);
      document.addEventListener('visibilitychange', function () {
        if (document.hidden) stop(); else rest();
      });
    });
  }

  /* ---------------------------------------------------------------- *
     Quotation carousel — one card at a time on a phone, three on a desk.
   * ---------------------------------------------------------------- */
  function wireSays() {
    $$('.says').forEach(function (box) {
      var track = $('.says-track', box);
      if (!track) return;
      var cards = $$(':scope > *', track);
      var bar = box.parentNode.querySelector('.says-bar');
      if (!bar || cards.length < 2) { if (bar) bar.remove(); return; }
      var pipBox = $('.pips', bar);
      var at = 0, per = 1, pages = 1;

      function measure() {
        var w = box.clientWidth, cw = cards[0].getBoundingClientRect().width;
        per = Math.max(1, Math.round(w / Math.max(cw, 1)));
        pages = Math.max(1, Math.ceil(cards.length / per));
        if (at > pages - 1) at = pages - 1;
        if (pipBox) {
          pipBox.textContent = '';
          for (var k = 0; k < pages; k++) pipBox.appendChild(document.createElement('i'));
        }
        paint();
      }
      function paint() {
        track.style.transform = 'translateX(' + (-at * 100) + '%)';
        if (pipBox) $$('i', pipBox).forEach(function (p, k) {
          p.classList.toggle('on', k === at);
        });
        bar.style.display = pages > 1 ? '' : 'none';
      }
      function go(n) { at = (n + pages) % pages; paint(); }

      var p = bar.querySelector('[data-prev]'), n = bar.querySelector('[data-next]');
      if (p) p.addEventListener('click', function () { go(at - 1); stop(); });
      if (n) n.addEventListener('click', function () { go(at + 1); stop(); });

      var timer = null;
      function run() { if (!reduced) { stop(); timer = setInterval(function () { go(at + 1); }, 6000); } }
      function stop() { if (timer) { clearInterval(timer); timer = null; } }
      box.addEventListener('mouseenter', stop);
      box.addEventListener('mouseleave', run);

      measure(); run();
      var t;
      window.addEventListener('resize', function () {
        clearTimeout(t); t = setTimeout(measure, 150);
      }, { passive: true });
    });
  }

  /* ---------------------------------------------------------------- *
     Search suggestions.

     Every `input[data-suggest]` gets a panel underneath it: the person's own
     recent searches while the box is empty, then real areas and listings as
     they type. It is an enhancement over a plain text input — the form still
     submits whatever was typed, so with scripting off nothing is lost.
   * ---------------------------------------------------------------- */
  function wireSuggest() {
    var boxes = $$('input[data-suggest]');
    if (!boxes.length) return;

    function esc(s) {
      return String(s).replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
    }
    /* mark the typed part inside a suggestion, without trusting either string */
    function mark(label, term) {
      var safe = esc(label);
      if (!term) return safe;
      var at = label.toLowerCase().indexOf(term.toLowerCase());
      if (at < 0) return safe;
      return esc(label.slice(0, at)) + '<mark>' +
             esc(label.slice(at, at + term.length)) + '</mark>' +
             esc(label.slice(at + term.length));
    }
    var ICON = {
      recent: 'history', area: 'pin', listing: 'building', search: 'search'
    };
    var SPRITE = {};
    /* borrow the icons the server already rendered on this page */
    $$('svg.ico-svg').forEach(function (svg) {
      var key = svg.getAttribute('data-icon');
      if (key && !SPRITE[key]) SPRITE[key] = svg.outerHTML;
    });
    function iconFor(kind) {
      return SPRITE[ICON[kind]] || SPRITE.search || '';
    }

    boxes.forEach(function (input) {
      var wrap = document.createElement('div');
      wrap.className = 'suggest-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      var panel = document.createElement('div');
      panel.className = 'suggest';
      panel.setAttribute('role', 'listbox');
      wrap.appendChild(panel);

      input.setAttribute('autocomplete', 'off');
      input.setAttribute('aria-expanded', 'false');

      var url = input.getAttribute('data-suggest') || '/property/suggest/';
      var at = -1, links = [], timer = null, cache = {}, lastTerm = null;

      function close() {
        panel.classList.remove('open');
        input.setAttribute('aria-expanded', 'false');
        at = -1;
      }
      function open() {
        if (!links.length) { close(); return; }
        panel.classList.add('open');
        input.setAttribute('aria-expanded', 'true');
      }
      function highlight(n) {
        links.forEach(function (a) { a.classList.remove('here'); });
        at = n;
        if (n >= 0 && links[n]) {
          links[n].classList.add('here');
          links[n].scrollIntoView({ block: 'nearest' });
        }
      }

      function draw(data) {
        var term = data.term || '';
        var html = '';
        (data.groups || []).forEach(function (g) {
          if (!g.items || !g.items.length) return;
          if (g.title) {
            html += '<div class="grp"><span>' + esc(g.title) + '</span>' +
              (g.items[0].kind === 'recent'
                ? '<button type="button" data-clear>Clear</button>' : '') +
              '</div>';
          }
          g.items.forEach(function (it) {
            html += '<a href="' + esc(it.url) + '" role="option">' +
              iconFor(it.kind) + '<span class="txt">' +
              '<span class="nm">' + mark(it.label, term) + '</span>' +
              (it.note ? '<span class="sub">' + esc(it.note) + '</span>' : '') +
              '</span></a>';
          });
        });
        panel.innerHTML = html ||
          '<div class="none">Nothing matches that yet. Press enter to search anyway.</div>';
        links = $$('a', panel);
        highlight(-1);
        open();

        var clear = $('[data-clear]', panel);
        if (clear) {
          clear.addEventListener('click', function (e) {
            e.preventDefault();
            var token = $('input[name=csrfmiddlewaretoken]');
            fetch('/property/suggest/clear/', {
              method: 'POST',
              headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': token ? token.value : ''
              }
            }).then(function () {
              cache = {};
              panel.innerHTML = '<div class="none">Recent searches cleared.</div>';
              links = [];
            }).catch(function () {});
          });
        }
      }

      function ask() {
        var term = input.value.trim();
        if (cache[term]) { draw(cache[term]); return; }
        fetch(url + '?q=' + encodeURIComponent(term), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
            if (!data) return;
            /* a slow answer for something they have since retyped is stale */
            if (input.value.trim() !== term) return;
            cache[term] = data;
            draw(data);
          })
          .catch(function () { close(); });
      }

      function schedule() {
        var term = input.value.trim();
        if (term === lastTerm) return;
        lastTerm = term;
        clearTimeout(timer);
        /* one letter is not enough to be worth a round trip */
        if (term.length === 1) { close(); return; }
        timer = setTimeout(ask, 180);
      }

      input.addEventListener('input', schedule);
      input.addEventListener('focus', function () {
        lastTerm = null;
        schedule();
      });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { close(); return; }
        if (!panel.classList.contains('open') || !links.length) return;
        if (e.key === 'ArrowDown') {
          e.preventDefault(); highlight((at + 1) % links.length);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault(); highlight((at - 1 + links.length) % links.length);
        } else if (e.key === 'Enter' && at >= 0) {
          e.preventDefault(); links[at].click();
        }
      });
      /* a click inside the panel must land before the blur closes it */
      panel.addEventListener('mousedown', function (e) { e.preventDefault(); });
      input.addEventListener('blur', function () { setTimeout(close, 120); });
      document.addEventListener('click', function (e) {
        if (!wrap.contains(e.target)) close();
      });
    });
  }

  /* ---------------------------------------------------------------- *
     Bulk selection on the agent approval queue
   * ---------------------------------------------------------------- */
  function wireBulk() {
    var bar = $('[data-bulk-bar]');
    if (!bar) return;
    var boxes = $$('input[name="picked"]');
    if (!boxes.length) { bar.remove(); return; }

    var count = $('[data-bulk-count]', bar);
    var all = $('[data-bulk-all]', bar);
    var reason = $('[name="bulk_reason"]', bar);

    function refresh() {
      var picked = boxes.filter(function (b) { return b.checked; });
      var n = picked.length;
      if (count) {
        count.textContent = n
          ? n + ' listing' + (n === 1 ? '' : 's') + ' selected'
          : 'Select listings to act on several at once';
      }
      bar.classList.toggle('idle', n === 0);
      if (all) {
        all.checked = n === boxes.length;
        all.indeterminate = n > 0 && n < boxes.length;
      }
      boxes.forEach(function (b) {
        var card = b.closest('.pcard') || b.closest('[data-row]');
        if (card) card.classList.toggle('picked', b.checked);
      });
    }

    boxes.forEach(function (b) { b.addEventListener('change', refresh); });
    if (all) {
      all.addEventListener('change', function () {
        boxes.forEach(function (b) { b.checked = all.checked; });
        refresh();
      });
    }
    $$('[data-bulk-do]', bar).forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        var n = boxes.filter(function (b) { return b.checked; }).length;
        if (!n) {
          e.preventDefault();
          toast('Tick the listings you want to act on first.', 'warn');
          return;
        }
        if (btn.getAttribute('data-bulk-do') === 'reject' &&
            reason && !reason.value.trim()) {
          e.preventDefault();
          reason.focus();
          toast('Sending listings back needs a reason.', 'warn');
          return;
        }
        var what = btn.getAttribute('data-bulk-do') === 'approve'
          ? 'Publish ' + n + ' listing' + (n === 1 ? '' : 's') + '?'
          : 'Send ' + n + ' listing' + (n === 1 ? '' : 's') + ' back to their owners?';
        if (!window.confirm(what)) e.preventDefault();
      });
    });
    refresh();
  }

  /* ---------------------------------------------------------------- *
     Back to the top
   * ---------------------------------------------------------------- */
  function wireToTop() {
    var b = document.getElementById('toTop');
    if (!b) return;
    b.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' });
    });
    var pending = false;
    function check() {
      pending = false;
      b.classList.toggle('on', window.scrollY > 420);
    }
    window.addEventListener('scroll', function () {
      if (pending) return;
      pending = true;
      requestAnimationFrame(check);
    }, { passive: true });
    check();
  }

  /* auto-tag the obvious blocks so templates stay clean */
  function markReveal() {
    $$('main section, main .pcard, main .pcard-hero, main .cat, main .cat-tile, ' +
       'main .stat, main .reason, ' +
       'main .tile, main .step, main .figure, main .area-link, main > .wrap > .card')
      .forEach(function (el) {
        if (!el.classList.contains('reveal')) el.classList.add('reveal');
      });
  }

  /* ---------------------------------------------------------------- *
     Counters — the headline numbers roll up the first time you see them
   * ---------------------------------------------------------------- */
  function wireCounters() {
    var nodes = $$('[data-count]');
    if (!nodes.length) return;
    if (reduced || !('IntersectionObserver' in window)) return;

    function run(el) {
      var target = parseInt(el.dataset.count, 10);
      if (!isFinite(target) || target <= 0) return;
      var started = null, ms = Math.min(1100, 320 + target * 18);
      function frame(now) {
        if (started === null) started = now;
        var t = Math.min(1, (now - started) / ms);
        /* ease out, so it slows into the real figure */
        var eased = 1 - Math.pow(1 - t, 3);
        el.textContent = Math.round(target * eased);
        if (t < 1) requestAnimationFrame(frame);
        else el.textContent = target;
      }
      el.textContent = '0';
      requestAnimationFrame(frame);
    }

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        run(e.target);
        io.unobserve(e.target);
      });
    }, { threshold: 0.5 });
    nodes.forEach(function (n) { io.observe(n); });
  }

  /* ---------------------------------------------------------------- *
     Photographs fade in once they have actually decoded, so a slow
     connection shows a settled layout rather than images snapping in.
   * ---------------------------------------------------------------- */
  function wireImageFade() {
    $$('.pcard-media img, .cat-tile img, .pcard-hero img, .gallery img, .photo-tile img')
      .forEach(function (img) {
        if (img.dataset.fade !== undefined) return;
        img.dataset.fade = '';
        if (img.complete && img.naturalWidth) { img.classList.add('ready'); return; }
        img.addEventListener('load', function () { img.classList.add('ready'); });
        img.addEventListener('error', function () { img.classList.add('ready'); });
      });
  }

  /* ---------------------------------------------------------------- *
     Go
   * ---------------------------------------------------------------- */
  function boot() {
    wireNavShadow(); wireProgress(); wireMenus(); wireModals(); wireConfirm();
    wirePasswordEyes(); wireFavourites(); wireCompare(); wireStrength();
    wireFilters(); wireOnce(); wireToasts(); wirePreview(); wireThread();
    wirePriceHint(); wireGallery(); wireCounters(); wireImageFade();
    wireVeil(); wireStage(); wireSays(); wireToTop();
    wireSuggest(); wireBulk();
    markReveal(); wireReveal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
