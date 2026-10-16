/* 课表页：当周 7 列 + 时间轴渲染、点方块弹窗、空态与范围外提示。
   坐标轴同一学期内固定（03 文档第六节）；冲突课程不画。 */

(() => {
    const PX_PER_MIN = 1.2;     // 1 分钟 = 1.2 像素
    const MIN_GRID_H = 460;
    const NARROW = 768;

    const root = document.getElementById('schedRoot');
    let cache = null;

    function gridHeight(spanMin) {
        return Math.max(Math.round(spanMin * PX_PER_MIN), MIN_GRID_H);
    }

    function blockLabel(block) {
        return window.innerWidth < NARROW ? (block.short_name || block.name) : block.name;
    }

    function blockHtml(block) {
        const top = block.top_pct;
        const height = block.height_pct;
        return '<div class="block" data-id="' + block.id + '"' +
            ' style="top:' + top + '%;height:' + height + '%;' +
            'background:' + App.escapeHtml(block.color) + ';' +
            'color:' + App.escapeHtml(block.text_color) + ';"' +
            ' title="' + App.escapeHtml(block.name) + '">' +
            '<span class="block-name">' + App.escapeHtml(blockLabel(block)) + '</span>' +
            '</div>';
    }

    function renderEmpty(title, withButton) {
        root.innerHTML =
            '<div class="empty-state">' +
                '<div class="big">' + App.escapeHtml(title) + '</div>' +
                (withButton ? '<a class="btn btn-primary" href="/settings/semesters">前往设置</a>' : '') +
            '</div>';
    }

    function render(data) {
        cache = data;

        if (!data.has_default) {
            renderEmpty('你还没有设置默认学期', true);
            return;
        }
        if (!data.in_range) {
            renderEmpty('不在学期范围内', false);
            return;
        }

        const h = gridHeight(data.axis.span_min);
        const head =
            '<div class="sched-head">' +
                '<div><strong>第 ' + data.semester.seq_no + ' 学期</strong></div>' +
                '<div class="center">第 ' + data.week_index + ' 周</div>' +
                '<div><button class="btn btn-outline" id="editCourses">编辑课程</button></div>' +
            '</div>';

        const cols = data.days.map((d) =>
            '<div class="grid-col' + (d.is_today ? ' is-today' : '') + '" data-date="' + d.date + '">' +
                d.blocks.map(blockHtml).join('') +
            '</div>').join('');

        const labels = data.days.map((d) =>
            '<div class="' + (d.is_today ? 'is-today' : '') + '">' + d.label + '</div>').join('');

        root.innerHTML = head +
            '<div class="grid-area">' +
                '<div class="grid-cols" style="--grid-h:' + h + 'px">' + cols + '</div>' +
                '<div class="grid-labels">' + labels + '</div>' +
            '</div>';

        document.getElementById('editCourses').addEventListener('click', () => {
            location.href = '/semesters/' + data.semester.id + '/courses';
        });

        root.querySelectorAll('.block').forEach((el) => {
            // 按方块实际高度算能铺几行，让超长课名以省略号收尾（P3）
            const heightPx = el.getBoundingClientRect().height;
            const lines = Math.max(1, Math.floor((heightPx - 6) / 16.25));   // 6=上下 padding，16.25=13px×1.25 行高
            const nameEl = el.querySelector('.block-name');
            if (nameEl) nameEl.style.webkitLineClamp = lines;
            el.addEventListener('click', () => showBlockDetail(Number(el.dataset.id)));
        });
    }

    function showBlockDetail(id) {
        const block = (cache.days || [])
            .flatMap((d) => d.blocks)
            .find((b) => b.id === id);
        if (!block) return;

        App.openModal({
            title: '课程信息',
            body:
                '<div class="detail-row"><span class="k">课程名字</span><span>' + App.escapeHtml(block.name) + '</span></div>' +
                '<div class="detail-row"><span class="k">任课老师</span><span>' + App.escapeHtml(block.teacher) + '</span></div>' +
                '<div class="detail-row"><span class="k">上下课时间</span><span>' +
                    App.escapeHtml(block.start_time) + ' - ' + App.escapeHtml(block.end_time) + '</span></div>' +
                '<div class="detail-row"><span class="k">上课地点</span><span>' + App.escapeHtml(block.location) + '</span></div>',
            foot: '<button class="btn btn-outline" onclick="App.closeModal()">关闭</button>',
        });
    }

    async function load() {
        try {
            render(await App.api('/api/schedule'));
        } catch (err) {
            App.fail(err);
        }
    }

    let resizeTimer = null;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => { if (cache) render(cache); }, 200);
    });

    load();
})();
