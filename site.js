(() => {
  const scene = document.querySelector('.ambient-scene');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
  let ambientFrame = 0;
  const resetAmbient = () => {
    cancelAnimationFrame(ambientFrame);
    ambientFrame = 0;
    scene.style.setProperty('--ambient-x', '0px');
    scene.style.setProperty('--ambient-y', '0px');
  };
  const syncAmbient = () => {
    document.documentElement.classList.toggle('ambient-paused', document.hidden || reducedMotion.matches);
    if (document.hidden || reducedMotion.matches || !finePointer.matches) resetAmbient();
  };
  document.addEventListener('pointermove', event => {
    if (reducedMotion.matches || !finePointer.matches || document.hidden) return;
    if (ambientFrame) cancelAnimationFrame(ambientFrame);
    const x = (event.clientX / innerWidth - .5) * 20;
    const y = (event.clientY / innerHeight - .5) * 14;
    ambientFrame = requestAnimationFrame(() => {
      scene.style.setProperty('--ambient-x', `${x.toFixed(2)}px`);
      scene.style.setProperty('--ambient-y', `${y.toFixed(2)}px`);
      ambientFrame = 0;
    });
  }, {passive: true});
  document.documentElement.addEventListener('pointerleave', resetAmbient);
  document.addEventListener('visibilitychange', syncAmbient);
  reducedMotion.addEventListener('change', syncAmbient);
  finePointer.addEventListener('change', syncAmbient);
  syncAmbient();

  const menu = document.querySelector('#menuToggle');
  const navigation = document.querySelector('#navLinks');
  const closeMenu = () => {
    navigation.classList.remove('is-open');
    menu.setAttribute('aria-expanded', 'false');
    menu.setAttribute('aria-label', 'Open navigation');
  };
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    navigation.classList.toggle('is-open', open);
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  });
  navigation.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && menu.getAttribute('aria-expanded') === 'true') {
      closeMenu();
      menu.focus();
    }
  });

  const dialog = document.querySelector('#previewDialog');
  const tabs = [...dialog.querySelectorAll('[role="tab"]')];
  const panels = [...dialog.querySelectorAll('[role="tabpanel"]')];
  let opener;
  const selectPreview = (mode, focus = false) => {
    tabs.forEach(tab => {
      const selected = tab.dataset.previewTab === mode;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && focus) tab.focus();
    });
    panels.forEach(panel => { panel.hidden = panel.dataset.previewPanel !== mode; });
  };
  document.querySelectorAll('[data-preview]').forEach(button => {
    button.addEventListener('click', () => {
      opener = button;
      selectPreview(button.dataset.preview);
      dialog.showModal();
      document.body.classList.add('dialog-open');
    });
  });
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectPreview(tab.dataset.previewTab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        selectPreview(tabs[next].dataset.previewTab, true);
      }
    });
  });
  dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    document.body.classList.remove('dialog-open');
    opener?.focus();
  });
  document.querySelector('#year').textContent = String(new Date().getFullYear());
})();
