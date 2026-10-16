/* 设置 → 学期：列表、新增弹窗、删除确认框、设为默认。 */

(() => {
    const listEl = document.getElementById('semList');

    function cardHtml(s) {
        const defaultOp = s.is_default
            ? '<button class="btn-link is-default" disabled>默认学期</button>'
            : '<button class="btn-link" data-act="default" data-id="' + s.id + '">设为默认</button>';
        return '' +
            '<div class="card sem-card">' +
                '<div>' +
                    '<span class="seq">第 ' + s.seq_no + ' 学期</span>' +
                    '<span class="dates">' + App.escapeHtml(s.start_text) + ' - ' +
                        App.escapeHtml(s.end_text) + '</span>' +
                '</div>' +
                '<div class="ops">' +
                    '<button class="btn btn-outline btn-sm" data-act="edit" data-id="' + s.id + '">设置</button>' +
                    '<button class="btn btn-danger btn-sm" data-act="del" data-id="' + s.id + '">删除</button>' +
                    defaultOp +
                '</div>' +
            '</div>';
    }

    async function load() {
        try {
            const data = await App.api('/api/semesters');
            const items = data.semesters || [];
            if (!items.length) {
                listEl.innerHTML = '<div class="empty-state"><div class="big">还没有学期，点右上角「+ 添加学期」</div></div>';
                return;
            }
            listEl.innerHTML = items.map(cardHtml).join('');
            listEl.querySelectorAll('button[data-act]').forEach((btn) => {
                btn.addEventListener('click', () => handle(btn.dataset.act, Number(btn.dataset.id)));
            });
        } catch (err) {
            App.fail(err);
        }
    }

    async function handle(act, id) {
        if (act === 'edit') {
            location.href = '/semesters/' + id + '/courses';
            return;
        }
        if (act === 'default') {
            try {
                await App.api('/api/semesters/' + id + '/default', { method: 'POST' });
                await load();
            } catch (err) {
                App.fail(err);
            }
            return;
        }
        if (act === 'del') {
            const ok = await App.confirmDialog('删除学期', '确定删除这个学期吗？该学期下的课程会一起删除');
            if (!ok) return;
            try {
                await App.api('/api/semesters/' + id, { method: 'DELETE' });
                await load();
            } catch (err) {
                App.fail(err);
            }
        }
    }

    function openAddModal() {
        App.openModal({
            title: '添加学期',
            body:
                '<div class="form-error" id="formError"></div>' +
                '<div class="field"><label>学期序号（第几学期）</label>' +
                    '<input type="number" min="1" step="1" id="seqNo" placeholder="例如 1"></div>' +
                '<div class="field-row">' +
                    '<div class="field"><label>起始日期</label><input type="date" id="startDate"></div>' +
                    '<div class="field"><label>结束日期</label><input type="date" id="endDate"></div>' +
                '</div>' +
                '<div class="field"><span class="hint">第一周 = 起始日所在的那一周（一周以周一开始）</span></div>',
            foot: '<button class="btn btn-outline" data-act="cancel">取消</button>' +
                  '<button class="btn btn-primary" data-act="save">确定</button>',
            onMount: (modal) => {
                const errBox = modal.querySelector('#formError');
                modal.querySelector('[data-act="cancel"]').addEventListener('click', App.closeModal);
                modal.querySelector('[data-act="save"]').addEventListener('click', async () => {
                    const body = {
                        seq_no: modal.querySelector('#seqNo').value,
                        start_date: modal.querySelector('#startDate').value,
                        end_date: modal.querySelector('#endDate').value,
                    };
                    try {
                        await App.api('/api/semesters', { method: 'POST', body });
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

    document.getElementById('addSemesterBtn').addEventListener('click', openAddModal);
    load();
})();
