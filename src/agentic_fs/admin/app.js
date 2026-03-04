// ═══════════════════════════════════════════════════════════════════
// Agentic Filesystem — Admin UI Application
// ═══════════════════════════════════════════════════════════════════

// ═══════════ CONFIGURATION ═══════════
const API_BASE = new URLSearchParams(window.location.search).get('api') || window.location.origin;

// ═══════════ STATE ═══════════
const state = {
  activeTenant: null,
  currentPage: 'tenants',
  tenants: [],
  namespaces: [],
  treePath: { namespace: '', path: '' },
  searchMode: 'hybrid',
  selectedFileId: null,
  previewOpen: false,
  expandedNodes: new Set(),
};

const pageNames = {
  tenants: 'Tenants',
  explorer: 'File Explorer',
  search: 'Search & RAG',
  upload: 'Upload Files',
  'tenant-settings': 'Tenant Settings',
  'tenant-users': 'Users & API Keys',
  'sys-settings': 'System Settings',
  'sys-accounts': 'Accounts & Tenants',
};

// ═══════════ API CLIENT ═══════════
async function api(path, options = {}) {
  const url = API_BASE + path;
  try {
    const headers = options.headers !== undefined ? options.headers : { 'Content-Type': 'application/json' };
    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
      const error = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(error.detail || `API error ${resp.status}`);
    }
    if (options.raw) return resp;
    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) return resp.json();
    return resp;
  } catch (err) {
    if (err instanceof TypeError) {
      showApiError(API_BASE);
    }
    throw err;
  }
}

function showApiError(url) {
  const banner = document.getElementById('apiErrorBanner');
  const urlSpan = document.getElementById('apiErrorUrl');
  if (banner) { banner.style.display = 'block'; urlSpan.textContent = url; }
}

function hideApiError() {
  const banner = document.getElementById('apiErrorBanner');
  if (banner) banner.style.display = 'none';
}

// Tenant endpoints
async function fetchTenants() { return api('/admin/tenants'); }
async function fetchNamespaces(tenant) { return api(`/v1/${encodeURIComponent(tenant)}/namespaces`); }

// Directory endpoints
async function fetchDirectory(tenant, namespace, path) {
  const base = path ? `/v1/${encodeURIComponent(tenant)}/dirs/${path}` : `/v1/${encodeURIComponent(tenant)}/dirs`;
  return api(`${base}?namespace=${encodeURIComponent(namespace)}`);
}
async function createDirectoryApi(tenant, namespace, path) {
  return api(`/v1/${encodeURIComponent(tenant)}/dirs`, {
    method: 'POST',
    body: JSON.stringify({ namespace, path }),
  });
}

