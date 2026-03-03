/**
 * CourseGrab 前端应用主模块
 */

// ==================== 全局状态 ====================
const state = {
    currentPage: 'dashboard',
    searchResults: [],
    queueTasks: [],
    selectedCourses: [],
    scheduleData: null,
    currentSemester: null,
    isGrabbing: false,
};

// ==================== 页面导航 ====================
function navigateTo(page) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    
    // 显示目标页面
    const targetPage = document.getElementById(`page-${page}`);
    if (targetPage) {
        targetPage.style.display = 'block';
    }
    
    // 更新导航状态
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    state.currentPage = page;
    
    // 加载页面数据
    switch (page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'search':
            loadDepartments();
            break;
        case 'queue':
            loadQueue();
            startQueueAutoRefresh();
            break;
        case 'schedule':
            loadSchedule();
            break;
        case 'settings':
            loadSettings();
            break;
    }
    
    // 离开队列页面时停止自动刷新
    if (page !== 'queue') {
        stopQueueAutoRefresh();
    }
}

// ==================== Toast 提示 ====================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? 'fa-check-circle' : 
                 type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle';
    
    toast.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    
    // 触发动画
    setTimeout(() => toast.classList.add('show'), 10);
    
    // 3秒后移除
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== 自定义确认弹窗 ====================
function showConfirmModal(title, message, onConfirm) {
    // 移除已有的弹窗
    const existing = document.getElementById('confirm-modal');
    if (existing) existing.remove();
    
    const modal = document.createElement('div');
    modal.id = 'confirm-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <i class="fas fa-exclamation-triangle" style="color: var(--warning);"></i>
                <h3>${title}</h3>
            </div>
            <div class="modal-body">
                <p>${message}</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="closeConfirmModal()">取消</button>
                <button class="btn btn-danger" id="modal-confirm-btn">确定</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 添加动画
    setTimeout(() => modal.classList.add('show'), 10);
    
    // 绑定确认按钮
    document.getElementById('modal-confirm-btn').onclick = async () => {
        closeConfirmModal();
        if (onConfirm) await onConfirm();
    };
    
    // 点击遮罩关闭
    modal.onclick = (e) => {
        if (e.target === modal) closeConfirmModal();
    };
}

function closeConfirmModal() {
    const modal = document.getElementById('confirm-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
    }
}

// ==================== 移动端菜单 ====================
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    sidebar.classList.toggle('mobile-open');
    overlay.classList.toggle('show');
}

function closeSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    
    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('show');
}

// ==================== 仪表盘 ====================
// 标记仪表盘是否已同步过课程
let hasDashboardSynced = false;

async function loadDashboard() {
    // 加载凭证状态
    await checkCredentialStatus();
    
    // 加载选课阶段信息
    await loadSystemInfo();
    
    // 首次加载时同步已选课程
    if (!hasDashboardSynced) {
        hasDashboardSynced = true;
        try {
            await API.courses.getSelected();
        } catch (e) {
            console.log('同步课程失败:', e);
        }
    }
    
    // 加载统计数据
    const queueResult = await API.queue.getList();
    if (queueResult.success) {
        const tasks = queueResult.data;
        document.getElementById('stat-queue').textContent = 
            tasks.filter(t => t.status === 'pending' || t.status === 'grabbing').length;
        document.getElementById('stat-success').textContent = 
            tasks.filter(t => t.status === 'success').length;
    }
    
    const selectedResult = await API.courses.getLocalSelected();
    if (selectedResult.success) {
        document.getElementById('stat-selected').textContent = selectedResult.data.length;
    }
}

async function loadSystemInfo() {
    const phaseEl = document.getElementById('phase-info');
    if (!phaseEl) return;
    
    const result = await API.auth.getSystemInfo();
    
    if (!result.success || !result.data.phase_name) {
        phaseEl.innerHTML = `
            <div class="phase-content">
                <i class="fas fa-info-circle"></i>
                <div class="phase-details">
                    <span class="phase-name">暂无选课阶段</span>
                    <span class="phase-time">请检查凭证状态</span>
                </div>
            </div>
        `;
        return;
    }
    
    const data = result.data;
    const startTime = data.phase_start ? new Date(data.phase_start.replace(' ', 'T')) : null;
    const endTime = data.phase_end ? new Date(data.phase_end.replace(' ', 'T')) : null;
    const now = new Date();
    
    let statusText = '';
    let statusClass = '';
    
    if (startTime && endTime) {
        if (now < startTime) {
            statusText = '未开始';
            statusClass = 'pending';
        } else if (now > endTime) {
            statusText = '已结束';
            statusClass = 'ended';
        } else {
            // 计算剩余时间
            const remaining = endTime - now;
            const hours = Math.floor(remaining / (1000 * 60 * 60));
            const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60));
            statusText = `剩余 ${hours}小时${minutes}分钟`;
            statusClass = 'active';
        }
    }
    
    phaseEl.innerHTML = `
        <div class="phase-content">
            <i class="fas fa-clock ${statusClass}"></i>
            <div class="phase-details">
                <span class="phase-name">${data.phase_name}</span>
                <span class="phase-time">
                    ${data.phase_start || ''} ~ ${data.phase_end || ''}
                </span>
                ${statusText ? `<span class="phase-status ${statusClass}">${statusText}</span>` : ''}
            </div>
        </div>
    `;
}

