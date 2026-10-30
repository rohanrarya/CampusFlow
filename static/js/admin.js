/**
 * CampusFlow — Admin Handler (admin.js)
 * Handles login, dashboard auth guard, ticket listing,
 * filtering, resolving, and logout.
 */

/* ─────────────────────────────────────────────────────────── */
/*  Shared Utilities                                           */
/* ─────────────────────────────────────────────────────────── */

function showToast(message, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" style="stroke:var(--success);"><polyline points="20 6 9 17 4 12"/></svg>',
    error:   '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" style="stroke:var(--danger);"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info:    '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" style="stroke:var(--primary);"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-close" role="button" aria-label="Close">
      <svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>
    </span>
  `;

  container.appendChild(toast);
  const remove = () => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 320);
  };
  toast.querySelector('.toast-close').addEventListener('click', remove);
  setTimeout(remove, duration);
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    let s = String(dateStr).trim();
    if (s.includes(' ') && !s.includes('T')) {
      s = s.replace(' ', 'T');
    }
    if (!s.endsWith('Z') && !/[+-]\d{2}(:\d{2})?$/.test(s)) {
      s += 'Z';
    }
    const d = new Date(s);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleString('en-IN', {
      dateStyle: 'medium', timeStyle: 'short',
    });
  } catch { return dateStr; }
}

function normalizeUrgency(urgency) {
  if (!urgency) return 'Low';
  const u = String(urgency).toLowerCase().trim();
  if (u.includes('high') || u.includes('urgent') || u.includes('critical')) return 'High';
  if (u.includes('med')) return 'Medium';
  if (u.includes('low')) return 'Low';
  return 'Low';
}

const URGENCY_CONFIG = {
  High:   { badgeClass: 'badge-high',   dotClass: 'dot-high' },
  Medium: { badgeClass: 'badge-medium', dotClass: 'dot-medium' },
  Low:    { badgeClass: 'badge-low',    dotClass: 'dot-low' },
};

function urgencyBadge(urgency) {
  const norm = normalizeUrgency(urgency);
  const cfg = URGENCY_CONFIG[norm] || { badgeClass: 'badge-low', dotClass: 'dot-low' };
  return `<span class="badge ${cfg.badgeClass}"><span class="dot ${cfg.dotClass}"></span>${norm}</span>`;
}

function statusBadge(status) {
  const s = String(status || 'Pending').trim();
  const isResolved = s.toLowerCase() === 'resolved';
  const isInProgress = s.toLowerCase().includes('progress');

  if (isResolved) {
    return `<span class="badge badge-resolved"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:var(--success);"><polyline points="20 6 9 17 4 12"/></svg> Resolved</span>`;
  }
  if (isInProgress) {
    return `<span class="badge badge-inprogress"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:var(--info);"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg> In Progress</span>`;
  }
  return `<span class="badge badge-pending"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:var(--warning);"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Pending</span>`;
}

/* ─────────────────────────────────────────────────────────── */
/*  LOGIN PAGE                                                 */
/* ─────────────────────────────────────────────────────────── */

function initLoginPage() {
  const form     = document.getElementById('login-form');
  const errorBox = document.getElementById('login-error');
  const btnText  = document.getElementById('login-btn-text');
  const loginBtn = document.getElementById('login-btn');

  if (!form) return;

  /* If already logged in, skip to dashboard */
  if (sessionStorage.getItem('cf_token')) {
    window.location.href = 'admin-dashboard.html';
    return;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
      showLoginError('Please enter both username and password.');
      return;
    }

    /* Loading */
    loginBtn.disabled = true;
    if (btnText) btnText.innerHTML = '<span class="btn-spinner"></span> Signing in…';
    if (errorBox) errorBox.classList.remove('visible');

    try {
      const data = await adminLogin(username, password);
      sessionStorage.setItem('cf_token', data.token || 'authenticated');
      sessionStorage.setItem('cf_username', data.username || username);
      window.location.href = 'admin-dashboard.html';
    } catch (err) {
      showLoginError(err.message || 'Invalid credentials. Please try again.');
    } finally {
      loginBtn.disabled = false;
      if (btnText) btnText.textContent = 'Sign In';
    }
  });

  function showLoginError(msg) {
    if (!errorBox) return;
    errorBox.querySelector('.error-msg').textContent = msg;
    errorBox.classList.add('visible');
  }
}

