/**
 * API 调用模块
 * 封装与后端的所有 HTTP 交互
 */

const API_BASE = '/api';

/**
 * 通用请求函数
 */
async function request(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    const finalOptions = { ...defaultOptions, ...options };
    
    if (finalOptions.body && typeof finalOptions.body === 'object') {
        finalOptions.body = JSON.stringify(finalOptions.body);
    }
    
    try {
        const response = await fetch(`${API_BASE}${url}`, finalOptions);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API Error:', error);
        return { success: false, message: error.message };
    }
}

/**
 * API 调用对象
 */
const API = {
    // ==================== 认证相关 ====================
    auth: {
        getStatus: (verify = true) => request(`/auth/status?verify=${verify}`),
        getSystemInfo: () => request('/auth/system-info'),
        updateCookies: (cookies) => request('/auth/cookies', {
            method: 'POST',
            body: cookies,
        }),
        refreshToken: () => request('/auth/refresh-token', { method: 'POST' }),
        validate: () => request('/auth/validate', { method: 'POST' }),
        clearCookies: () => request('/auth/cookies', { method: 'DELETE' }),
    },
    
    // ==================== 课程相关 ====================
    courses: {
        getDepartments: () => request('/courses/departments'),
        search: (keyword, college = '', pageIndex = 1, pageSize = 20) => {
            let url = `/courses/search?keyword=${encodeURIComponent(keyword)}&page_index=${pageIndex}&page_size=${pageSize}`;
            if (college) url += `&college=${encodeURIComponent(college)}`;
            return request(url);
        },
        getSelected: () => request('/courses/selected'),
        getLocalSelected: () => request('/courses/selected/local'),
        getList: () => request('/courses/list'),
        cancel: (bjdm) => request(`/courses/cancel?bjdm=${encodeURIComponent(bjdm)}`, { method: 'POST' }),
        checkConflict: (bjdm, pksj) => request('/courses/conflict/check', {
            method: 'POST',
            body: { bjdm, pksj },
        }),
    },
    
    // ==================== 抢课队列 ====================
    queue: {
        getList: (status = null) => {
            const url = status ? `/queue?status=${status}` : '/queue';
            return request(url);
        },
        add: (task) => request('/queue', {
            method: 'POST',
            body: task,
        }),
        batchAdd: (tasks) => request('/queue/batch', {
            method: 'POST',
            body: { tasks },
        }),
        remove: (bjdm) => request(`/queue/${bjdm}`, { method: 'DELETE' }),
        clear: (status = null) => {
            const url = status ? `/queue?status=${status}` : '/queue';
            return request(url, { method: 'DELETE' });
        },
        updatePriority: (bjdm, priority) => request(`/queue/${bjdm}/priority?priority=${priority}`, {
            method: 'PUT',
        }),
    },
    
    // ==================== 抢课控制 ====================
    grabber: {
        start: (taskIds = null) => request('/grabber/start', {
            method: 'POST',
            body: taskIds ? { task_ids: taskIds } : {},
        }),
        stop: (taskIds = null) => request('/grabber/stop', {
            method: 'POST',
            body: taskIds ? { task_ids: taskIds } : {},
        }),
        getStatus: () => request('/grabber/status'),
    },
    
    // ==================== 课表 ====================
    schedule: {
        get: (semester = null, includeQueue = true) => {
            let url = `/schedule?include_queue=${includeQueue}&_=${new Date().getTime()}`;
            if (semester) url += `&semester=${encodeURIComponent(semester)}`;
            return request(url);
        },
        getSemesters: () => request('/schedule/semesters'),
    },
    
    // ==================== 设置 ====================
    settings: {
        getNotification: () => request('/settings/notification'),
        updateNotification: (config) => request('/settings/notification', {
            method: 'PUT',
            body: config,
        }),
        testNotification: () => request('/settings/notification/test', { method: 'POST' }),
    },
    
    // ==================== 代理 ====================
    proxy: {
        start: (port = 8888) => request(`/proxy/start?port=${port}`, { method: 'POST' }),
        stop: () => request('/proxy/stop', { method: 'POST' }),
        getStatus: () => request('/proxy/status'),
    },
    
    // ==================== 健康检查 ====================
    health: () => request('/health'),
};

/**
 * WebSocket 连接管理
 */
class GrabberWebSocket {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.onStatusUpdate = null;
        this.onGrabSuccess = null;
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/grabber/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            if (message.type === 'status_update' && this.onStatusUpdate) {
                this.onStatusUpdate(message.data);
            }
            
            if (message.type === 'grab_success' && this.onGrabSuccess) {
                this.onGrabSuccess(message.data);
            }
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => {
                    this.reconnectAttempts++;
                    this.connect();
                }, 2000);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// 导出全局 WebSocket 实例
const grabberWS = new GrabberWebSocket();
