// Light/dark toggle. Light is the default; dark only when the visitor picks it.
// The <head> script in index.html applies the saved choice before first paint;
// this file wires the button and tells the maps (app.js) when the theme changes.
(() => {
    const root = document.documentElement;
    const button = document.getElementById('theme-toggle');
    if (!button) return;

    const sync = () => button.setAttribute('aria-pressed', String(root.dataset.theme === 'dark'));
    sync();

    button.addEventListener('click', () => {
        root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem('theme', root.dataset.theme); } catch {}
        sync();
        document.dispatchEvent(new CustomEvent('themechange', { detail: root.dataset.theme }));
    });
})();