/* ─────────────────────────────────────────────────────────── */
/*  DASHBOARD PAGE                                             */
/* ─────────────────────────────────────────────────────────── */

let allTickets = [];
let activeStatusFilter  = 'all';
let activeUrgencyFilter = 'all';
let currentView = 'table'; // 'table' or 'cards'

function initDashboardPage() {
  /* Auth guard */
  const token = sessionStorage.getItem('cf_token');
  if (!token) {
    window.location.href = 'admin-login.html';
    return;
  }

  /* Show username */
  const adminNameEl = document.getElementById('admin-name');
  if (adminNameEl) adminNameEl.textContent = sessionStorage.getItem('cf_username') || 'Admin';

  /* Logout */
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      sessionStorage.removeItem('cf_token');
      sessionStorage.removeItem('cf_username');
      window.location.href = 'admin-login.html';
    });
  }

  /* View switchers */
  const viewTableBtn = document.getElementById('view-table-btn');
  const viewCardsBtn = document.getElementById('view-cards-btn');

  if (viewTableBtn && viewCardsBtn) {
    viewTableBtn.addEventListener('click', () => {
      currentView = 'table';
      viewTableBtn.classList.add('active');
      viewCardsBtn.classList.remove('active');
      renderTickets();
    });

    viewCardsBtn.addEventListener('click', () => {
      currentView = 'cards';
      viewCardsBtn.classList.add('active');
      viewTableBtn.classList.remove('active');
      renderTickets();
    });
  }

  /* Filter buttons — status */
  document.querySelectorAll('[data-status-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeStatusFilter = btn.dataset.statusFilter;
      document.querySelectorAll('[data-status-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderTickets();
    });
  });

  /* Filter buttons — urgency */
  document.querySelectorAll('[data-urgency-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      activeUrgencyFilter = btn.dataset.urgencyFilter;
      document.querySelectorAll('[data-urgency-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderTickets();
    });
  });

  /* Refresh button */
  const refreshBtn = document.getElementById('refresh-btn');
  if (refreshBtn) refreshBtn.addEventListener('click', fetchTickets);

  /* Modal Close Listeners */
  const modalOverlay = document.getElementById('ticket-modal-overlay');
  const modalCloseBtn = document.getElementById('modal-close-btn');

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener('click', closeTicketModal);
  }

  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeTicketModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTicketModal();
  });

  fetchTickets();
  initMembersTab();
}

