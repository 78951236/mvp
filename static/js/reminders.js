/* 设置 → 提醒：列表、新增/修改弹窗、单条开关、删除确认。 */

(() => {
    const listEl = document.getElementById('reminderList');
    let options = { events: [], scopes: [], extras: [] };
    let reminders = [];

    /* ------------------------------------------------------ 一行提醒 */

    function rowHtml(r) {
        const extras = (r.extra_labels || []).length
            ? (r.extra_labels || []).map((t) => '<span class="chip">' + App.escapeHtml(t) + '</span>').join('')
            : '<span class="chip">无</span>';
        return '' +
            '<div class="card reminder-card' + (r.enabled ? '' : ' is-off') + '">' +
                '<div class="reminder-main">' +
                    '<label class="switch">' +
                        '<input type="checkbox" class="toggle" data-id="' + r.id + '"' +
                            (r.enabled ? ' checked' : '') + '>' +
                        '<span>' + (r.enabled ? '开' : '关') + '</span>' +
                    '</label>' +
                    '<strong>' + App.escapeHtml(r.event_label) + '</strong>' +
                    '<span>' + App.escapeHtml(r.offset_text) + '</span>' +
                    '<span>' + App.escapeHtml(r.direction_label) + '</span>' +
                    '<span>' + App.escapeHtml(r.scope_label) + '</span>' +
                '</div>' +
                '<div class="reminder-foot">' +
                    '<div>附加信息：' + extras + '</div>' +
                    '<div class="ops">' +
                        '<button class="btn btn-outline btn-sm" data-act="edit" data-id="' + r.id + '">设置</button>' +
                        '<button class="btn btn-danger btn-sm" data-act="del" data-id="' + r.id + '">删除</button>' +
                    '</div>' +
                '</div>' +
            '</div>';
    }

    async function load() {
        try {
            const data = await App.api('/api/reminders');
            options = data.options || options;
            reminders = data.reminders || [];
            if (!reminders.length) {
                listEl.innerHTML = '<div class="empty-state"><div class="big">还没有提醒，点右上角「+ 添加提醒」</div></div>';
                return;
            }
            listEl.innerHTML = reminders.map(rowHtml).join('');

            listEl.querySelectorAll('button[data-act]').forEach((btn) => {
                btn.addEventListener('click', () => handle(btn.dataset.act, Number(btn.dataset.id)));
            });
            listEl.querySelectorAll('input.toggle').forEach((box) => {
                box.addEventListener('change', () => toggle(Number(box.dataset.id)));
            });
        } catch (err) {
            App.fail(err);
        }
    }

    async function toggle(id) {
        try {
            await App.api('/api/reminders/' + id + '/toggle', { method: 'POST' });
            await load();
        } catch (err) {
            App.fail(err);
            await load();
        }
    }

    async function handle(act, id) {
        const item = reminders.find((r) => r.id === id);
        if (!item) return;
        if (act === 'edit') {
            openModal(item);
            return;
        }
        const ok = await App.confirmDialog('删除提醒', '确定删除这条提醒吗');
        if (!ok) return;
        try {
            await App.api('/api/reminders/' + id, { method: 'DELETE' });
            await load();
        } catch (err) {
            App.fail(err);
        }
    }

    /* -------------------------------------------------------- 添加/修改 */

    function selectHtml(id, items, current) {
        return '<select id="' + id + '">' + items.map((it) =>
            '<option value="' + App.escapeHtml(it.value) + '"' +
            (it.value === current ? ' selected' : '') + '>' + App.escapeHtml(it.label) + '</option>'
        ).join('') + '</select>';
    }

    function numberOptions(max) {
        const out = [];
        for (let i = 0; i <= max; i++) {
            out.push({ value: String(i), label: String(i).padStart(2, '0') });
        }
        return out;
    }

    function formHtml(r) {
        const hours = r ? r.offset_hours : 0;
        const minutes = r ? r.offset_minutes : 30;
        const direction = r ? r.direction : 'before';
        const extras = new Set((r && r.extra_list) || ['name', 'location']);
        const boxes = options.extras.map((it) =>
            '<label><input type="checkbox" class="extra" value="' + App.escapeHtml(it.value) + '"' +
            (extras.has(it.value) ? ' checked' : '') + '>' + App.escapeHtml(it.label) + '</label>'
        ).join('');
        return '' +
            '<div class="form-error" id="formError"></div>' +
            '<div class="field"><label>事件</label>' +
                selectHtml('fEvent', options.events, r ? r.event : 'class_start') + '</div>' +
            '<div class="field">' +
                '<label>时间差</label>' +
                '<div class="field-row">' +
                    '<div>' + selectHtml('fHours', numberOptions(23, hours), String(hours)) + '</div>' +
                    '<div>' + selectHtml('fMinutes', numberOptions(59, minutes), String(minutes)) + '</div>' +
                    '<div>' + selectHtml('fDirection', [{ value: 'before', label: '前' }, { value: 'after', label: '后' }], direction) + '</div>' +
                '</div>' +
                '<span class="hint">时（0~23）、分（0~59）、前 / 后</span>' +
            '</div>' +
            '<div class="field"><label>提醒范围</label>' +
                selectHtml('fScope', options.scopes, r ? r.scope : 'next_class') + '</div>' +
            '<div class="field"><label>附加信息（可多选）</label>' +
                '<div class="weekday-picker">' + boxes + '</div></div>' +
            '<div class="field"><label class="switch">' +
                '<input type="checkbox" id="fEnabled"' + (!r || r.enabled ? ' checked' : '') + '> 开启这条提醒</label></div>';
    }

    function openModal(r) {
        const isEdit = !!r;
        App.openModal({
            title: isEdit ? '修改提醒' : '添加提醒',
            body: formHtml(r),
            foot: '<button class="btn btn-outline" data-act="cancel">取消</button>' +
                  '<button class="btn btn-primary" data-act="save">确定</button>',
            onMount: (modal) => {
                const errBox = modal.querySelector('#formError');
                modal.querySelector('[data-act="cancel"]').addEventListener('click', App.closeModal);
                modal.querySelector('[data-act="save"]').addEventListener('click', async () => {
                    const body = {
                        event: modal.querySelector('#fEvent').value,
                        offset_hours: modal.querySelector('#fHours').value,
                        offset_minutes: modal.querySelector('#fMinutes').value,
                        direction: modal.querySelector('#fDirection').value,
                        scope: modal.querySelector('#fScope').value,
                        extra_fields: Array.from(modal.querySelectorAll('.extra:checked')).map((el) => el.value),
                        enabled: modal.querySelector('#fEnabled').checked,
                    };
                    try {
                        if (isEdit) {
                            await App.api('/api/reminders/' + r.id, { method: 'PUT', body });
                        } else {
                            await App.api('/api/reminders', { method: 'POST', body });
                        }
                        App.closeModal();
                        await load();
                    } catch (err) {
                        errBox.textContent = err.message;
                        errBox.style.display = 'block';
                    }
                });
            },
        });
    }

    document.getElementById('addReminderBtn').addEventListener('click', () => openModal(null));
    load();
})();