// File endpoints
async function fetchFileMeta(tenant, fileId) {
  return api(`/v1/${encodeURIComponent(tenant)}/files/${encodeURIComponent(fileId)}/meta`);
}
async function fetchBatch(tenant, fileIds, includeContent, maxTextChars) {
  const body = { file_ids: fileIds, include_content: includeContent };
  if (maxTextChars) body.max_text_chars = maxTextChars;
  return api(`/v1/${encodeURIComponent(tenant)}/files/batch`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}
async function deleteFileApi(tenant, fileId) {
  return api(`/v1/${encodeURIComponent(tenant)}/files/${encodeURIComponent(fileId)}`, { method: 'DELETE' });
}
async function uploadFileApi(tenant, file, namespace, path, tags) {
  const form = new FormData();
  form.append('file', file);
  form.append('namespace', namespace);
  if (path) form.append('path', path);
  if (tags) form.append('tags', tags);
  return api(`/v1/${encodeURIComponent(tenant)}/files`, { method: 'POST', body: form, headers: undefined });
}

// Search endpoints
async function searchSemantic(tenant, body) {
  return api(`/v1/${encodeURIComponent(tenant)}/search/semantic`, { method: 'POST', body: JSON.stringify(body) });
}
async function searchHybrid(tenant, body) {
  return api(`/v1/${encodeURIComponent(tenant)}/search/hybrid`, { method: 'POST', body: JSON.stringify(body) });
}
async function findSimilar(tenant, fileId, k) {
  return api(`/v1/${encodeURIComponent(tenant)}/search/similar/${encodeURIComponent(fileId)}?k=${k}`);
}
async function searchAsk(tenant, body) {
  return api(`/v1/${encodeURIComponent(tenant)}/search/ask`, { method: 'POST', body: JSON.stringify(body) });
}
async function fetchIndexingStatus(tenant, fileId) {
  return api(`/v1/${encodeURIComponent(tenant)}/search/status/${encodeURIComponent(fileId)}`);
}

// ═══════════ UTILITIES ═══════════
function escapeHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function formatBytes(bytes) {
  if (bytes == null) return '—';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
}

function formatDate(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function truncateId(id, len) {
  if (!id) return '—';
  len = len || 12;
  return id.length > len ? id.slice(0, len) + '...' : id;
}

function getFileIconClass(mimeType) {
  if (!mimeType) return 'file';
  if (mimeType === 'directory') return 'dir';
  if (mimeType === 'text/markdown') return 'md';
  if (mimeType === 'text/plain') return 'txt';
  if (mimeType === 'application/pdf') return 'pdf';
  if (mimeType === 'application/json') return 'json';
  if (mimeType.startsWith('image/')) return 'img';
  return 'file';
}

function getFileIconLabel(mimeType) {
  if (!mimeType) return 'FILE';
  if (mimeType === 'directory') return '';
  if (mimeType === 'text/markdown') return 'MD';
  if (mimeType === 'text/plain') return 'TXT';
  if (mimeType === 'application/pdf') return 'PDF';
  if (mimeType === 'application/json') return 'JSON';
  if (mimeType.startsWith('image/')) return 'IMG';
  return 'FILE';
}

function getStatusClass(status) {
  const map = { indexed: 'status-indexed', pending: 'status-pending', processing: 'status-processing', failed: 'status-failed' };
  return map[status] || 'status-pending';
}

const FOLDER_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>';
const FOLDER_SVG_SM = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>';
const FILE_SVG_SM = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>';

// ═══════════ THEME ═══════════
function initTheme() {
  const saved = localStorage.getItem('afs-theme');
  if (saved) document.documentElement.dataset.theme = saved;
}

function toggleTheme() {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('afs-theme', html.dataset.theme);
}

// ═══════════ NAVIGATION ═══════════
function toggleNavSection(id) {
  document.getElementById(id).classList.toggle('collapsed');
}

function showPage(pageId, navEl) {
  state.currentPage = pageId;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const page = document.getElementById('page-' + pageId);
  if (page) page.classList.add('active');
  if (navEl) {
    navEl.classList.add('active');
  } else {
    const el = document.querySelector('[data-page="' + pageId + '"]');
    if (el) el.classList.add('active');
  }
  updateBreadcrumb(pageId);
  closePreview();

  // Trigger page-specific data loads
  switch (pageId) {
    case 'tenants': loadTenantsPage(); break;
    case 'explorer': loadExplorerPage(); break;
    case 'search': loadSearchNamespaces(); break;
    case 'upload': loadUploadNamespaces(); break;
  }
}

function updateBreadcrumb(pageId) {
  const bc = document.getElementById('breadcrumb');
  if (pageId === 'explorer' && state.activeTenant) {
    bc.innerHTML = '<span class="crumb" onclick="showPage(\'tenants\')">Tenants</span><span class="sep">/</span><span class="crumb current">' + escapeHtml(state.activeTenant) + '</span>';
  } else {
    bc.innerHTML = '<span class="crumb current">' + escapeHtml(pageNames[pageId] || pageId) + '</span>';
  }
}

// ═══════════ TENANT SELECTOR ═══════════
function switchTenant(val) {
  if (!val) return;
  state.activeTenant = val;
  state.namespaces = [];
  state.treePath = { namespace: '', path: '' };
  state.selectedFileId = null;
  state.expandedNodes.clear();

  if (state.currentPage === 'explorer') loadExplorerPage();
  if (state.currentPage === 'search') loadSearchNamespaces();
  if (state.currentPage === 'upload') loadUploadNamespaces();
}

function selectTenant(name) {
  state.activeTenant = name;
  document.getElementById('sidebarTenantSelect').value = name;
  showPage('explorer');
}

function populateTenantSelector(tenants) {
  const select = document.getElementById('sidebarTenantSelect');
  select.innerHTML = '<option value="">— Select Tenant —</option>' +
    tenants.map(t => '<option value="' + escapeHtml(t) + '"' + (t === state.activeTenant ? ' selected' : '') + '>' + escapeHtml(t) + '</option>').join('');
}

// ═══════════ TENANTS PAGE ═══════════
async function loadTenantsPage() {
  const container = document.getElementById('tenantCards');
  container.innerHTML = '<div class="loading-spinner">Loading tenants...</div>';
  hideApiError();

  try {
    const data = await fetchTenants();
    state.tenants = data.tenants;
    populateTenantSelector(data.tenants);

    const badge = document.getElementById('tenantCountBadge');
    if (badge) badge.textContent = data.total;
    const statTotal = document.getElementById('statTotalTenants');
    if (statTotal) statTotal.textContent = data.total;

    if (data.tenants.length === 0) {
      container.innerHTML = '<div class="empty-state" style="grid-column:1/-1">No tenants found. Upload files to create a tenant.</div>';
      return;
    }

    // Fetch namespace counts in parallel
    const details = await Promise.allSettled(
      data.tenants.map(async t => {
        try {
          const ns = await fetchNamespaces(t);
          return { name: t, nsCount: ns.total };
        } catch {
          return { name: t, nsCount: 0 };
        }
      })
    );

    const tenantInfos = details.map(d => d.status === 'fulfilled' ? d.value : { name: '?', nsCount: 0 });
    renderTenantCards(tenantInfos);
  } catch (err) {
    container.innerHTML = '<div class="error-banner" style="grid-column:1/-1">' + escapeHtml(err.message) + '</div>';
  }
}

function renderTenantCards(infos) {
  const container = document.getElementById('tenantCards');
  container.innerHTML = infos.map(info => `
    <div class="tenant-card" onclick="selectTenant('${escapeHtml(info.name)}')">
      <div class="tenant-name">
        <div class="tenant-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></div>
        ${escapeHtml(info.name)}
        <span class="status status-active">Active</span>
      </div>
      <div class="tenant-stats">
        <span>${FILE_SVG_SM} — files</span>
        <span>${FOLDER_SVG_SM} ${info.nsCount} ns</span>
        <span>—</span>
      </div>
    </div>
  `).join('');
}

// ═══════════ FILE EXPLORER ═══════════

// --- Tree Panel ---
async function loadExplorerPage() {
  if (!state.activeTenant) {
    document.getElementById('treeContainer').innerHTML = '<div class="empty-state">Select a tenant first</div>';
    document.getElementById('fileGrid').innerHTML = '<div class="empty-state">Select a tenant to browse files</div>';
    document.getElementById('explorerPath').textContent = 'Select a tenant';
    return;
  }

  document.getElementById('treeContainer').innerHTML = '<div class="loading-spinner">Loading...</div>';

  try {
    const nsData = await fetchNamespaces(state.activeTenant);
    state.namespaces = nsData.namespaces;
    renderTree(nsData.namespaces);

    // Auto-select first namespace if none selected
    if (nsData.namespaces.length > 0 && !state.treePath.namespace) {
      state.treePath = { namespace: nsData.namespaces[0], path: '' };
    }
    if (state.treePath.namespace) {
      highlightTreeItem(state.treePath.namespace, state.treePath.path);
      loadDirectoryListing();
    }
  } catch (err) {
    document.getElementById('treeContainer').innerHTML = '<div class="error-banner">' + escapeHtml(err.message) + '</div>';
  }
}

function renderTree(namespaces) {
  const container = document.getElementById('treeContainer');
  if (namespaces.length === 0) {
    container.innerHTML = '<div class="empty-state">No namespaces</div>';
    return;
  }

  let html = '';
  for (const ns of namespaces) {
    const isActive = state.treePath.namespace === ns && state.treePath.path === '';
    html += `<div class="tree-item tree-ns${isActive ? ' active' : ''}" data-ns="${escapeHtml(ns)}" data-path="" onclick="selectTreeNode('${escapeHtml(ns)}','')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
      <strong>${escapeHtml(ns)}</strong>
    </div>`;
    // Render expanded children
    const nodeKey = ns + ':';
    if (state.expandedNodes.has(nodeKey)) {
      html += renderTreeChildrenPlaceholder(ns, '', 1);
    }
  }
  container.innerHTML = html;

  // Load children for expanded nodes
  for (const ns of namespaces) {
    const nodeKey = ns + ':';
    if (state.expandedNodes.has(nodeKey)) {
      loadTreeChildren(ns, '', 1);
    }
  }
}

function renderTreeChildrenPlaceholder(ns, path, depth) {
  return `<div id="tree-children-${escapeHtml(ns)}-${escapeHtml(path)}" class="tree-children"></div>`;
}

async function selectTreeNode(ns, path) {
  const nodeKey = ns + ':' + path;
  // Toggle expansion
  if (state.expandedNodes.has(nodeKey)) {
    state.expandedNodes.delete(nodeKey);
  } else {
    state.expandedNodes.add(nodeKey);
  }

  state.treePath = { namespace: ns, path: path };
  renderTree(state.namespaces);
  loadDirectoryListing();
}

async function loadTreeChildren(ns, path, depth) {
  const containerId = 'tree-children-' + ns + '-' + path;
  const container = document.getElementById(containerId);
  if (!container) return;

  try {
    const data = await fetchDirectory(state.activeTenant, ns, path);
    const dirs = data.entries.filter(e => e.type === 'directory');
    if (dirs.length === 0) {
      container.innerHTML = '';
      return;
    }
    let html = '';
    for (const dir of dirs) {
      const dirPath = path ? path + '/' + dir.name : dir.name;
      const isActive = state.treePath.namespace === ns && state.treePath.path === dirPath;
      const indentClass = 'indent-' + Math.min(depth, 3);
      html += `<div class="tree-item tree-folder ${indentClass}${isActive ? ' active' : ''}" data-ns="${escapeHtml(ns)}" data-path="${escapeHtml(dirPath)}" onclick="selectTreeNode('${escapeHtml(ns)}','${escapeHtml(dirPath)}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
        ${escapeHtml(dir.name)}
      </div>`;
      const childKey = ns + ':' + dirPath;
      if (state.expandedNodes.has(childKey)) {
        html += renderTreeChildrenPlaceholder(ns, dirPath, depth + 1);
      }
    }
    container.innerHTML = html;

    // Recursively load expanded children
    for (const dir of dirs) {
      const dirPath = path ? path + '/' + dir.name : dir.name;
      const childKey = ns + ':' + dirPath;
      if (state.expandedNodes.has(childKey)) {
        loadTreeChildren(ns, dirPath, depth + 1);
      }
    }
  } catch {
    container.innerHTML = '';
  }
}

function highlightTreeItem(ns, path) {
  document.querySelectorAll('.tree-item').forEach(el => el.classList.remove('active'));
  const item = document.querySelector(`.tree-item[data-ns="${ns}"][data-path="${path}"]`);
  if (item) item.classList.add('active');
}

// --- File List Panel ---
async function loadDirectoryListing() {
  const { namespace, path } = state.treePath;
  const grid = document.getElementById('fileGrid');
  grid.innerHTML = '<div class="loading-spinner">Loading...</div>';
  updateExplorerPath(namespace, path);

  try {
    const data = await fetchDirectory(state.activeTenant, namespace, path);
    renderFileList(data.entries);

    // Batch-fetch indexing status for files
    const fileIds = data.entries.filter(e => e.type === 'file' && e.file_id).map(e => e.file_id);
    if (fileIds.length > 0) {
      fetchBatch(state.activeTenant, fileIds, false).then(batchData => {
        for (const f of batchData.files) {
          const badge = document.getElementById('status-' + f.file_id);
          if (badge) {
            badge.className = 'status ' + getStatusClass(f.indexing_status);
            badge.textContent = f.indexing_status;
          }
        }
      }).catch(() => {});
    }
  } catch (err) {
    grid.innerHTML = '<div class="error-banner">' + escapeHtml(err.message) + '</div>';
  }
}

function renderFileList(entries) {
  const grid = document.getElementById('fileGrid');

  if (entries.length === 0) {
    grid.innerHTML = '<div class="empty-state">This directory is empty</div>';
    return;
  }

  // Sort: directories first, then files
  const sorted = [...entries].sort((a, b) => {
    if (a.type === 'directory' && b.type !== 'directory') return -1;
    if (a.type !== 'directory' && b.type === 'directory') return 1;
    return a.name.localeCompare(b.name);
  });

  grid.innerHTML = sorted.map(entry => {
    if (entry.type === 'directory') {
      return `<div class="file-row" onclick="navigateToDir('${escapeHtml(entry.name)}')">
        <div class="file-icon dir">${FOLDER_SVG}</div>
        <div class="file-info">
          <div class="file-name">${escapeHtml(entry.name)}</div>
          <div class="file-meta"><span>Directory</span></div>
        </div>
      </div>`;
    }

    const iconClass = getFileIconClass(entry.mime_type);
    const iconLabel = getFileIconLabel(entry.mime_type);
    const iconContent = iconClass === 'dir' ? FOLDER_SVG : escapeHtml(iconLabel);

    return `<div class="file-row" data-file-id="${escapeHtml(entry.file_id)}" onclick="selectFileRow(this,'${escapeHtml(entry.file_id)}')">
      <div class="file-icon ${iconClass}">${iconContent}</div>
      <div class="file-info">
        <div class="file-name">${escapeHtml(entry.name)}</div>
        <div class="file-meta">
          <span>${formatBytes(entry.size_bytes)}</span>
          <span>${escapeHtml(entry.mime_type || '')}</span>
          <span class="status status-pending" id="status-${escapeHtml(entry.file_id)}">...</span>
        </div>
      </div>
      <div class="file-actions">
        <button class="btn-icon" title="Download" onclick="event.stopPropagation();downloadFile('${escapeHtml(entry.file_id)}','${escapeHtml(entry.name)}')"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></button>
        <button class="btn-icon" title="Delete" onclick="event.stopPropagation();handleDeleteFile('${escapeHtml(entry.file_id)}','${escapeHtml(entry.name)}')"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg></button>
      </div>
    </div>`;
  }).join('');
}

function navigateToDir(dirName) {
  const { namespace, path } = state.treePath;
  const newPath = path ? path + '/' + dirName : dirName;
  // Expand tree node
  const nodeKey = namespace + ':' + (path || '');
  state.expandedNodes.add(nodeKey);
  state.treePath = { namespace, path: newPath };
  state.expandedNodes.add(namespace + ':' + newPath);
  renderTree(state.namespaces);
  loadDirectoryListing();
}

function updateExplorerPath(namespace, path) {
  const el = document.getElementById('explorerPath');
  let display = escapeHtml(state.activeTenant) + ' / ' + escapeHtml(namespace);
  if (path) display += ' / ' + escapeHtml(path);
  display += ' /';
  el.textContent = display;
}

// --- File Selection & Preview ---
function selectFileRow(el, fileId) {
  document.querySelectorAll('.file-row').forEach(r => r.classList.remove('selected'));
  el.classList.add('selected');
  state.selectedFileId = fileId;
  openPreview(fileId);
}

async function openPreview(fileId) {
  if (!fileId) return;
  state.previewOpen = true;

  // Show panel with loading
  document.getElementById('previewTitle').textContent = 'Loading...';
  document.getElementById('previewPathText').textContent = '';
  document.getElementById('previewMeta').innerHTML = '<div class="loading-spinner">Loading metadata...</div>';
  document.getElementById('previewContentText').textContent = '';
  document.getElementById('previewBackdrop').classList.add('visible');
  document.getElementById('previewPanel').classList.add('open');

  try {
    const data = await fetchBatch(state.activeTenant, [fileId], true, 10000);
    if (data.files.length > 0) {
      renderPreview(data.files[0]);
    } else {
      document.getElementById('previewTitle').textContent = 'File not found';
    }
  } catch (err) {
    document.getElementById('previewMeta').innerHTML = '<div class="error-banner">' + escapeHtml(err.message) + '</div>';
  }
}

function renderPreview(file) {
  document.getElementById('previewTitle').textContent = file.filename;
  document.getElementById('previewPathText').textContent = (file.namespace || '') + ' / ' + (file.path ? file.path + ' / ' : '') + file.filename;

  const meta = document.getElementById('previewMeta');
  meta.innerHTML = `
    <div class="preview-meta-row"><span class="label">File ID</span><span style="font-family:var(--font-mono);font-size:10px">${escapeHtml(file.file_id)}</span></div>
    <div class="preview-meta-row"><span class="label">Size</span><span>${formatBytes(file.size_bytes)}</span></div>
    <div class="preview-meta-row"><span class="label">MIME</span><span>${escapeHtml(file.mime_type)}</span></div>
    <div class="preview-meta-row"><span class="label">Status</span><span class="status ${getStatusClass(file.indexing_status)}">${escapeHtml(file.indexing_status)}</span></div>
    <div class="preview-meta-row"><span class="label">Created</span><span>${formatDate(file.created_at)}</span></div>
    <div class="preview-meta-row"><span class="label">Tags</span><span>${file.tags && file.tags.length ? escapeHtml(file.tags.join(', ')) : '—'}</span></div>
  `;

  const contentEl = document.getElementById('previewContentText');
  if (file.content == null) {
    contentEl.textContent = file.content_type === 'binary'
      ? '[Binary file — download to view]'
      : '[No content available]';
    if (file.download_url) {
      contentEl.innerHTML += '\n\n<a href="' + escapeHtml(file.download_url) + '" style="color:var(--accent)" download>Download file</a>';
    }
  } else if (file.content_type === 'json') {
    contentEl.textContent = typeof file.content === 'string' ? file.content : JSON.stringify(file.content, null, 2);
  } else {
    contentEl.textContent = file.content;
  }
  if (file.truncated) {
    contentEl.textContent += '\n\n[Content truncated — download for full file]';
  }
}

function closePreview() {
  document.getElementById('previewBackdrop').classList.remove('visible');
  document.getElementById('previewPanel').classList.remove('open');
  state.previewOpen = false;
}

// --- File Actions ---
function downloadFile(fileId, filename) {
  const url = API_BASE + '/v1/' + encodeURIComponent(state.activeTenant) + '/files/' + encodeURIComponent(fileId);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

async function handleDeleteFile(fileId, filename) {
  if (!confirm('Delete "' + filename + '"? This cannot be undone.')) return;
  try {
    await deleteFileApi(state.activeTenant, fileId);
    closePreview();
    loadDirectoryListing();
  } catch (err) {
    alert('Delete failed: ' + err.message);
  }
}

function handleNewFolder() {
  if (!state.activeTenant) { alert('Select a tenant first.'); return; }
  const name = prompt('Folder name:');
  if (!name || !name.trim()) return;
  const { namespace, path } = state.treePath;
  const fullPath = path ? path + '/' + name.trim() : name.trim();
  createDirectoryApi(state.activeTenant, namespace || 'default', fullPath)
    .then(() => {
      loadDirectoryListing();
      // Refresh tree
      state.expandedNodes.add((namespace || 'default') + ':' + (path || ''));
      renderTree(state.namespaces);
    })
    .catch(err => alert('Create folder failed: ' + err.message));
}

// ═══════════ SEARCH & RAG ═══════════
function setSearchMode(mode, tabEl) {
  state.searchMode = mode;
  document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
  if (tabEl) tabEl.classList.add('active');

  document.getElementById('ragExtras').style.display = mode === 'rag' ? 'block' : 'none';
  document.getElementById('ragAnswer').style.display = 'none';
  document.getElementById('similarInput').style.display = mode === 'similar' ? 'block' : 'none';
  document.getElementById('searchBoxWrap').style.display = mode === 'similar' ? 'none' : 'block';

  const input = document.getElementById('searchInput');
  input.placeholder = mode === 'rag' ? 'Ask a question (e.g. "What is our refund policy?")...' : 'Enter your search query...';
}

async function loadSearchNamespaces() {
  if (!state.activeTenant) return;
  try {
    const data = await fetchNamespaces(state.activeTenant);
    const select = document.getElementById('searchNamespace');
    select.innerHTML = '<option value="">All Namespaces</option>' +
      data.namespaces.map(ns => '<option value="' + escapeHtml(ns) + '">' + escapeHtml(ns) + '</option>').join('');
  } catch {}
}

async function executeSearch() {
  const tenant = state.activeTenant;
  if (!tenant) { alert('Select a tenant first.'); return; }

  const k = parseInt(document.getElementById('searchK').value) || 5;
  const namespace = document.getElementById('searchNamespace').value || undefined;
  const path = document.getElementById('searchPath').value || undefined;
  const resultsContainer = document.getElementById('searchResults');

  resultsContainer.innerHTML = '<div class="loading-spinner">Searching...</div>';
  document.getElementById('ragAnswer').style.display = 'none';

  try {
    let result;
    switch (state.searchMode) {
      case 'semantic': {
        const query = document.getElementById('searchInput').value;
        if (!query.trim()) { resultsContainer.innerHTML = '<div class="empty-state">Enter a search query</div>'; return; }
        result = await searchSemantic(tenant, { query, k, namespace, path });
        renderSearchResults(result.results);
        break;
      }
      case 'hybrid': {
        const query = document.getElementById('searchInput').value;
        if (!query.trim()) { resultsContainer.innerHTML = '<div class="empty-state">Enter a search query</div>'; return; }
        result = await searchHybrid(tenant, { query, k, namespace, path });
        renderSearchResults(result.results);
        break;
      }
      case 'similar': {
        const fileId = document.getElementById('similarFileIdInput').value;
        if (!fileId.trim()) { resultsContainer.innerHTML = '<div class="empty-state">Enter a file ID</div>'; return; }
        result = await findSimilar(tenant, fileId.trim(), k);
        renderSearchResults(result.results);
        break;
      }
      case 'rag': {
        const query = document.getElementById('searchInput').value;
        if (!query.trim()) { resultsContainer.innerHTML = '<div class="empty-state">Enter a question</div>'; return; }
        const systemPrompt = document.getElementById('ragSystemPrompt').value || undefined;
        result = await searchAsk(tenant, { query, k, namespace, path, system_prompt: systemPrompt });
        renderRagAnswer(result.answer);
        renderSearchResults(result.sources);
        break;
      }
    }
  } catch (err) {
    resultsContainer.innerHTML = '<div class="error-banner">' + escapeHtml(err.message) + '</div>';
  }
}

function renderSearchResults(hits) {
  const container = document.getElementById('searchResults');
  if (!hits || hits.length === 0) {
    container.innerHTML = '<div class="empty-state">No results found</div>';
    return;
  }

  container.innerHTML = hits.map((hit, i) => `
    <div class="search-result animate-slide-up" style="animation-delay:${i * 0.05}s">
      <div class="search-result-header">
        <span class="filename">${escapeHtml(hit.filename)}</span>
        <span class="chunk-idx">Chunk #${hit.chunk_idx}</span>
        <span class="score">${hit.score != null ? hit.score.toFixed(2) : '—'}</span>
      </div>
      <div class="search-result-body">${escapeHtml(hit.chunk_text)}</div>
      <div class="search-result-meta">
        <span>${FOLDER_SVG_SM} ${escapeHtml(hit.namespace || '')}${hit.path ? ' / ' + escapeHtml(hit.path) : ''}</span>
        <span>file_id: ${escapeHtml(truncateId(hit.file_id))}</span>
      </div>
    </div>
  `).join('');
}

function renderRagAnswer(answer) {
  const el = document.getElementById('ragAnswer');
  const textEl = document.getElementById('ragAnswerText');
  if (!answer) { el.style.display = 'none'; return; }
  textEl.textContent = answer;
  el.style.display = 'block';
}

// ═══════════ UPLOAD ═══════════
function initUploadDragDrop() {
  const drop = document.getElementById('uploadDrop');
  const fileInput = document.getElementById('fileInput');
  if (!drop || !fileInput) return;

  drop.addEventListener('click', () => fileInput.click());
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('drag-over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag-over'));
  drop.addEventListener('drop', e => {
    e.preventDefault();
    drop.classList.remove('drag-over');
    handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) handleFiles(fileInput.files);
    fileInput.value = '';
  });
}

function handleUploadClick() {
  const fileInput = document.getElementById('fileInput');
  if (fileInput.files.length > 0) {
    handleFiles(fileInput.files);
  } else {
    fileInput.click();
  }
}

async function loadUploadNamespaces() {
  if (!state.activeTenant) return;
  try {
    const data = await fetchNamespaces(state.activeTenant);
    const select = document.getElementById('uploadNamespace');
    select.innerHTML = data.namespaces.map(ns =>
      '<option value="' + escapeHtml(ns) + '">' + escapeHtml(ns) + '</option>'
    ).join('');
    if (data.namespaces.length === 0) {
      select.innerHTML = '<option value="default">default</option>';
    }
    populateFolderPicker(data.namespaces);
  } catch {}
}

async function handleFiles(files) {
  const tenant = state.activeTenant;
  if (!tenant) { alert('Select a tenant first.'); return; }

  const namespace = document.getElementById('uploadNamespace').value || 'default';
  const path = document.getElementById('uploadPathInput').value || '';
  const tags = document.getElementById('uploadTags').value || '';
  const resultsContainer = document.getElementById('uploadResults');

  for (const file of files) {
    const resultDiv = document.createElement('div');
    resultDiv.className = 'upload-result';
    resultDiv.innerHTML = '<span class="upload-filename">' + escapeHtml(file.name) + '</span><span class="upload-status"><span class="status status-processing">Uploading...</span></span>';
    resultsContainer.appendChild(resultDiv);

    try {
      const result = await uploadFileApi(tenant, file, namespace, path, tags);
      resultDiv.classList.add('success');
      resultDiv.querySelector('.upload-status').innerHTML =
        '<span class="status status-indexed">Uploaded</span> <code style="margin-left:6px">' + escapeHtml(truncateId(result.file_id, 16)) + '</code>';
      pollIndexingStatus(tenant, result.file_id, resultDiv);
    } catch (err) {
      resultDiv.classList.add('error');
      resultDiv.querySelector('.upload-status').innerHTML =
        '<span class="status status-failed">Failed: ' + escapeHtml(err.message) + '</span>';
    }
  }
}

async function pollIndexingStatus(tenant, fileId, resultDiv) {
  let delay = 1000;
  for (let i = 0; i < 8; i++) {
    await new Promise(r => setTimeout(r, delay));
    try {
      const status = await fetchIndexingStatus(tenant, fileId);
      const statusSpan = resultDiv.querySelector('.upload-status');
      statusSpan.innerHTML =
        '<span class="status ' + getStatusClass(status.indexing_status) + '">' + escapeHtml(status.indexing_status) + '</span>' +
        ' <code style="margin-left:6px">' + escapeHtml(truncateId(fileId, 16)) + '</code>';
      if (status.indexing_status === 'indexed' || status.indexing_status === 'failed') return;
    } catch {}
    delay = Math.min(delay * 2, 8000);
  }
}

// ═══════════ FOLDER PICKER ═══════════
async function populateFolderPicker(namespaces) {
  const dropdown = document.getElementById('fpDropdown');
  if (!dropdown) return;
  let html = '';

  for (const ns of namespaces) {
    html += `<div class="fp-item fp-ns" onclick="pickFolder('${escapeHtml(ns)}','')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
      <strong>${escapeHtml(ns)}</strong> /
    </div>`;
    try {
      const dirs = await fetchDirectory(state.activeTenant, ns, '');
      for (const entry of dirs.entries) {
        if (entry.type === 'directory') {
          html += `<div class="fp-item fp-folder fp-indent-1" onclick="pickFolder('${escapeHtml(ns)}','${escapeHtml(entry.name)}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
            ${escapeHtml(entry.name)} /
          </div>`;
        }
      }
    } catch {}
  }
  dropdown.innerHTML = html;
}

function toggleFolderPicker() {
  document.getElementById('fpDropdown').classList.toggle('open');
}

function pickFolder(ns, path) {
  const display = ns + (path ? ' / ' + path : '') + ' /';
  document.getElementById('fpSelectedText').textContent = display;
  document.getElementById('fpSelectedText').style.color = 'var(--text-primary)';
  document.getElementById('uploadPathInput').value = path;
  document.getElementById('fpDropdown').classList.remove('open');
  // Set namespace dropdown
  const nsSelect = document.getElementById('uploadNamespace');
  if (nsSelect) {
    for (const o of nsSelect.options) {
      if (o.value === ns) { o.selected = true; break; }
    }
  }
}

// ═══════════ KEYBOARD SHORTCUTS ═══════════
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && state.previewOpen) closePreview();
});

// ═══════════ INIT ═══════════
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initUploadDragDrop();
  loadTenantsPage();

  // Close folder picker on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.folder-picker')) {
      const dd = document.getElementById('fpDropdown');
      if (dd) dd.classList.remove('open');
    }
  });
});