async function fetchTickets() {
  const grid    = document.getElementById('tickets-grid');
  const spinner = document.getElementById('spinner');
  if (!grid) return;

  /* 1. Instant cache render (0ms load time when opening dashboard) */
  const cachedData = sessionStorage.getItem('cf_cached_tickets');
  if (cachedData && allTickets.length === 0) {
    try {
      allTickets = JSON.parse(cachedData);
      updateDashStats();
      renderTickets();
    } catch {}
  } else if (allTickets.length === 0) {
    if (spinner) spinner.style.display = 'flex';
    grid.innerHTML = '';
  }

  /* 2. Fetch fresh data in background */
  try {
    const freshTickets = await getAllTickets();
    allTickets = freshTickets.sort((a, b) => {
      if (a.created_at && b.created_at) {
        const timeDiff = new Date(b.created_at) - new Date(a.created_at);
        if (timeDiff !== 0) return timeDiff;
      }
      return (b.id || 0) - (a.id || 0);
    });
    sessionStorage.setItem('cf_cached_tickets', JSON.stringify(allTickets));
    updateDashStats();
    renderTickets();
  } catch (err) {
    console.error('Failed to fetch tickets:', err);
    if (allTickets.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon"><svg class="ui-icon" width="40" height="40" viewBox="0 0 24 24" style="stroke:var(--warning);"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></span>
          <h3>Could not load tickets</h3>
          <p>${err.message || 'Please check your connection and try again.'}</p>
        </div>`;
      showToast('Failed to load tickets: ' + (err.message || ''), 'error');
    }
  } finally {
    if (spinner) spinner.style.display = 'none';
  }
}

function updateDashStats() {
  const total    = allTickets.length;
  const pending  = allTickets.filter(t => t.status?.toLowerCase() !== 'resolved').length;
  const resolved = allTickets.filter(t => t.status?.toLowerCase() === 'resolved').length;
  const high     = allTickets.filter(t => normalizeUrgency(t.urgency) === 'High').length;

  setEl('stat-total',    total);
  setEl('stat-pending',  pending);
  setEl('stat-resolved', resolved);
  setEl('stat-high',     high);
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function getFilteredTickets() {
  return allTickets.filter(ticket => {
    const statusMatch =
      activeStatusFilter === 'all' ||
      (activeStatusFilter === 'pending'  && ticket.status?.toLowerCase() !== 'resolved') ||
      (activeStatusFilter === 'resolved' && ticket.status?.toLowerCase() === 'resolved');

    const urgencyMatch =
      activeUrgencyFilter === 'all' ||
      normalizeUrgency(ticket.urgency).toLowerCase() === activeUrgencyFilter.toLowerCase();

    return statusMatch && urgencyMatch;
  });
}

function renderTickets() {
  const container = document.getElementById('tickets-grid');
  if (!container) return;

  const filtered = getFilteredTickets();

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon"><svg class="ui-icon" width="40" height="40" viewBox="0 0 24 24" style="stroke:var(--success);"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></span>
        <h3>No tickets found!</h3>
        <p>There are no tickets matching the current filter.</p>
      </div>`;
    return;
  }

  if (currentView === 'table') {
    container.innerHTML = buildTicketTable(filtered);

    /* Row click -> open modal */
    container.querySelectorAll('.ticket-row').forEach(row => {
      row.addEventListener('click', (e) => {
        if (e.target.closest('[data-resolve-id]')) return; // ignore resolve button click
        openTicketModal(row.dataset.ticketId);
      });
    });

    /* Attach direct resolve button listeners */
    container.querySelectorAll('[data-resolve-id]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        handleResolve(btn.dataset.resolveId, btn);
      });
    });

  } else {
    /* Cards View */
    container.innerHTML = `
      <div class="tickets-grid">
        ${filtered.map(ticket => buildTicketCard(ticket)).join('')}
      </div>
    `;

    container.querySelectorAll('.ticket-card').forEach(card => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('[data-resolve-id]')) return;
        openTicketModal(card.dataset.ticketId);
      });
    });

    container.querySelectorAll('[data-resolve-id]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        handleResolve(btn.dataset.resolveId, btn);
      });
    });
  }
}

