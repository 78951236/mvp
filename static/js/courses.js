/* 课程设置页：顶部学期信息、课程卡片增删改、左侧颜色圆、冲突标红。 */

(() => {
    const sem = window.SEMESTER;
    const listEl = document.getElementById('courseList');
    const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

    /* ------------------------------------------------------ 卡片渲染 */

    function cardHtml(c) {
        const warn = c.has_conflict
            ? '<div class="warn">⚠ 与《' + App.escapeHtml((c.conflict_with || []).join('》《')) + '》时间冲突，请修改</div>'
            : '';
        const note = c.note ? '<div class="meta">备注：' + App.escapeHtml(c.note) + '</div>' : '';
        return '' +
            '<div class="card course-card' + (c.has_conflict ? ' conflict' : '') + '">' +
                '<span class="dot" style="background:' + App.escapeHtml(c.color) + '"></span>' +
                '<div class="line1">' +
                    '<span class="name">' + App.escapeHtml(c.name) + '</span>' +
                    '<span class="meta">' + App.escapeHtml(c.teacher) + '</span>' +
                '</div>' +
                '<div class="meta">' + App.escapeHtml(c.weekday_text) + '　' +
                    App.escapeHtml(c.start_text) + ' - ' + App.escapeHtml(c.end_text) + '</div>' +
                '<div class="meta">' + App.escapeHtml(c.start_time) + ' - ' + App.escapeHtml(c.end_time) +
                    '　' + App.escapeHtml(c.location) + '</div>' +
                note + warn +
                '<div class="ops">' +
                    '<button class="btn btn-outline btn-sm" data-act="edit" data-id="' + c.id + '">设置</button>' +
                    '<button class="btn btn-danger btn-sm" data-act="del" data-id="' + c.id + '">删除</button>' +
                '</div>' +
            '</div>';
    }

    let courses = [];

    async function load() {
        try {
            const data = await App.api('/api/semesters/' + sem.id + '/courses');
            courses = data.courses || [];
            if (!courses.length) {
                listEl.innerHTML = '<div class="empty-state"><div class="big">这门学期还没有课程，点右上角「+ 添加课程」</div></div>';
                return;
            }
            listEl.innerHTML = courses.map(cardHtml).join('');
            listEl.querySelectorAll('button[data-act]').forEach((btn) => {
                btn.addEventListener('click', () => handle(btn.dataset.act, Number(btn.dataset.id)));
            });
        } catch (err) {
            App.fail(err);
        }
    }

    async function handle(act, id) {
        const course = courses.find((c) => c.id === id);
        if (!course) return;
        if (act === 'edit') {
            openCourseModal(course);
            return;
        }
        const ok = await App.confirmDialog('删除课程', '确定删除这门课吗');
        if (!ok) return;
        try {
            await App.api('/api/courses/' + id, { method: 'DELETE' });
            await load();
        } catch (err) {
            App.fail(err);
        }
    }

    /* ------------------------------------------------------ 课程表单 */

    function formHtml(c) {
        const checked = new Set((c && c.weekday_list) || []);
        const boxes = WEEKDAYS.map((label, i) => {
            const v = i + 1;
            return '<label><input type="checkbox" class="wd" value="' + v + '"' +
                (checked.has(v) ? ' checked' : '') + '>' + label + '</label>';
        }).join('');
        return '' +
            '<div class="form-error" id="formError"></div>' +
            '<div class="field"><label>课程名称</label><input type="text" id="fName" value="' +
                App.escapeHtml(c ? c.name : '') + '"></div>' +
            '<div class="field-row">' +
                '<div class="field"><label>任课老师</label><input type="text" id="fTeacher" value="' +
                    App.escapeHtml(c ? c.teacher : '') + '"></div>' +
                '<div class="field"><label>上课地点</label><input type="text" id="fLocation" value="' +
                    App.escapeHtml(c ? c.location : '') + '"></div>' +
            '</div>' +
            '<div class="field"><label>周几（可多选）</label><div class="weekday-picker">' + boxes + '</div></div>' +
            '<div class="field-row">' +
                '<div class="field"><label>持续时间 · 起</label><input type="date" id="fStartDate" value="' +
                    App.escapeHtml(c ? c.start_date : sem.start_date) + '"></div>' +
                '<div class="field"><label>持续时间 · 止</label><input type="date" id="fEndDate" value="' +
                    App.escapeHtml(c ? c.end_date : sem.end_date) + '"></div>' +
            '</div>' +
            '<div class="field-row">' +
                '<div class="field"><label>上课时间</label><input type="time" id="fStartTime" value="' +
                    App.escapeHtml(c ? c.start_time : '08:00') + '"></div>' +
                '<div class="field"><label>下课时间</label><input type="time" id="fEndTime" value="' +
                    App.escapeHtml(c ? c.end_time : '09:40') + '"></div>' +
            '</div>' +
            '<div class="field-row">' +
                '<div class="field"><label>颜色（可选）</label><input type="color" id="fColor" value="' +
                    App.escapeHtml(c ? c.color : '#FFFFFF') + '"></div>' +
                '<div class="field" style="flex:2 1 0"><label>备注（可选）</label><input type="text" id="fNote" value="' +
                    App.escapeHtml(c ? c.note : '') + '"></div>' +
            '</div>';
    }

    function openCourseModal(course) {
        const isEdit = !!course;
        App.openModal({
            title: isEdit ? '修改课程' : '添加课程',
            body: formHtml(course),
            foot: '<button class="btn btn-outline" data-act="cancel">取消</button>' +
                  '<button class="btn btn-primary" data-act="save">确定</button>',
            onMount: (modal) => {
                const errBox = modal.querySelector('#formError');
                modal.querySelector('[data-act="cancel"]').addEventListener('click', App.closeModal);
                modal.querySelector('[data-act="save"]').addEventListener('click', async () => {
                    const weekdays = Array.from(modal.querySelectorAll('.wd:checked')).map((el) => el.value);
                    const body = {
                        name: modal.querySelector('#fName').value,
                        teacher: modal.querySelector('#fTeacher').value,
                        location: modal.querySelector('#fLocation').value,
                        weekdays: weekdays,
                        start_date: modal.querySelector('#fStartDate').value,
                        end_date: modal.querySelector('#fEndDate').value,
                        start_time: modal.querySelector('#fStartTime').value,
                        end_time: modal.querySelector('#fEndTime').value,
                        color: modal.querySelector('#fColor').value,
                        note: modal.querySelector('#fNote').value,
                    };
                    try {
                        if (isEdit) {
                            await App.api('/api/courses/' + course.id, { method: 'PUT', body });
                        } else {
                            await App.api('/api/semesters/' + sem.id + '/courses', { method: 'POST', body });
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

    /* ---------------------------------------------------- 顶部学期信息 */

    document.getElementById('saveSemesterBtn').addEventListener('click', async () => {
        const body = {
            seq_no: document.getElementById('seqNo').value,
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
        };
        try {
            const data = await App.api('/api/semesters/' + sem.id, { method: 'PUT', body });
            Object.assign(sem, data.semester);
            App.toast('学期信息已保存');
        } catch (err) {
            App.fail(err);
        }
    });

    document.getElementById('addCourseBtn').addEventListener('click', () => openCourseModal(null));

    load();
})();