async function checkCredentialStatus() {
    const result = await API.auth.getStatus();
    const statusEl = document.getElementById('credential-status');
    const userInfoEl = document.getElementById('user-info');
    
    if (result.success && result.data.has_cookies) {
        if (result.data.is_valid) {
            statusEl.innerHTML = `
                <div class="status-indicator valid"></div>
                <span>凭证有效</span>
            `;
            // 显示用户信息
            if (userInfoEl && result.data.student_name) {
                userInfoEl.innerHTML = `
                    <div class="user-info-content">
                        <i class="fas fa-user-graduate"></i>
                        <div class="user-details">
                            <span class="user-name">${result.data.student_name}</span>
                            <span class="user-id">${result.data.student_id || ''}</span>
                        </div>
                    </div>
                `;
                userInfoEl.style.display = 'flex';
            }
        } else {
            statusEl.innerHTML = `
                <div class="status-indicator expired"></div>
                <span>凭证已失效</span>
            `;
            if (userInfoEl) userInfoEl.style.display = 'none';
        }
    } else {
        statusEl.innerHTML = `
            <div class="status-indicator"></div>
            <span>未配置凭证</span>
        `;
        if (userInfoEl) userInfoEl.style.display = 'none';
    }
}


// ==================== Cookie 管理 ====================
function parseCookieString(cookieStr) {
    const cookies = {};
    cookieStr.split(';').forEach(part => {
        const [key, ...valueParts] = part.trim().split('=');
        if (key) {
            cookies[key.trim()] = valueParts.join('=').trim();
        }
    });
    return cookies;
}

async function saveCookies() {
    const input = document.getElementById('cookie-input').value.trim();
    if (!input) {
        showToast('请输入 Cookie', 'error');
        return;
    }
    
    const cookies = parseCookieString(input);
    
    // 检查必需的 Cookie
    const required = ['JSESSIONID', 'GS_SESSIONID'];
    const missing = required.filter(k => !cookies[k]);
    
    if (missing.length > 0) {
        showToast(`缺少必需的 Cookie: ${missing.join(', ')}`, 'error');
        return;
    }
    
    const result = await API.auth.updateCookies(cookies);
    
    if (result.success) {
        showToast('凭证保存成功', 'success');
        
        // 更新凭证状态和用户信息
        await checkCredentialStatus();
        
        // 更新选课阶段信息
        await loadSystemInfo();
        
        // 同步已选课程（清除旧用户数据，获取新用户数据）
        await API.courses.getSelected();
        
        // 刷新课表相关数据
        loadMiniSchedule();
        
        // 如果当前在课表页面，刷新主课表
        if (state.currentPage === 'schedule') {
            loadSchedule();
        }
    } else {
        showToast(result.message || '保存失败', 'error');
    }
}

async function validateCookies() {
    const result = await API.auth.validate();
    
    if (result.success) {
        showToast('凭证验证通过', 'success');
    } else {
        showToast(result.message || '凭证无效', 'error');
    }
}

// ==================== 课程搜索 ====================
// 院系列表缓存
let departmentsCache = null;

async function loadDepartments() {
    // 如果已缓存则直接使用
    if (departmentsCache) {
        renderDepartments(departmentsCache);
        return;
    }
    
    const result = await API.courses.getDepartments();
    if (result.success && result.data) {
        departmentsCache = result.data;
        renderDepartments(result.data);
    }
}

function renderDepartments(departments) {
    const select = document.getElementById('search-college');
    if (!select) return;
    
    // 保留第一个"全部院系"选项
    select.innerHTML = '<option value="">全部院系</option>';
    
    departments.forEach(dept => {
        const option = document.createElement('option');
        option.value = dept.code;
        option.textContent = dept.name;
        select.appendChild(option);
    });
}

function onCollegeChange() {
    // 如果有搜索关键词，自动触发搜索
    const keyword = document.getElementById('search-keyword').value.trim();
    if (keyword) {
        searchCourses();
    }
}