function buildTicketTable(tickets) {
  return `
    <div class="table-responsive">
      <table class="tickets-table">
        <thead>
          <tr>
            <th>Ticket ID</th>
            <th>Problem Summary</th>
            <th>Category</th>
            <th>Department</th>
            <th>Location</th>
            <th>Urgency</th>
            <th>Status</th>
            <th style="text-align: right; width: 100px;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${tickets.map(t => {
            const isResolved = t.status?.toLowerCase() === 'resolved';
            const urgencyKey = t.urgency || 'Low';
            const rawDesc    = t.problem || t.description || 'No description provided';
            const shortDesc  = rawDesc.length > 55 ? rawDesc.slice(0, 55) + '…' : rawDesc;
            const displayId  = t.ticket_id || `#${t.id}`;
            const targetId   = t.ticket_id || t.id;
            const hasPhoto   = Boolean(t.image_url);

            return `
              <tr class="ticket-row ${isResolved ? 'resolved' : ''}" data-ticket-id="${targetId}" title="Click row to view full details">
                <td><span class="ticket-id-badge">${displayId}</span></td>
                <td>
                  <div class="table-problem-text" title="${escapeHtml(rawDesc)}">
                    ${hasPhoto ? '<span title="Photo attached" style="margin-right:4px;display:inline-flex;align-items:center;vertical-align:middle;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg></span>' : ''}
                    ${escapeHtml(shortDesc)}
                  </div>
                </td>
                <td><span class="badge badge-accent">${escapeHtml(t.category || 'General')}</span></td>
                <td><span style="display:inline-flex;align-items:center;gap:4px;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg> ${escapeHtml(t.department || '—')}</span></td>
                <td><span style="display:inline-flex;align-items:center;gap:4px;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg> ${escapeHtml(t.location || '—')}</span></td>
                <td>${urgencyBadge(urgencyKey)}</td>
                <td>${statusBadge(t.status)}</td>
                <td style="text-align: right;">
                  ${!isResolved ? `
                    <button class="btn btn-success btn-sm" data-resolve-id="${targetId}" title="Mark as Resolved" style="display:inline-flex;align-items:center;gap:4px;">
                      <svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:#fff;"><polyline points="20 6 9 17 4 12"/></svg> Resolve
                    </button>
                  ` : '<span class="badge badge-resolved" style="font-size: .7rem; padding: 2px 8px;">Resolved</span>'}
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function buildTicketCard(ticket) {
  const isResolved = ticket.status?.toLowerCase() === 'resolved';
  const urgencyKey = normalizeUrgency(ticket.urgency);
  const rawDesc    = ticket.problem || ticket.description || '';
  const shortDesc  = rawDesc
    ? rawDesc.slice(0, 160) + (rawDesc.length > 160 ? '…' : '')
    : 'No description provided.';
  const displayId  = ticket.ticket_id || `#${ticket.id}`;
  const resolveTargetId = ticket.ticket_id || ticket.id;
  const hasPhoto   = Boolean(ticket.image_url);

  return `
    <div class="ticket-card urgency-${urgencyKey.toLowerCase()} ${isResolved ? 'resolved' : ''}"
         data-ticket-id="${resolveTargetId}"
         id="ticket-${resolveTargetId}"
         style="cursor: pointer;"
         title="Click card to view details">
      <div>
        <div class="ticket-meta">
          <span class="ticket-id">${displayId}</span>
          ${hasPhoto ? '<span class="badge badge-accent" style="font-size:.7rem; padding:2px 8px; display:inline-flex; align-items:center; gap:3px;"><svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg> Photo</span>' : ''}
          ${urgencyBadge(urgencyKey)}
          ${statusBadge(ticket.status)}
          <span class="ticket-date">${formatDate(ticket.created_at)}</span>
        </div>

        <p class="ticket-description">${escapeHtml(shortDesc)}</p>

        <div class="ticket-footer">
          <span class="ticket-dept" style="display:inline-flex;align-items:center;gap:4px;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg> ${ticket.department || 'Unknown Dept.'}</span>
          <span class="badge badge-accent" style="margin-left:4px;">
            ${ticket.category || 'General'}
          </span>
          ${ticket.location ? `
          <span class="badge" style="margin-left:4px; background: rgba(0,0,0,0.06); color: var(--text-muted); display:inline-flex; align-items:center; gap:4px;">
            <svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg> ${escapeHtml(ticket.location)}
          </span>` : ''}
          ${ticket.submitted_by ? `
          <span class="badge" style="margin-left:4px; background: rgba(99,102,241,0.08); color: var(--primary); display:inline-flex; align-items:center; gap:4px;" title="Submitted by ${escapeHtml(ticket.submitted_by)}">
            <svg class="ui-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> ${escapeHtml(ticket.submitted_by)}
          </span>` : ''}
        </div>
      </div>

      <div class="ticket-actions">
        ${!isResolved ? `
          <button
            class="btn btn-success btn-sm"
            data-resolve-id="${resolveTargetId}"
            title="Mark as Resolved"
            style="display:inline-flex;align-items:center;gap:4px;"
          ><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:#fff;"><polyline points="20 6 9 17 4 12"/></svg> Resolve</button>
        ` : `
          <span class="badge badge-resolved"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:var(--success);"><polyline points="20 6 9 17 4 12"/></svg> Resolved</span>
        `}
      </div>
    </div>
  `;
}

