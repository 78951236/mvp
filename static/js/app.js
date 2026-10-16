/* 公共脚本：接口调用、弹窗、确认框、菜单栏收起/抽屉。 */

const App = (() => {

    /* ---------------------------------------------------------- 接口 */

    async function api(path, { method = 'GET', body = null } = {}) {
        const opts = { method, headers: {} };
        if (body !== null) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        }
        const res = await fetch(path, opts);
        let data = null;
        try {
            data = await res.json();
        } catch (e) {
            throw new Error('服务器返回了看不懂的内容（HTTP ' + res.status + '）');
        }
        if (!res.ok || data.ok === false) {
            throw new Error((data && data.error) || ('操作失败（HTTP ' + res.status + '）'));
        }
        return data;
    }

    /* ------------------------------------------------------------ 工具 */

    function escapeHtml(text) {
        return String(text === null || text === undefined ? '' : text)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    let toastTimer = null;

    function toast(message) {
        const old = document.querySelector('.toast');
        if (old) old.remove();
        const el = document.createElement('div');
        el.className = 'toast';
        el.textContent = message;
        document.body.appendChild(el);
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => el.remove(), 2600);
    }

    function fail(err) {
        console.error(err);
        toast(err && err.message ? err.message : '操作失败');
    }

    /* ------------------------------------------------------------ 弹窗 */

    function openModal({ title, body, foot, onMount }) {
        closeModal();
        const mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML =
            '<div class="modal" role="dialog" aria-modal="true">' +
                '<div class="modal-head"><span>' + escapeHtml(title) + '</span>' +
                    '<button class="modal-close" aria-label="关闭">✕</button></div>' +
                '<div class="modal-body">' + (body || '') + '</div>' +
                (foot ? '<div class="modal-foot">' + foot + '</div>' : '') +
            '</div>';

        // 点遮罩关闭
        mask.addEventListener('click', (e) => { if (e.target === mask) closeModal(); });
        mask.querySelector('.modal-close').addEventListener('click', closeModal);
        document.body.appendChild(mask);

        const modal = mask.querySelector('.modal');
        const first = modal.querySelector('input, select, textarea, button.btn-primary');
        if (first) setTimeout(() => first.focus(), 30);
        if (onMount) onMount(modal, mask);
        return modal;
    }

    function closeModal() {
        const old = document.querySelector('.modal-mask');
        if (old) old.remove();
    }

    /* 删除等危险操作必须先弹确认框（02 文档 3.3） */
    function confirmDialog(title, text, okText = '确定删除') {
        return new Promise((resolve) => {
            const modal = openModal({
                title,
                body: '<div>' + escapeHtml(text) + '</div>',
                foot: '<button class="btn btn-outline" data-act="cancel">取消</button>' +
                      '<button class="btn btn-danger" data-act="ok">' + escapeHtml(okText) + '</button>',
            });
            modal.querySelector('[data-act="cancel"]').addEventListener('click', () => {
                closeModal();
                resolve(false);
            });
            modal.querySelector('[data-act="ok"]').addEventListener('click', () => {
                closeModal();
                resolve(true);
            });
        });
    }

    /* -------------------------------------------------- 菜单栏 / 抽屉 */

    function initLayout() {
        const body = document.body;
        const collapseBtn = document.getElementById('collapseBtn');
        const expandBtn = document.getElementById('expandBtn');
        const hamburger = document.getElementById('hamburger');
        const overlay = document.getElementById('overlay');
        const groupTitle = document.getElementById('navGroupTitle');
        const group = document.getElementById('navGroup');
        const sub = document.getElementById('navSub');
        const isNarrow = () => window.matchMedia('(max-width: 767px)').matches;

        // 桌面上的收起状态记在本地，下次打开还是收起的样子
        if (!isNarrow() && localStorage.getItem('navCollapsed') === '1') {
            body.classList.add('nav-collapsed');
        }
        if (collapseBtn) {
            collapseBtn.addEventListener('click', () => {
                body.classList.add('nav-collapsed');
                localStorage.setItem('navCollapsed', '1');
            });
        }
        if (expandBtn) {
            expandBtn.addEventListener('click', () => {
                body.classList.remove('nav-collapsed');
                localStorage.setItem('navCollapsed', '0');
            });
        }
        if (hamburger) {
            hamburger.addEventListener('click', () => body.classList.toggle('drawer-open'));
        }
        if (overlay) {
            overlay.addEventListener('click', () => body.classList.remove('drawer-open'));
        }
        document.querySelectorAll('.sidebar a.nav-item').forEach((a) => {
            a.addEventListener('click', () => body.classList.remove('drawer-open'));
        });
        if (groupTitle && group && sub) {
            groupTitle.addEventListener('click', () => {
                sub.classList.toggle('collapsed');
                group.classList.toggle('open');
            });
        }

        // 页面不可缩放：双指缩放无效（iOS 的 gesture 事件）
        ['gesturestart', 'gesturechange', 'gestureend'].forEach((evt) => {
            document.addEventListener(evt, (e) => e.preventDefault(), { passive: false });
        });
    }

    // 阻止双击放大
    let lastTouch = 0;
    document.addEventListener('touchend', (e) => {
        const now = Date.now();
        if (now - lastTouch <= 300) e.preventDefault();
        lastTouch = now;
    }, { passive: false });

    document.addEventListener('DOMContentLoaded', initLayout);

    return { api, escapeHtml, toast, fail, openModal, closeModal, confirmDialog };
})();