async function searchCourses() {
    const keyword = document.getElementById('search-keyword').value.trim();
    if (!keyword) {
        showToast('请输入搜索关键词', 'error');
        return;
    }
    
    const college = document.getElementById('search-college')?.value || '';
    
    const tbody = document.getElementById('search-results');
    tbody.innerHTML = '<tr><td colspan="7" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    const result = await API.courses.search(keyword, college);
    
    if (!result.success) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">
            <i class="fas fa-exclamation-circle"></i>
            <h3>搜索失败</h3>
            <p>${result.message}</p>
        </td></tr>`;
        return;
    }
    
    const courses = result.data.courses || [];
    state.searchResults = courses;
    
    document.getElementById('search-count').textContent = `(共 ${result.data.total} 条)`;
    
    if (courses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">
            <i class="fas fa-search"></i>
            <h3>未找到相关课程</h3>
            <p>尝试其他关键词</p>
        </td></tr>`;
        return;
    }
    
    tbody.innerHTML = courses.map((course, index) => {
        const capacity = course.KXRS || 0;
        const current = course.DQRS || 0;
        const fillPercent = capacity > 0 ? (current / capacity * 100) : 0;
        const fillClass = fillPercent >= 90 ? 'danger' : fillPercent >= 70 ? 'warning' : '';
        
        // 冲突状态
        let conflictTag = '';
        if (course.IS_CONFLICT === 1) {
            conflictTag = '<span class="tag tag-danger"><i class="fas fa-exclamation-triangle"></i> 与已选冲突</span>';
        } else if (course.IS_QUEUE_CONFLICT === 1) {
            conflictTag = '<span class="tag tag-warning"><i class="fas fa-exclamation-circle"></i> 与队列冲突</span>';
        }
        
        // 课程详情标签
        const detailTags = [
            course.KCXF ? `<span class="course-tag credit">${course.KCXF}学分</span>` : '',
            course.KCCCMC ? `<span class="course-tag level">${course.KCCCMC}</span>` : '',
            course.XQMC ? `<span class="course-tag campus">${course.XQMC}</span>` : '',
        ].filter(t => t).join('');
        
        // 授课信息标签
        const teachingTags = [
            course.SKFSMC ? `<span class="course-tag-sm">${course.SKFSMC}</span>` : '',
            course.SKYYMC ? `<span class="course-tag-sm">${course.SKYYMC}</span>` : '',
            course.KSLXMC ? `<span class="course-tag-sm">${course.KSLXMC}</span>` : '',
        ].filter(t => t).join('');
        
        return `
            <tr data-index="${index}">
                <td><input type="checkbox" class="course-checkbox" data-bjdm="${course.BJDM}"></td>
                <td>
                    <div class="course-info-cell">
                        <div class="course-name">${course.KCMC || ''}</div>
                        <div class="course-code">${course.KCDM || ''} | ${course.BJMC || ''}</div>
                        <div class="course-tags">${detailTags}</div>
                    </div>
                </td>
                <td>
                    <div class="teacher-info">
                        <div class="teacher-name">${course.RKJS || ''}</div>
                        <div class="college-name">${course.KCKKDWMC || ''}</div>
                    </div>
                </td>
                <td class="course-time">
                    <div>${course.PKSJ || ''}</div>
                    <div class="course-location">${course.PKDD || ''}</div>
                    <div class="teaching-tags">${teachingTags}</div>
                </td>
                <td>
                    <div class="course-capacity">
                        <span>${current}/${capacity}</span>
                        <div class="capacity-bar">
                            <div class="capacity-fill ${fillClass}" style="width: ${fillPercent}%"></div>
                        </div>
                    </div>
                </td>
                <td>${conflictTag}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="addToQueue(${index})">
                        <i class="fas fa-plus"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}


function toggleSelectAllCourses() {
    const selectAll = document.getElementById('select-all-courses').checked;
    document.querySelectorAll('.course-checkbox').forEach(cb => {
        cb.checked = selectAll;
    });
}

async function addToQueue(index) {
    const course = state.searchResults[index];
    if (!course) return;
    
    const task = {
        bjdm: course.BJDM,
        kcdm: course.KCDM,
        kcmc: course.KCMC,
        bjmc: course.BJMC,
        rkjs: course.RKJS,
        pksj: course.PKSJ,
        pkdd: course.PKDD,
        xnxqmc: course.XNXQMC,
        kxrs: course.KXRS,
        dqrs: course.DQRS,
    };
    
    const result = await API.queue.add(task);
    
    if (result.success) {
        showToast(`已添加: ${course.KCMC}`, 'success');
        // 刷新迷你课表
        loadMiniSchedule();
    } else {
        showToast(result.message || '添加失败', 'error');
    }
}

async function addSelectedToQueue() {
    const checkboxes = document.querySelectorAll('.course-checkbox:checked');
    if (checkboxes.length === 0) {
        showToast('请先选择课程', 'error');
        return;
    }
    
    const tasks = [];
    checkboxes.forEach(cb => {
        const bjdm = cb.dataset.bjdm;
        const course = state.searchResults.find(c => c.BJDM === bjdm);
        if (course) {
            tasks.push({
                bjdm: course.BJDM,
                kcdm: course.KCDM,
                kcmc: course.KCMC,
                bjmc: course.BJMC,
                rkjs: course.RKJS,
                pksj: course.PKSJ,
                pkdd: course.PKDD,
                xnxqmc: course.XNXQMC,
                kxrs: course.KXRS,
                dqrs: course.DQRS,
            });
        }
    });
    
    const result = await API.queue.batchAdd(tasks);
    
    if (result.success) {
        showToast(`已添加 ${result.data.added.length} 门课程`, 'success');
        // 刷新迷你课表
        loadMiniSchedule();
    } else {
        showToast(result.message || '添加失败', 'error');
    }
}

// ==================== 抢课队列 ====================
async function loadQueue() {
    const result = await API.queue.getList();
    const tbody = document.getElementById('queue-list');
    
    if (!result.success) {
        showToast(result.message || '加载失败', 'error');
        return;
    }
    
    const tasks = result.data || [];
    state.queueTasks = tasks;
    
    // 分离待抢任务和历史记录
    const activeTasks = tasks.filter(t => t.status === 'pending' || t.status === 'grabbing');
    const historyTasks = tasks.filter(t => t.status === 'success' || t.status === 'failed' || t.status === 'cancelled');
    
    document.getElementById('queue-count').textContent = `(${activeTasks.length} 个待抢)`;
    
    // 渲染待抢任务
    renderActiveQueue(activeTasks);
    
    // 渲染历史记录
    renderHistoryQueue(historyTasks);
}

function renderActiveQueue(tasks) {
    const tbody = document.getElementById('queue-list');
    
    if (tasks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">
            <i class="fas fa-inbox"></i>
            <h3>队列为空</h3>
            <p>前往课程搜索添加课程</p>
        </td></tr>`;
        return;
    }
    
    tbody.innerHTML = tasks.map(task => {
        const statusTag = getStatusTag(task.status, task.error_msg);
        const conflictWarning = task.is_queue_conflict ? 
            '<span class="tag tag-warning" style="margin-left: 8px;" title="与其他课程时间冲突"><i class="fas fa-exclamation-circle"></i></span>' : '';
        
        // 容量信息
        const capacityInfo = task.kxrs ? `<div style="font-size: 11px; color: var(--text-muted);">${task.dqrs || 0}/${task.kxrs} 人</div>` : '';
        
        return `
            <tr class="queue-task-row" data-status="${task.status}">
                <td>
                    <div class="course-name">${task.kcmc}${conflictWarning}</div>
                    <div class="course-class">${task.kcdm}</div>
                    ${capacityInfo}
                </td>
                <td>${task.bjmc || ''}</td>
                <td class="course-teacher">${task.rkjs || ''}</td>
                <td class="course-time">${task.pksj || ''}</td>
                <td>
                    <div class="task-status-container">
                        ${statusTag}
                        ${task.error_msg ? `<div class="error-msg" title="${task.error_msg}" style="font-size: 11px; color: var(--danger); margin-top: 4px; word-break: break-all;">${task.error_msg}</div>` : ''}
                    </div>
                </td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="removeFromQueue('${task.bjdm}')" 
                            ${task.status === 'grabbing' ? 'disabled' : ''}>
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderHistoryQueue(tasks) {
    const tbody = document.getElementById('history-list');
    
    if (!tbody) return;
    
    if (tasks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 30px; color: var(--text-muted);">
            暂无历史记录
        </td></tr>`;
        return;
    }
    
    // 按更新时间倒序
    tasks.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    
    tbody.innerHTML = tasks.map(task => {
        const statusTag = getStatusTag(task.status);
        
        return `
            <tr class="queue-task-row history-row" data-status="${task.status}">
                <td>
                    <div class="course-name">${task.kcmc}</div>
                    <div class="course-class">${task.kcdm}</div>
                </td>
                <td>${task.bjmc || ''}</td>
                <td class="course-teacher">${task.rkjs || ''}</td>
                <td class="course-time">${task.pksj || ''}</td>
                <td>
                    <div class="task-status-container">
                        ${statusTag}
                        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                            ${task.error_msg || ''}
                            <span style="margin-left: 8px;">${new Date(task.updated_at).toLocaleTimeString()}</span>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

async function clearHistory() {
    const historyTasks = state.queueTasks.filter(t => t.status === 'success' || t.status === 'failed' || t.status === 'cancelled');
    if (historyTasks.length === 0) {
        showToast('没有可清除的历史记录', 'info');
        return;
    }
    
    showConfirmModal('清除历史', `确定要清除 ${historyTasks.length} 条历史记录吗？`, async () => {
        // 逐个删除（临时方案，理想情况应有批量删除接口）
        let successCount = 0;
        for (const task of historyTasks) {
            const result = await API.queue.remove(task.bjdm);
            if (result.success) successCount++;
        }
        
        showToast(`已清除 ${successCount} 条记录`, 'success');
        loadQueue();
    });
}

function getStatusTag(status, errorMsg = '') {
    const tags = {
        pending: '<span class="tag tag-pending"><i class="fas fa-clock"></i> 等待中</span>',
        grabbing: '<span class="tag tag-info"><i class="fas fa-spinner fa-spin"></i> 抢课中</span>',
        success: '<span class="tag tag-success"><i class="fas fa-check"></i> 已选中</span>',
        failed: '<span class="tag tag-danger"><i class="fas fa-times"></i> 失败</span>',
        cancelled: '<span class="tag tag-pending"><i class="fas fa-ban"></i> 已取消</span>',
    };
    return tags[status] || `<span class="tag">${status}</span>`;
}

async function removeFromQueue(bjdm) {
    const result = await API.queue.remove(bjdm);
    
    if (result.success) {
        showToast('已移除', 'success');
        await loadQueue();
        // 刷新迷你课表
        loadMiniSchedule();
    } else {
        showToast(result.message || '移除失败', 'error');
    }
}

async function clearQueue() {
    const activeTasks = state.queueTasks.filter(t => t.status === 'pending' || t.status === 'grabbing');
    
    if (activeTasks.length === 0) {
        showToast('队列中没有待抢任务', 'info');
        return;
    }

    showConfirmModal('确定要清空队列吗？', `确定要移除所有 ${activeTasks.length} 个待抢课程吗？`, async () => {
        // 如果后端提供了批量删除或清空指定状态的接口最好，这里先用循环删除
        let successCount = 0;
        for (const task of activeTasks) {
            const result = await API.queue.remove(task.bjdm);
            if (result.success) successCount++;
        }
        
        showToast(`已移除 ${successCount} 个待抢任务`, 'success');
        await loadQueue();
        loadMiniSchedule();
    });
}

// 队列自动刷新定时器
let queueRefreshTimer = null;

function startQueueAutoRefresh() {
    // 先停止已有的定时器
    stopQueueAutoRefresh();
    
    // 每3秒刷新一次队列状态
    queueRefreshTimer = setInterval(async () => {
        if (state.currentPage === 'queue') {
            await loadQueue();
        }
    }, 3000);
}

function stopQueueAutoRefresh() {
    if (queueRefreshTimer) {
        clearInterval(queueRefreshTimer);
        queueRefreshTimer = null;
    }
}

// ==================== 抢课控制 ====================
async function startAllGrabbing() {
    const result = await API.grabber.start();
    
    if (result.success) {
        showToast(result.message, 'success');
        state.isGrabbing = true;
        showGrabberPanel();
        updateGrabberStatus();
        
        // 连接 WebSocket
        grabberWS.onStatusUpdate = updateGrabberUI;
        grabberWS.onGrabSuccess = async (data) => {
            showToast(`🎉 抢课成功: ${data.kcmc}`, 'success');
            await loadQueue();
            // 刷新课程信息和课表
            await syncSelectedCourses();
        };
        grabberWS.connect();
        
        if (state.currentPage === 'queue') {
            loadQueue();
        }
    } else {
        showToast(result.message || '启动失败', 'error');
    }
}

async function stopAllGrabbing() {
    const result = await API.grabber.stop();
    
    if (result.success) {
        showToast(result.message, 'success');
        state.isGrabbing = false;
        updateGrabberStatus();
        grabberWS.disconnect();
        
        if (state.currentPage === 'queue') {
            loadQueue();
        }
    } else {
        showToast(result.message || '停止失败', 'error');
    }
}

async function updateGrabberStatus() {
    const result = await API.grabber.getStatus();
    
    if (result.success) {
        updateGrabberUI(result.data);
    }
}

function updateGrabberUI(data) {
    state.isGrabbing = data.is_running;
    
    const pulse = document.getElementById('grabber-pulse');
    const statusText = document.getElementById('grabber-status-text');
    
    if (data.is_running) {
        pulse.classList.add('running');
        statusText.textContent = '抢课中';
    } else {
        pulse.classList.remove('running');
        statusText.textContent = '已停止';
    }
    
    document.getElementById('grabber-active').textContent = data.active_tasks || 0;
    document.getElementById('grabber-success').textContent = data.success_count || 0;
    document.getElementById('grabber-failed').textContent = data.failed_count || 0;
    
    // 检测任务是否全部完成（正在运行但没有活动任务）
    if (data.is_running && data.active_tasks === 0) {
        // 自动停止抢课
        stopAllGrabbing().then(() => {
            showToast('所有任务已完成，抢课已自动停止', 'success');
            // 3秒后隐藏面板
            setTimeout(() => {
                hideGrabberPanel();
            }, 3000);
        });
    }
    
    // 更新任务列表
    const tasksEl = document.getElementById('grabber-tasks');
    const currentTasks = data.current_tasks || [];
    
    if (currentTasks.length > 0) {
        tasksEl.innerHTML = currentTasks.map(bjdm => {
            const task = state.queueTasks.find(t => t.bjdm === bjdm);
            const name = task ? task.kcmc : bjdm.substring(0, 8) + '...';
            return `
                <div class="grabber-task">
                    <span>${name}</span>
                    <div class="spinner"></div>
                </div>
            `;
        }).join('');
    } else {
        tasksEl.innerHTML = '<div style="text-align: center; color: var(--text-muted);">无进行中的任务</div>';
    }
}

function showGrabberPanel() {
    document.getElementById('grabber-panel').style.display = 'block';
}

function hideGrabberPanel() {
    document.getElementById('grabber-panel').style.display = 'none';
}

function toggleGrabberPanel() {
    const panel = document.getElementById('grabber-panel');
    const body = panel.querySelector('.grabber-body');
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
}

// ==================== 课表 ====================
// 标记是否已在本次会话中同步过课程
let hasLoadedCoursesThisSession = false;

async function loadSchedule() {
    const showQueueCheckbox = document.getElementById('show-queue-courses');
    const includeQueue = showQueueCheckbox ? showQueueCheckbox.checked : true;
    
    // 页面首次加载时同步已选课程
    if (!hasLoadedCoursesThisSession) {
        hasLoadedCoursesThisSession = true;
        try {
            // 同步课程
            await API.courses.getSelected();
        } catch (e) {
            console.log('同步课程失败:', e);
        }
    }
    
    const result = await API.schedule.get(null, includeQueue);
    
    if (!result.success) {
        showToast(result.message || '加载失败', 'error');
        return;
    }
    
    state.scheduleData = result.data;
    
    // 渲染学期标签
    const semesterTabs = document.getElementById('semester-tabs');
    const semesters = result.data.semesters || [];
    
    // 如果没有指定当前学期，使用返回的默认值
    if (!state.currentSemester || !semesters.includes(state.currentSemester)) {
        state.currentSemester = result.data.current_semester || semesters[0];
    }
    
    if (semesters.length === 0) {
        semesterTabs.innerHTML = '<div style="color: var(--text-muted);">暂无课程数据，请先同步已选课程</div>';
        document.getElementById('schedule-table').innerHTML = '';
        return;
    }
    
    semesterTabs.innerHTML = semesters.map(sem => `
        <div class="semester-tab ${sem === state.currentSemester ? 'active' : ''}" 
             onclick="switchSemester('${sem}')">
            ${sem}
        </div>
    `).join('');
    
    // 渲染课表
    renderScheduleTable();
    
    // 加载课程列表
    loadCourseList();
}

async function loadCourseList() {
    const tbody = document.getElementById('course-list');
    const statsEl = document.getElementById('course-stats');
    if (!tbody) return;
    
    const result = await API.courses.getList();
    
    if (!result.success || !result.data || result.data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-state">
            <i class="fas fa-inbox"></i>
            <h3>暂无课程</h3>
            <p>请先同步已选课程</p>
        </td></tr>`;
        if (statsEl) statsEl.innerHTML = '';
        return;
    }
    
    const courses = result.data;
    
    // 统计课程数量和学分（只统计正式选中和已中签的）
    const validStatuses = ['confirmed', 'won'];
    const validCourses = courses.filter(c => validStatuses.includes(c.status));
    const totalCount = validCourses.length;
    const totalCredits = validCourses.reduce((sum, c) => sum + (parseFloat(c.xf) || 0), 0);
    
    if (statsEl) {
        statsEl.innerHTML = `
            <span class="stat-item">
                <i class="fas fa-book"></i>
                有效课程: <strong>${totalCount}</strong> 门
            </span>
            <span class="stat-item">
                <i class="fas fa-star"></i>
                总学分: <strong>${totalCredits.toFixed(1)}</strong> 分
            </span>
        `;
    }
    
    // 显示预选课程开关
    const showPendingCheckbox = document.getElementById('show-pending-courses');
    const showPending = showPendingCheckbox ? showPendingCheckbox.checked : true;
    
    // 过滤课程（未中签的始终显示在列表中）
    const displayCourses = courses;
    
    tbody.innerHTML = displayCourses.map(c => {
        // 状态标签
        let statusTag = '';
        switch (c.status) {
            case 'confirmed':
                statusTag = '<span class="course-status-tag confirmed">正式选中</span>';
                break;
            case 'won':
                statusTag = '<span class="course-status-tag won">已中签</span>';
                break;
            case 'pending':
                statusTag = '<span class="course-status-tag pending">待抽签</span>';
                break;
            case 'failed':
                statusTag = '<span class="course-status-tag failed">未中签</span>';
                break;
            default:
                statusTag = `<span class="course-status-tag unknown">${c.status_text}</span>`;
        }
        
        // 退课按钮
        let actionBtn = '';
        if (c.can_cancel) {
            actionBtn = `<button class="btn btn-sm btn-danger" onclick="confirmCancelCourse('${c.bjdm}', '${c.kcmc}')">
                <i class="fas fa-times"></i> 退课
            </button>`;
        } else {
            actionBtn = '<span style="color: var(--text-muted); font-size: 12px;">不可退</span>';
        }
        
        return `
            <tr class="course-row-${c.status}">
                <td>
                    <div class="course-name">${c.kcmc || ''}</div>
                    <div class="course-code">${c.kcdm || ''}</div>
                </td>
                <td>${c.bjmc || ''}</td>
                <td>${c.rkjs || ''}</td>
                <td class="course-time">${c.pksj || ''}</td>
                <td>${c.xf || ''}</td>
                <td>${statusTag}</td>
                <td>${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

// 退课二次确认
function confirmCancelCourse(bjdm, kcmc) {
    showConfirmModal(
        '确认退课',
        `确定要退选课程 <strong>${kcmc}</strong> 吗？<br><br><span style="color: var(--danger);">⚠️ 此操作不可撤销，请谨慎操作！</span>`,
        () => {
            // 第二次确认
            showConfirmModal(
                '再次确认',
                `<span style="color: var(--danger); font-weight: bold;">请再次确认：确定要退选 ${kcmc} 吗？</span>`,
                () => {
                    doCancelCourse(bjdm, kcmc);
                }
            );
        }
    );
}

async function doCancelCourse(bjdm, kcmc) {
    const result = await API.courses.cancel(bjdm);
    
    if (result.success) {
        showToast(`已成功退选 ${kcmc}`, 'success');
        // 刷新课表和课程列表
        loadSchedule();
    } else {
        if (result.data?.token_expired) {
            showToast('页面已过期，正在刷新Token...', 'warning');
            await API.auth.refreshToken();
            // 重试
            const retryResult = await API.courses.cancel(bjdm);
            if (retryResult.success) {
                showToast(`已成功退选 ${kcmc}`, 'success');
                loadSchedule();
            } else {
                showToast(retryResult.message || '退课失败', 'error');
            }
        } else {
            showToast(result.message || '退课失败', 'error');
        }
    }
}


function switchSemester(semester) {
    state.currentSemester = semester;
    
    // 更新标签状态
    document.querySelectorAll('.semester-tab').forEach(tab => {
        tab.classList.toggle('active', tab.textContent.trim() === semester);
    });
    
    renderScheduleTable();
}

function renderScheduleTable() {
    const scheduleData = state.scheduleData;
    if (!scheduleData || !state.currentSemester) return;
    
    const semesterData = scheduleData.schedules[state.currentSemester];
    if (!semesterData) return;
    
    // 使用大节数据
    const bigGrid = semesterData.big_grid;
    const bigSections = semesterData.big_sections || [];
    const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    
    const table = document.getElementById('schedule-table');
    
    // 表头
    let html = `
        <thead>
            <tr>
                <th>节次</th>
                ${weekdays.map(day => `<th>${day}</th>`).join('')}
            </tr>
        </thead>
        <tbody>
    `;
    
    // 表体 - 每大节一行
    for (const bigSec of bigSections) {
        html += `<tr>
            <td>
                <div class="section-header">${bigSec.name}</div>
                <div class="section-time">${bigSec.time}</div>
            </td>`;
        
        for (let weekday = 1; weekday <= 7; weekday++) {
            const cellCourses = (bigGrid && bigGrid[weekday]) ? (bigGrid[weekday][bigSec.id] || []) : [];
            
            html += '<td class="schedule-cell">';
            
            cellCourses.forEach(course => {
                const isQueue = course.source === 'queue';
                const hasConflict = course.has_conflict === true;
                const weeksStr = formatWeeks(course.weeks);
                
                // 构建样式类
                let courseClass = 'schedule-course';
                if (isQueue) courseClass += ' queue';
                if (hasConflict) courseClass += ' conflict';
                
                // 删除按钮（仅队列课程显示）
                const deleteBtn = isQueue ? 
                    `<button class="course-delete-btn" onclick="event.stopPropagation(); removeFromQueueAndRefresh('${course.bjdm}')" title="从队列移除">×</button>` : '';
                
                html += `
                    <div class="${courseClass}" 
                         data-bjdm="${course.bjdm}"
                         title="${course.kcmc}\n${course.rkjs || ''}\n${course.pkdd || ''}\n${weeksStr}${hasConflict ? '\n⚠ 时间冲突' : ''}">
                        ${deleteBtn}
                        <div class="course-name">${course.kcmc}</div>
                        <div class="course-location">${course.pkdd || ''}</div>
                        <div class="course-weeks">${weeksStr}</div>
                        ${hasConflict ? '<div class="conflict-badge">冲突</div>' : ''}
                    </div>
                `;
            });
            
            html += '</td>';
        }
        
        html += '</tr>';
    }
    
    html += '</tbody>';
    table.innerHTML = html;
}

// 从队列移除并刷新课表
async function removeFromQueueAndRefresh(bjdm) {
    const result = await API.queue.remove(bjdm);
    
    if (result.success) {
        showToast('已从队列移除', 'success');
        // 刷新课表
        await loadSchedule();
        // 如果当前在队列页，也刷新
        if (state.currentPage === 'queue') {
            await loadQueue();
        }
    } else {
        showToast(result.message || '移除失败', 'error');
    }
}

function formatWeeks(weeks) {
    if (!weeks || weeks.length === 0) return '';
    
    if (weeks.length === 1) return `第${weeks[0]}周`;
    
    const sorted = [...weeks].sort((a, b) => a - b);
    
    // 智能合并连续周次
    const ranges = [];
    let rangeStart = sorted[0];
    let rangeEnd = sorted[0];
    
    for (let i = 1; i < sorted.length; i++) {
        if (sorted[i] === rangeEnd + 1) {
            // 连续，扩展当前范围
            rangeEnd = sorted[i];
        } else {
            // 不连续，保存当前范围并开始新范围
            if (rangeStart === rangeEnd) {
                ranges.push(`${rangeStart}`);
            } else {
                ranges.push(`${rangeStart}-${rangeEnd}`);
            }
            rangeStart = sorted[i];
            rangeEnd = sorted[i];
        }
    }
    
    // 保存最后一个范围
    if (rangeStart === rangeEnd) {
        ranges.push(`${rangeStart}`);
    } else {
        ranges.push(`${rangeStart}-${rangeEnd}`);
    }
    
    return ranges.join(',') + '周';
}

// ==================== 同步已选课程 ====================
async function syncSelectedCourses() {
    const result = await API.courses.getSelected();
    
    if (result.success) {
        showToast(result.message, 'success');
        loadDashboard();
        loadSchedule();
        loadMiniSchedule(); // 联动刷新迷你课表
    } else {
        showToast(result.message || '同步失败', 'error');
    }
}

// ==================== 设置 ====================
async function loadSettings() {
    const result = await API.settings.getNotification();
    
    if (!result.success) return;
    
    const config = result.data;
    
    document.getElementById('email-enabled').checked = config.email_enabled;
    document.getElementById('email-smtp-host').value = config.email_smtp_host || '';
    document.getElementById('email-smtp-port').value = config.email_smtp_port || 465;
    document.getElementById('email-username').value = config.email_username || '';
    document.getElementById('email-to').value = config.email_to || '';
    
    document.getElementById('wecom-enabled').checked = config.wecom_enabled;
    document.getElementById('wecom-webhook').value = config.wecom_webhook || '';
}

async function saveNotificationConfig() {
    const config = {
        email_enabled: document.getElementById('email-enabled').checked,
        email_smtp_host: document.getElementById('email-smtp-host').value,
        email_smtp_port: parseInt(document.getElementById('email-smtp-port').value) || 465,
        email_username: document.getElementById('email-username').value,
        email_password: document.getElementById('email-password').value,
        email_to: document.getElementById('email-to').value,
        wecom_enabled: document.getElementById('wecom-enabled').checked,
        wecom_webhook: document.getElementById('wecom-webhook').value,
    };
    
    const result = await API.settings.updateNotification(config);
    
    if (result.success) {
        showToast('设置已保存', 'success');
    } else {
        showToast(result.message || '保存失败', 'error');
    }
}

async function testNotification() {
    const result = await API.settings.testNotification();
    
    if (result.success) {
        const data = result.data;
        let msg = '测试完成: ';
        if (data.email) msg += '邮件✓ ';
        if (data.wecom) msg += '企微✓';
        if (!data.email && !data.wecom) msg += '未发送任何通知';
        showToast(msg, data.email || data.wecom ? 'success' : 'error');
    } else {
        showToast(result.message || '测试失败', 'error');
    }
}

// ==================== 代理控制 ====================
async function startProxy() {
    const port = parseInt(document.getElementById('proxy-port').value) || 8888;
    
    showToast('正在启动代理...', 'info');
    const result = await API.proxy.start(port);
    
    if (result.success) {
        showToast(`代理已启动在端口 ${port}`, 'success');
        updateProxyUI(true, port);
    } else {
        showToast(result.message || '启动失败', 'error');
    }
}

async function stopProxy() {
    const result = await API.proxy.stop();
    
    if (result.success) {
        showToast('代理已停止', 'success');
        updateProxyUI(false);
    } else {
        showToast(result.message || '停止失败', 'error');
    }
}

async function checkProxyStatus() {
    const result = await API.proxy.getStatus();
    
    if (result.success) {
        const status = result.data;
        updateProxyUI(status.is_running, status.port);
        
        // 更新日志
        if (status.recent_logs && status.recent_logs.length > 0) {
            document.getElementById('proxy-logs').style.display = 'block';
            document.getElementById('proxy-log-content').textContent = status.recent_logs.join('\n');
        }
    }
}

function updateProxyUI(isRunning, port = null) {
    const startBtn = document.getElementById('btn-start-proxy');
    const stopBtn = document.getElementById('btn-stop-proxy');
    const statusBadge = document.getElementById('proxy-status-badge');
    
    if (isRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusBadge.innerHTML = `<span class="tag tag-success">运行中 :${port || 8888}</span>`;
        document.getElementById('proxy-logs').style.display = 'block';
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusBadge.innerHTML = '<span class="tag tag-pending">未运行</span>';
    }
}

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    // 绑定导航点击事件
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
            closeSidebar();
        });
    });
    
    // 搜索框回车事件
    document.getElementById('search-keyword').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchCourses();
        }
    });
    
    // 显示待抢课程复选框事件
    const showQueueCheckbox = document.getElementById('show-queue-courses');
    if (showQueueCheckbox) {
        showQueueCheckbox.addEventListener('change', () => {
            loadSchedule();
        });
    }
    
    // 恢复主题设置
    initTheme();
    
    // 加载仪表盘
    loadDashboard();
    
    // 检查抢课状态
    updateGrabberStatus().then(() => {
        if (state.isGrabbing) {
            showGrabberPanel();
            grabberWS.onStatusUpdate = updateGrabberUI;
            grabberWS.connect();
        }
    });
});

// ==================== 主题切换 ====================
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }
}

// ==================== 迷你课表 ====================
let miniScheduleData = null;
let miniCurrentSemester = null;

function toggleMiniSchedule() {
    const panel = document.getElementById('mini-schedule-panel');
    panel.classList.toggle('collapsed');
    
    // 首次展开时加载数据
    if (!panel.classList.contains('collapsed') && !miniScheduleData) {
        loadMiniSchedule();
    }
}

async function loadMiniSchedule() {
    const result = await API.schedule.get(null, true);
    
    if (!result.success) {
        return;
    }
    
    miniScheduleData = result.data;
    const semesters = result.data.semesters || [];
    
    if (!miniCurrentSemester || !semesters.includes(miniCurrentSemester)) {
        miniCurrentSemester = result.data.current_semester || semesters[0];
    }
    
    // 渲染学期标签
    const tabsContainer = document.getElementById('mini-semester-tabs');
    if (semesters.length > 0) {
        tabsContainer.innerHTML = semesters.map(sem => `
            <div class="mini-semester-tab ${sem === miniCurrentSemester ? 'active' : ''}" 
                 onclick="switchMiniSemester('${sem}')">
                ${sem.split(' ')[1] || sem}
            </div>
        `).join('');
    }
    
    renderMiniSchedule();
}

function switchMiniSemester(semester) {
    miniCurrentSemester = semester;
    
    // 更新标签状态
    document.querySelectorAll('.mini-semester-tab').forEach(tab => {
        tab.classList.toggle('active', tab.textContent.trim() === semester.split(' ')[1]);
    });
    
    renderMiniSchedule();
}

function renderMiniSchedule() {
    if (!miniScheduleData || !miniCurrentSemester) return;
    
    const semesterData = miniScheduleData.schedules[miniCurrentSemester];
    if (!semesterData) return;
    
    const bigGrid = semesterData.big_grid;
    const bigSections = semesterData.big_sections || [];
    const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
    
    const gridContainer = document.getElementById('mini-schedule-grid');
    
    let html = `<table>
        <thead>
            <tr>
                <th style="width: 45px;">节次</th>
                ${weekdays.map(d => `<th>${d}</th>`).join('')}
            </tr>
        </thead>
        <tbody>
    `;
    
    for (const bigSec of bigSections) {
        html += `<tr>
            <td style="font-size: 10px;">${bigSec.name.replace('第', '')}</td>`;
        
        for (let weekday = 1; weekday <= 7; weekday++) {
            const cellCourses = (bigGrid && bigGrid[weekday]) ? (bigGrid[weekday][bigSec.id] || []) : [];
            
            html += '<td>';
            cellCourses.forEach(course => {
                const isQueue = course.source === 'queue';
                const hasConflict = course.has_conflict === true;
                
                let courseClass = 'mini-course';
                if (isQueue) courseClass += ' queue';
                if (hasConflict) courseClass += ' conflict';
                
                // 队列课程添加删除按钮
                const deleteBtn = isQueue ? 
                    `<span class="mini-delete" onclick="event.stopPropagation(); removeMiniCourse('${course.bjdm}')" title="移除">×</span>` : '';
                
                html += `
                    <div class="${courseClass}" title="${course.kcmc}\n${course.pkdd || ''}">
                        ${deleteBtn}
                        <div class="mini-course-name">${course.kcmc}</div>
                    </div>
                `;
            });
            html += '</td>';
        }
        
        html += '</tr>';
    }
    
    html += '</tbody></table>';
    gridContainer.innerHTML = html;
}

// 从迷你课表移除课程
async function removeMiniCourse(bjdm) {
    const result = await API.queue.remove(bjdm);
    if (result.success) {
        showToast('已移除', 'success');
        loadMiniSchedule();
    } else {
        showToast(result.message || '移除失败', 'error');
    }
}

// 导出课表为图片 - source: 'main' 或 'mini'
async function exportScheduleAsImage(source = 'main') {
    // 检查html2canvas是否加载
    if (typeof html2canvas === 'undefined') {
        // 动态加载html2canvas
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
        script.onload = () => doExportScheduleImage(source);
        document.head.appendChild(script);
        showToast('正在加载导出组件...', 'info');
    } else {
        doExportScheduleImage(source);
    }
}

async function doExportScheduleImage(source = 'main') {
    // 根据来源决定使用哪个学期和表格
    let semester, table;
    
    if (source === 'mini') {
        semester = miniCurrentSemester;
        table = document.querySelector('#mini-schedule-grid table');
    } else {
        semester = state.currentSemester;
        table = document.getElementById('schedule-table');
    }
    
    if (!table || !table.innerHTML.trim()) {
        showToast('请先加载课表', 'warning');
        return;
    }
    
    showToast('正在生成图片...', 'info');
    
    try {
        const canvas = await html2canvas(table, {
            backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--bg-card').trim(),
            scale: 2,
        });
        
        const link = document.createElement('a');
        link.download = `课表_${semester || '导出'}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        
        showToast('课表导出成功！', 'success');
    } catch (e) {
        showToast('导出失败: ' + e.message, 'error');
    }
}

// 页面加载时初始化迷你课表为折叠状态，并加载数据
setTimeout(() => {
    const panel = document.getElementById('mini-schedule-panel');
    if (panel) {
        panel.classList.add('collapsed');
        loadMiniSchedule();
    }
}, 1000);