/* ── Modal Details Popup ──────────────────────────────────── */
function openTicketModal(ticketId) {
  const ticket = allTickets.find(t =>
    String(t.ticket_id) === String(ticketId) || String(t.id) === String(ticketId)
  );

  if (!ticket) return;

  const overlay    = document.getElementById('ticket-modal-overlay');
  const titleEl    = document.getElementById('modal-ticket-id');
  const statusEl   = document.getElementById('modal-ticket-status');
  const bodyEl     = document.getElementById('modal-body');
  const footerEl   = document.getElementById('modal-footer');

  if (!overlay || !bodyEl) return;

  const displayId  = ticket.ticket_id || `#${ticket.id}`;
  const statusLower = (ticket.status || 'pending').toLowerCase();
  const isResolved = statusLower === 'resolved';
  const isInProgress = statusLower.includes('progress');
  const targetId   = ticket.ticket_id || ticket.id;

  if (titleEl) titleEl.textContent = `Ticket Details — ${displayId}`;
  if (statusEl) statusEl.innerHTML = statusBadge(ticket.status);

  bodyEl.innerHTML = `
    <div class="modal-info-grid">
      <div class="modal-info-item">
        <div class="modal-info-label">Category</div>
        <div class="modal-info-value"><span class="badge badge-accent">${escapeHtml(ticket.category || 'General')}</span></div>
      </div>

      <div class="modal-info-item">
        <div class="modal-info-label">Urgency Level</div>
        <div class="modal-info-value">${urgencyBadge(ticket.urgency || 'Low')}</div>
      </div>

      <div class="modal-info-item">
        <div class="modal-info-label">Assigned Department</div>
        <div class="modal-info-value" style="display:inline-flex;align-items:center;gap:5px;"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg> ${escapeHtml(ticket.department || 'Not Assigned')}</div>
      </div>

      <div class="modal-info-item">
        <div class="modal-info-label">Campus Location</div>
        <div class="modal-info-value" style="display:inline-flex;align-items:center;gap:5px;"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg> ${escapeHtml(ticket.location || 'Not Specified')}</div>
      </div>

      <div class="modal-info-item" style="grid-column: 1 / -1;">
        <div class="modal-info-label">Date Ticket Raised</div>
        <div class="modal-info-value" style="font-weight: 500; color: var(--text-muted);">${formatDate(ticket.created_at)}</div>
      </div>

      ${ticket.submitted_by ? `
      <div class="modal-info-item" style="grid-column: 1 / -1;">
        <div class="modal-info-label">Submitted By</div>
        <div class="modal-info-value" style="display:inline-flex;align-items:center;gap:6px;">
          <svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
          ${escapeHtml(ticket.submitted_by)} ${ticket.user_college_id ? `<span style="font-size:0.78rem; color:var(--text-muted);">(${escapeHtml(ticket.user_college_id)})</span>` : ''}
        </div>
      </div>` : ''}
    </div>

    <div class="modal-problem-box">
      <h4>Complaint Description</h4>
      <p>${escapeHtml(ticket.problem || ticket.description || 'No detailed description available.')}</p>
    </div>

    ${ticket.image_url ? `
    <div style="margin-top:16px;">
      <div style="font-size:.78rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;display:flex;align-items:center;gap:5px;"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg> Attached Photo (Cloudinary)</div>
      <a href="${ticket.image_url}" target="_blank" rel="noopener noreferrer" title="Click to view full photo in new tab">
        <img
          src="${ticket.image_url}"
          alt="Complaint photo"
          style="width:100%;max-height:280px;object-fit:cover;border-radius:var(--radius);border:1px solid var(--border);display:block;cursor:pointer;"
          loading="lazy"
        />
      </a>
      <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;display:flex;align-items:center;gap:5px;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg> Click image to open high-resolution photo in new tab</div>
    </div>` : ''}
  `;

  footerEl.innerHTML = `
    <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
      ${!isInProgress && !isResolved ? `
        <button class="btn btn-secondary btn-sm" id="modal-inprogress-btn" style="display:inline-flex;align-items:center;gap:4px;">
          <svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg> Mark In Progress
        </button>
      ` : ''}

      ${!isResolved ? `
        <button class="btn btn-success btn-sm" id="modal-resolve-btn" style="display:inline-flex;align-items:center;gap:4px;">
          <svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:#fff;"><polyline points="20 6 9 17 4 12"/></svg> Mark Resolved
        </button>
      ` : `
        <span class="badge badge-resolved" style="padding: 6px 12px; font-size: .8rem; display:inline-flex; align-items:center; gap:4px;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24" style="stroke:var(--success);"><polyline points="20 6 9 17 4 12"/></svg> Resolved</span>
        <button class="btn btn-secondary btn-sm" id="modal-reopen-btn" style="display:inline-flex;align-items:center;gap:4px;">
          <svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg> Reopen Ticket
        </button>
      `}
    </div>
    <button class="btn btn-secondary" id="modal-close-action">Close</button>
  `;

  /* Attach modal buttons */
  const modalResolveBtn = document.getElementById('modal-resolve-btn');
  if (modalResolveBtn) {
    modalResolveBtn.addEventListener('click', async () => {
      await handleStatusUpdate(targetId, 'Resolved', modalResolveBtn);
      openTicketModal(targetId);
    });
  }

  const modalInProgressBtn = document.getElementById('modal-inprogress-btn');
  if (modalInProgressBtn) {
    modalInProgressBtn.addEventListener('click', async () => {
      await handleStatusUpdate(targetId, 'In Progress', modalInProgressBtn);
      openTicketModal(targetId);
    });
  }

  const modalReopenBtn = document.getElementById('modal-reopen-btn');
  if (modalReopenBtn) {
    modalReopenBtn.addEventListener('click', async () => {
      await handleStatusUpdate(targetId, 'Pending', modalReopenBtn);
      openTicketModal(targetId);
    });
  }

  const modalCloseAction = document.getElementById('modal-close-action');
  if (modalCloseAction) {
    modalCloseAction.addEventListener('click', closeTicketModal);
  }

  overlay.classList.add('visible');
}

function closeTicketModal() {
  const overlay = document.getElementById('ticket-modal-overlay');
  if (overlay) overlay.classList.remove('visible');
}

async function handleStatusUpdate(ticketId, newStatus, btn) {
  const originalHTML = btn.innerHTML;
  btn.disabled  = true;
  btn.innerHTML = '<span class="btn-spinner"></span>';

  try {
    await updateTicketStatus(ticketId, newStatus);

    /* Update local state */
    const idx = allTickets.findIndex(t =>
      String(t.ticket_id) === String(ticketId) || String(t.id) === String(ticketId)
    );
    if (idx !== -1) allTickets[idx].status = newStatus;

    updateDashStats();
    renderTickets();
    showToast(`Ticket ${ticketId} updated to "${newStatus}"!`, 'success');
  } catch (err) {
    console.error('Status update error:', err);
    btn.disabled  = false;
    btn.innerHTML = originalHTML;
    showToast(err.message || 'Failed to update ticket status.', 'error');
  }
}

async function handleResolve(ticketId, btn) {
  return handleStatusUpdate(ticketId, 'Resolved', btn);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ─────────────────────────────────────────────────────────── */
/*  Boot — detect which page we're on                         */
/* ─────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('login-form')) {
    initLoginPage();
  } else if (document.getElementById('tickets-grid')) {
    initDashboardPage();
  }
});


/* ─────────────────────────────────────────────────────────── */
/*  MEMBERS & SPREADSHEET ROSTER MODULE                        */
/* ─────────────────────────────────────────────────────────── */

let allMembers = [];

function initMembersTab() {
  const tabComplaintsBtn = document.getElementById('tab-complaints-btn');
  const tabMembersBtn = document.getElementById('tab-members-btn');
  const secComplaints = document.getElementById('section-complaints');
  const secMembers = document.getElementById('section-members');

  if (!tabComplaintsBtn || !tabMembersBtn) return;

  tabComplaintsBtn.addEventListener('click', () => {
    tabComplaintsBtn.classList.add('active');
    tabMembersBtn.classList.remove('active');
    if (secComplaints) secComplaints.style.display = 'block';
    if (secMembers) secMembers.style.display = 'none';
  });

  tabMembersBtn.addEventListener('click', () => {
    tabMembersBtn.classList.add('active');
    tabComplaintsBtn.classList.remove('active');
    if (secComplaints) secComplaints.style.display = 'none';
    if (secMembers) secMembers.style.display = 'block';
    loadAdminMembers();
    loadSpreadsheetConfigUI();
  });

  // Search input
  const searchInput = document.getElementById('member-search-input');
  let memberSearchTimer = null;
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      clearTimeout(memberSearchTimer);
      memberSearchTimer = setTimeout(() => {
        loadAdminMembers(searchInput.value.trim());
      }, 300);
    });
  }

  // Add Member Modal
  const openAddBtn = document.getElementById('btn-open-add-member');
  const addModal = document.getElementById('add-member-modal-overlay');
  const addCloseBtn = document.getElementById('add-member-close-btn');
  const addCancelBtn = document.getElementById('add-member-cancel-btn');
  const addForm = document.getElementById('add-member-form');
  const addBtnText = document.getElementById('add-member-btn-text');

  if (openAddBtn && addModal) {
    openAddBtn.addEventListener('click', () => {
      if (addForm) addForm.reset();
      addModal.classList.add('visible');
    });
  }
  const closeAddModal = () => { if (addModal) addModal.classList.remove('visible'); };
  if (addCloseBtn) addCloseBtn.addEventListener('click', closeAddModal);
  if (addCancelBtn) addCancelBtn.addEventListener('click', closeAddModal);
  if (addModal) {
    addModal.addEventListener('click', (e) => { if (e.target === addModal) closeAddModal(); });
  }

  if (addForm) {
    addForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const cid = document.getElementById('new-college-id').value.trim();
      const name = document.getElementById('new-name').value.trim();
      const dept = document.getElementById('new-dept').value.trim();
      const role = document.getElementById('new-role').value;
      const email = document.getElementById('new-email').value.trim();

      if (!cid || !name) {
        showToast('College ID and Name are required.', 'error');
        return;
      }

      if (addBtnText) addBtnText.innerHTML = '<span class="btn-spinner"></span> Saving…';

      try {
        const res = await addAdminMember({
          college_id: cid,
          name: name,
          department: dept,
          role: role,
          email: email
        });
        showToast(res.message || 'Member added successfully!', 'success');
        closeAddModal();
        loadAdminMembers();
        loadSpreadsheetConfigUI();
      } catch (err) {
        showToast(err.message || 'Failed to add member', 'error');
      } finally {
        if (addBtnText) addBtnText.textContent = 'Save to Roster & Sheet';
      }
    });
  }

  // Sheet Config Modal
  const openConfigBtn = document.getElementById('btn-config-sheet');
  const configModal = document.getElementById('config-sheet-modal-overlay');
  const configCloseBtn = document.getElementById('config-sheet-close-btn');
  const configCancelBtn = document.getElementById('config-sheet-cancel-btn');
  const configForm = document.getElementById('config-sheet-form');

  if (openConfigBtn && configModal) {
    openConfigBtn.addEventListener('click', async () => {
      try {
        const cfg = await fetchSpreadsheetConfig();
        const urlInput = document.getElementById('config-sheet-url');
        const webhookInput = document.getElementById('config-webhook-url');
        if (urlInput) urlInput.value = cfg.google_sheet_url || '';
        if (webhookInput) webhookInput.value = cfg.webhook_url || '';
      } catch (e) {}
      configModal.classList.add('visible');
    });
  }
  const closeConfigModal = () => { if (configModal) configModal.classList.remove('visible'); };
  if (configCloseBtn) configCloseBtn.addEventListener('click', closeConfigModal);
  if (configCancelBtn) configCancelBtn.addEventListener('click', closeConfigModal);
  if (configModal) {
    configModal.addEventListener('click', (e) => { if (e.target === configModal) closeConfigModal(); });
  }

  if (configForm) {
    configForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const sheetUrl = document.getElementById('config-sheet-url').value.trim();
      const webhookUrl = document.getElementById('config-webhook-url').value.trim();

      try {
        await saveSpreadsheetConfig({ google_sheet_url: sheetUrl, webhook_url: webhookUrl });
        showToast('Spreadsheet configuration saved!', 'success');
        closeConfigModal();
        loadSpreadsheetConfigUI();
      } catch (err) {
        showToast(err.message || 'Failed to save settings', 'error');
      }
    });
  }

  // Sync Sheet Button
  const syncBtn = document.getElementById('btn-sync-sheet');
  const syncBtnText = document.getElementById('btn-sync-sheet-text');
  if (syncBtn) {
    syncBtn.addEventListener('click', async () => {
      syncBtn.disabled = true;
      if (syncBtnText) syncBtnText.innerHTML = '<span class="btn-spinner"></span> Syncing…';

      try {
        const res = await syncSpreadsheet();
        showToast(`Sync complete! Added: ${res.added}, Updated: ${res.updated} members.`, 'success');
        loadAdminMembers();
        loadSpreadsheetConfigUI();
      } catch (err) {
        showToast(err.message || 'Failed to sync with Google Sheet', 'error');
      } finally {
        syncBtn.disabled = false;
        if (syncBtnText) syncBtnText.textContent = 'Sync with Google Sheet';
      }
    });
  }

  // Import CSV input
  const csvInput = document.getElementById('csv-file-input');
  if (csvInput) {
    csvInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      try {
        const res = await importMembersCSV(file);
        showToast(res.message || 'CSV imported successfully!', 'success');
        loadAdminMembers();
        loadSpreadsheetConfigUI();
      } catch (err) {
        showToast(err.message || 'Failed to import CSV', 'error');
      } finally {
        csvInput.value = '';
      }
    });
  }
}

async function loadSpreadsheetConfigUI() {
  try {
    const cfg = await fetchSpreadsheetConfig();
    const countBadge = document.getElementById('members-count-badge');
    const lastSynced = document.getElementById('sheet-last-synced');
    const statusText = document.getElementById('sheet-status-text');

    if (countBadge) countBadge.textContent = cfg.total_members || 0;
    if (lastSynced) lastSynced.textContent = cfg.last_synced_at || 'Never';

    if (statusText) {
      if (cfg.google_sheet_url) {
        statusText.textContent = 'Connected: Google Sheet Active';
      } else {
        statusText.textContent = 'Active (Neon DB Directory)';
      }
    }
  } catch (err) {
    console.error('Error loading spreadsheet config:', err);
  }
}

async function loadAdminMembers(search = '') {
  const container = document.getElementById('members-table-container');
  if (!container) return;

  try {
    const members = await fetchAdminMembers(search);
    allMembers = members;

    const countBadge = document.getElementById('members-count-badge');
    if (countBadge) countBadge.textContent = members.length;

    if (!members || members.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </div>
          <h3>No members found</h3>
          <p>${search ? 'No results matching "' + escapeHtml(search) + '".' : 'Click "Add Student / Member" or sync from your Google Sheet to populate the roster.'}</p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <table class="tickets-table">
        <thead>
          <tr>
            <th>College ID</th>
            <th>Member Name</th>
            <th>Department</th>
            <th>Role</th>
            <th>Email</th>
            <th style="text-align:right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${members.map(m => {
            const isFaculty = (m.role || '').toLowerCase() === 'faculty';
            return `
              <tr>
                <td><span class="ticket-id-badge" style="font-weight:700;">${escapeHtml(m.college_id)}</span></td>
                <td><strong style="color:#fff;">${escapeHtml(m.name)}</strong></td>
                <td>${escapeHtml(m.department || '—')}</td>
                <td>
                  <span class="role-badge" style="${isFaculty ? 'background:rgba(245,158,11,0.2);color:#fbbf24;border-color:rgba(245,158,11,0.4);' : ''}">
                    ${escapeHtml((m.role || 'student').toUpperCase())}
                  </span>
                </td>
                <td style="color:var(--text-muted); font-size:0.85rem;">${escapeHtml(m.email || '—')}</td>
                <td style="text-align:right;">
                  <button
                    class="btn btn-secondary btn-sm delete-member-btn"
                    data-college-id="${escapeHtml(m.college_id)}"
                    data-name="${escapeHtml(m.name)}"
                    style="padding:4px 10px; font-size:0.75rem; color:#ef4444; border-color:rgba(239,68,68,0.35); cursor:pointer;"
                    title="Remove member"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;

    // Attach delete listeners
    container.querySelectorAll('.delete-member-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const cid = btn.dataset.collegeId;
        const name = btn.dataset.name;
        if (!confirm(`Are you sure you want to remove ${name} (${cid}) from the roster?`)) return;

        try {
          await deleteAdminMember(cid);
          showToast(`Member ${cid} removed.`, 'success');
          loadAdminMembers();
          loadSpreadsheetConfigUI();
        } catch (err) {
          showToast(err.message || 'Failed to delete member', 'error');
        }
      });
    });

  } catch (err) {
    console.error('Failed to load members:', err);
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon"><svg class="ui-icon" width="36" height="36" viewBox="0 0 24 24" style="stroke:var(--danger);"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg></span>
        <h3>Could not load members</h3>
        <p>${escapeHtml(err.message || 'Please check your connection and try again.')}</p>
      </div>
    `;
  }
}
