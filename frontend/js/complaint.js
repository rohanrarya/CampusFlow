/**
 * CampusFlow — Complaint Form Handler (complaint.js)
 * Handles form submission, result display, and toast notifications.
 */

/* ── Toast Notifications ──────────────────────────────────── */
function showToast(message, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: '<svg class="ui-icon" width="18" height="18" viewBox="0 0 24 24" style="color:#10b981;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    error: '<svg class="ui-icon" width="18" height="18" viewBox="0 0 24 24" style="color:#ef4444;"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info: '<svg class="ui-icon" width="18" height="18" viewBox="0 0 24 24" style="color:#6366f1;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-message" style="flex:1; color:#0f172a !important; font-weight:500; margin:0 8px;">${message}</span>
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

/* ── Urgency & Status Helpers ────────────────────────────── */
function normalizeUrgency(urgency) {
  if (!urgency) return 'Low';
  const u = String(urgency).toLowerCase().trim();
  if (u.includes('high') || u.includes('urgent') || u.includes('critical')) return 'High';
  if (u.includes('med')) return 'Medium';
  if (u.includes('low')) return 'Low';
  return 'Low';
}

function getUrgencyBadge(urgency) {
  const norm = normalizeUrgency(urgency);
  const cfg = {
    High:   { class: 'badge-high',   dot: 'dot-high',   label: 'High' },
    Medium: { class: 'badge-medium', dot: 'dot-medium', label: 'Medium' },
    Low:    { class: 'badge-low',    dot: 'dot-low',    label: 'Low' },
  }[norm] || { class: 'badge-low', dot: 'dot-low', label: 'Low' };

  return `<span class="badge ${cfg.class}"><span class="dot ${cfg.dot}"></span>${cfg.label}</span>`;
}

function getStatusBadge(status) {
  const s = String(status || 'Pending').trim();
  const isResolved = s.toLowerCase() === 'resolved';
  const isInProgress = s.toLowerCase().includes('progress');

  if (isResolved) {
    return `<span class="badge badge-resolved"><svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24" style="color:#065f46;margin-right:4px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>Resolved</span>`;
  }
  if (isInProgress) {
    return `<span class="badge badge-inprogress"><svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24" style="color:#0369a1;margin-right:4px;"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>In Progress</span>`;
  }
  return `<span class="badge badge-pending"><svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24" style="color:#1e40af;margin-right:4px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>Pending</span>`;
}

/* ── Format Date ──────────────────────────────────────────── */
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
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return dateStr;
  }
}

/* ── Result Display ───────────────────────────────────────── */
function displayResult(ticket) {
  const resultArea = document.getElementById('result-area');
  if (!resultArea) return;

  const urgencyBadge = getUrgencyBadge(ticket.urgency);
  const statusBadge  = getStatusBadge(ticket.status);
  const date         = formatDate(ticket.created_at || new Date().toISOString());
  const displayId    = ticket.ticket_id || (ticket.id ? `#${ticket.id}` : 'N/A');

  resultArea.innerHTML = `
    <div class="result-card">
      <div class="result-success-header">
        <div class="result-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        </div>
        <div>
          <div class="result-title">Complaint Submitted!</div>
          <div class="result-subtitle">Track your complaint using the ticket ID below.</div>
        </div>
      </div>

      <div class="result-grid">
        <div class="result-field" style="grid-column: 1 / -1;">
          <div class="result-field-label">Ticket ID</div>
          <div class="result-field-value">
            <span class="ticket-id-badge">${displayId}</span>
          </div>
        </div>

        <div class="result-field">
          <div class="result-field-label">Category</div>
          <div class="result-field-value">${ticket.category || '—'}</div>
        </div>

        <div class="result-field">
          <div class="result-field-label">Department</div>
          <div class="result-field-value">${ticket.department || '—'}</div>
        </div>

        <div class="result-field">
          <div class="result-field-label">Location</div>
          <div class="result-field-value">${ticket.location || '—'}</div>
        </div>

        <div class="result-field">
          <div class="result-field-label">Urgency Level</div>
          <div class="result-field-value">${urgencyBadge}</div>
        </div>

        <div class="result-field">
          <div class="result-field-label">Status</div>
          <div class="result-field-value">${statusBadge}</div>
        </div>

        <div class="result-field">
          <div class="result-field-label">Submitted On</div>
          <div class="result-field-value" style="font-weight: 500; color: var(--text-muted);">${date}</div>
        </div>

        ${ticket.submitted_by ? `
        <div class="result-field">
          <div class="result-field-label">Submitted By</div>
          <div class="result-field-value">${escapeHtml(ticket.submitted_by)} ${ticket.user_college_id ? `<span style="font-size:0.75rem; color:var(--text-muted);">(${escapeHtml(ticket.user_college_id)})</span>` : ''}</div>
        </div>` : ''}

        ${ticket.problem || ticket.description ? `
        <div class="result-field" style="grid-column: 1 / -1;">
          <div class="result-field-label">Identified Problem</div>
          <div class="result-field-value">${ticket.problem || ticket.description}</div>
        </div>` : ''}
      </div>

      ${ticket.image_url ? `
      <div style="margin-top:16px;">
        <div class="result-field-label" style="margin-bottom:8px; display:inline-flex; align-items:center; gap:5px;">
          <svg class="ui-icon" width="15" height="15" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
          Attached Photo
        </div>
        <a href="${ticket.image_url}" target="_blank" rel="noopener noreferrer" title="Click to view full photo">
          <img
            src="${ticket.image_url}"
            alt="Complaint photo"
            style="width:100%;max-height:240px;object-fit:cover;border-radius:var(--radius);border:1px solid var(--border);display:block;cursor:pointer;"
            loading="lazy"
          />
        </a>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px; display:inline-flex; align-items:center; gap:4px;">
          <svg class="ui-icon" width="12" height="12" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          Click image to view high-resolution photo in new tab
        </div>
      </div>` : ''}

      <p style="margin-top: 16px; font-size: .82rem; color: var(--text-muted); line-height: 1.6; display:flex; align-items:flex-start; gap:8px;">
        <svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" style="color:var(--primary);flex-shrink:0;margin-top:2px;"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
        <span>Save your ticket ID for reference. Our team will review and address your complaint promptly.</span>
      </p>
    </div>
  `;

  resultArea.classList.add('visible');
  resultArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ── Form Validation ──────────────────────────────────────── */
function validateForm(textarea) {
  const value = textarea.value.trim();
  const errorEl = document.getElementById('complaint-error');
  const charCount = document.getElementById('char-count');

  if (charCount) charCount.textContent = value.length;

  if (!value) {
    textarea.classList.add('error');
    if (errorEl) { errorEl.textContent = 'Please describe your complaint.'; errorEl.classList.add('visible'); }
    return false;
  }

  if (value.length < 20) {
    textarea.classList.add('error');
    if (errorEl) { errorEl.textContent = 'Please provide at least 20 characters for a meaningful complaint.'; errorEl.classList.add('visible'); }
    return false;
  }

  textarea.classList.remove('error');
  if (errorEl) errorEl.classList.remove('visible');
  return true;
}

/* ── Camera & Photo State ─────────────────────────────────── */
let capturedPhotoBase64 = null;   // holds the Base64 string to send to backend

/* ── Camera Logic ─────────────────────────────────────────── */
function initCameraFeature() {
  const cameraNativeInput = document.getElementById('camera-native-input');
  const fileInput         = document.getElementById('file-input');
  const openCameraLabel   = document.getElementById('open-camera-label');
  const removePhotoBtn    = document.getElementById('remove-photo-btn');

  if (!cameraNativeInput && !fileInput) return; // not on a page with camera UI

  // Detect mobile and tablet devices
  const isMobileOrTablet = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|Tablet/i.test(navigator.userAgent)
    || (navigator.maxTouchPoints > 1 && /Macintosh/i.test(navigator.userAgent)) // iPadOS
    || (window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

  // Show "Open Camera" on mobile and tablet only; hide for PC users
  if (openCameraLabel) {
    if (isMobileOrTablet) {
      openCameraLabel.style.setProperty('display', 'inline-flex', 'important');
    } else {
      openCameraLabel.style.setProperty('display', 'none', 'important');
    }
  }

  /* — Process selected image file with auto-resize and client compression — */
  function handleSelectedFile(file, inputEl) {
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      showToast('Please select a valid image file (JPEG, PNG, WEBP, etc.)', 'error', 4000);
      if (inputEl) inputEl.value = '';
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      showToast('Selected image is larger than 20MB. Please select a smaller photo.', 'error', 4000);
      if (inputEl) inputEl.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        // High-res smartphones shoot 12MP-48MP photos. Resize to max 1280px for instant upload.
        const MAX_DIM = 1280;
        let width = img.width;
        let height = img.height;

        if (width > MAX_DIM || height > MAX_DIM) {
          if (width > height) {
            height = Math.round((height * MAX_DIM) / width);
            width = MAX_DIM;
          } else {
            width = Math.round((width * MAX_DIM) / height);
            height = MAX_DIM;
          }
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        capturedPhotoBase64 = canvas.toDataURL('image/jpeg', 0.85);
        showPhotoPreview(capturedPhotoBase64);
        if (inputEl) inputEl.value = '';
      };

      img.onerror = () => {
        // Fallback to original Base64 if canvas drawing fails
        capturedPhotoBase64 = e.target.result;
        showPhotoPreview(capturedPhotoBase64);
        if (inputEl) inputEl.value = '';
      };

      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  /* — Native device camera input (fires when user takes photo on mobile / tablet) — */
  if (cameraNativeInput) {
    cameraNativeInput.addEventListener('change', (e) => {
      handleSelectedFile(e.target.files[0], cameraNativeInput);
    });
  }

  /* — Choose from gallery (file picker) — */
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      handleSelectedFile(e.target.files[0], fileInput);
    });
  }

  /* — Remove attached photo — */
  if (removePhotoBtn) {
    removePhotoBtn.addEventListener('click', () => {
      capturedPhotoBase64 = null;
      const previewWrap = document.getElementById('photo-preview-wrap');
      if (previewWrap) previewWrap.style.display = 'none';
      removePhotoBtn.style.display = 'none';
      if (fileInput) fileInput.value = '';
      if (cameraNativeInput) cameraNativeInput.value = '';
    });
  }
}

function showPhotoPreview(base64) {
  const img = document.getElementById('photo-preview-img');
  const wrap = document.getElementById('photo-preview-wrap');
  const removeBtn = document.getElementById('remove-photo-btn');

  if (img) img.src = base64;
  if (wrap) wrap.style.display = 'block';
  if (removeBtn) removeBtn.style.display = 'inline-flex';
  showToast('Photo attached! It will be uploaded with your complaint.', 'info', 3000);
}

/* ── Form Submit Handler ──────────────────────────────────── */
function initComplaintForm() {
  const form      = document.getElementById('complaint-form');
  const textarea  = document.getElementById('complaint-text');
  const submitBtn = document.getElementById('submit-btn');
  const btnText   = document.getElementById('btn-text');

  if (!form || !textarea || !submitBtn) return;

  /* Live character count */
  textarea.addEventListener('input', () => {
    const charCount = document.getElementById('char-count');
    if (charCount) charCount.textContent = textarea.value.length;
    if (textarea.value.trim().length >= 20) {
      textarea.classList.remove('error');
      const errEl = document.getElementById('complaint-error');
      if (errEl) errEl.classList.remove('visible');
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!validateForm(textarea)) return;

    if (typeof isUserLoggedIn === 'function' && !isUserLoggedIn()) {
      showToast('Please sign in with your College ID before submitting a complaint.', 'error', 5000);
      if (typeof initAuthGate === 'function') initAuthGate();
      return;
    }

    const complaintText = textarea.value.trim();

    /* Disable submit button while uploading photo & submitting complaint */
    submitBtn.disabled = true;
    submitBtn.style.cursor = 'not-allowed';
    if (btnText) {
      btnText.innerHTML = capturedPhotoBase64
        ? '<span class="btn-spinner"></span> Uploading photo to Cloudinary…'
        : '<span class="btn-spinner"></span> Submitting…';
    }

    /* Hide previous result */
    const resultArea = document.getElementById('result-area');
    if (resultArea) resultArea.classList.remove('visible');

    try {
      // Pass the Base64 photo and status callback to update button text dynamically
      const ticket = await submitComplaint(complaintText, capturedPhotoBase64, (status) => {
        if (btnText) {
          btnText.innerHTML = `<span class="btn-spinner"></span> ${status}`;
        }
      });
      displayResult(ticket);
      showToast('Complaint submitted successfully!', 'success');

      /* Reset form & photo state */
      form.reset();
      capturedPhotoBase64 = null;
      const charCount = document.getElementById('char-count');
      if (charCount) charCount.textContent = '0';
      const previewWrap = document.getElementById('photo-preview-wrap');
      if (previewWrap) previewWrap.style.display = 'none';
      const removeBtn = document.getElementById('remove-photo-btn');
      if (removeBtn) removeBtn.style.display = 'none';
      const cameraNativeInput = document.getElementById('camera-native-input');
      if (cameraNativeInput) cameraNativeInput.value = '';

      /* Refresh home stats & complaints table */
      loadHomeStats();
      fetchAndRenderHomeComplaints();

    } catch (err) {
      console.error('Complaint submission error:', err);
      showToast(err.message || 'Failed to submit complaint. Please try again.', 'error', 6000);
    } finally {
      submitBtn.disabled = false;
      submitBtn.style.cursor = 'pointer';
      if (btnText) {
        btnText.innerHTML = 'Submit Complaint <svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" style="stroke:#fff;margin-left:4px;"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>';
      }
    }
  });
}

/* ── Home Page Live Stats ─────────────────────────────────── */
async function loadHomeStats() {
  const resolvedEl = document.getElementById('home-stat-resolved');
  const pendingEl  = document.getElementById('home-stat-pending');
  const deptsEl    = document.getElementById('home-stat-depts');

  if (!resolvedEl && !pendingEl) return;

  try {
    const tickets = await getAllTickets();
    const resolved = tickets.filter(t => t.status?.toLowerCase() === 'resolved').length;
    const pending  = tickets.filter(t => t.status?.toLowerCase() !== 'resolved').length;
    const depts    = new Set(tickets.map(t => t.department).filter(Boolean)).size;

    if (resolvedEl) resolvedEl.textContent = resolved;
    if (pendingEl)  pendingEl.textContent  = pending;
    if (deptsEl)    deptsEl.textContent    = depts || 0;
  } catch {
    // If backend is offline or starting up, keep default numbers
  }
}

/* ── Recent Complaints Feed (5 items, Show More, Show All) ── */
let allHomeTickets = [];
let homeDisplayLimit = 5;

async function fetchAndRenderHomeComplaints() {
  const container = document.getElementById('home-complaints-container');
  if (!container) return;

  try {
    allHomeTickets = await getAllTickets();
    allHomeTickets.sort((a, b) => {
      if (a.created_at && b.created_at) {
        const timeDiff = new Date(b.created_at) - new Date(a.created_at);
        if (timeDiff !== 0) return timeDiff;
      }
      return (b.id || 0) - (a.id || 0);
    });
    renderHomeComplaints();
  } catch (err) {
    console.error('Failed to load recent complaints:', err);
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon"><svg class="ui-icon" width="40" height="40" viewBox="0 0 24 24" style="stroke:var(--warning);"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></span>
        <h3>Could not load recent complaints</h3>
        <p>Make sure the backend is running. We will keep checking.</p>
      </div>`;
  }
}

function renderHomeComplaints() {
  const container = document.getElementById('home-complaints-container');
  const showMoreBtn = document.getElementById('show-more-btn');
  const showingCountEl = document.getElementById('showing-count');
  const totalCountEl = document.getElementById('total-count');

  if (!container) return;

  if (allHomeTickets.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon"><svg class="ui-icon" width="40" height="40" viewBox="0 0 24 24" style="stroke:var(--success);"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></span>
        <h3>No complaints reported yet!</h3>
        <p>All campus facilities are currently in great condition.</p>
      </div>`;
    if (showMoreBtn) showMoreBtn.style.display = 'none';
    return;
  }

  const visibleTickets = allHomeTickets.slice(0, homeDisplayLimit);

  if (showingCountEl) showingCountEl.textContent = visibleTickets.length;
  if (totalCountEl)   totalCountEl.textContent   = allHomeTickets.length;

  container.innerHTML = `
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
          </tr>
        </thead>
        <tbody>
          ${visibleTickets.map(t => {
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
                <td>${getUrgencyBadge(urgencyKey)}</td>
                <td>${getStatusBadge(t.status)}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;

  /* Attach click listeners */
  container.querySelectorAll('.ticket-row').forEach(row => {
    row.addEventListener('click', () => openHomeModal(row.dataset.ticketId));
  });

  /* Show More Button Visibility */
  if (showMoreBtn) {
    if (allHomeTickets.length > homeDisplayLimit) {
      showMoreBtn.style.display = 'inline-flex';
    } else {
      showMoreBtn.style.display = 'none';
    }
  }
}

/* ── Student Details Modal Popup ──────────────────────────── */
function openHomeModal(ticketId) {
  const ticket = allHomeTickets.find(t =>
    String(t.ticket_id) === String(ticketId) || String(t.id) === String(ticketId)
  );

  if (!ticket) return;

  const overlay  = document.getElementById('home-modal-overlay');
  const titleEl  = document.getElementById('home-modal-ticket-id');
  const statusEl = document.getElementById('home-modal-ticket-status');
  const bodyEl   = document.getElementById('home-modal-body');

  if (!overlay || !bodyEl) return;

  const displayId = ticket.ticket_id || `#${ticket.id}`;

  if (titleEl) titleEl.textContent = `Ticket Details — ${displayId}`;
  if (statusEl) statusEl.innerHTML = getStatusBadge(ticket.status);

  bodyEl.innerHTML = `
    <div class="modal-info-grid">
      <div class="modal-info-item">
        <div class="modal-info-label">Category</div>
        <div class="modal-info-value"><span class="badge badge-accent">${escapeHtml(ticket.category || 'General')}</span></div>
      </div>

      <div class="modal-info-item">
        <div class="modal-info-label">Urgency Level</div>
        <div class="modal-info-value">${getUrgencyBadge(ticket.urgency || 'Low')}</div>
      </div>

      <div class="modal-info-item">
        <div class="modal-info-label">Department</div>
        <div class="modal-info-value" style="display:inline-flex;align-items:center;gap:5px;"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg> ${escapeHtml(ticket.department || 'Not Assigned')}</div>
      </div>

      <div class="modal-info-item">
        <div class="modal-info-label">Location</div>
        <div class="modal-info-value" style="display:inline-flex;align-items:center;gap:5px;"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg> ${escapeHtml(ticket.location || 'Not Specified')}</div>
      </div>

      <div class="modal-info-item" style="grid-column: 1 / -1;">
        <div class="modal-info-label">Date Submitted</div>
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
      <h4>Full Complaint Description</h4>
      <p>${escapeHtml(ticket.problem || ticket.description || 'No detailed description available.')}</p>
    </div>

    ${ticket.image_url ? `
    <div style="margin-top:16px;">
      <div style="font-size:.78rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;display:flex;align-items:center;gap:5px;"><svg class="ui-icon" width="14" height="14" viewBox="0 0 24 24"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg> Attached Photo (Cloudinary)</div>
      <a href="${ticket.image_url}" target="_blank" rel="noopener noreferrer" title="Click to view full photo in new tab">
        <img
          src="${ticket.image_url}"
          alt="Complaint photo"
          style="width:100%;max-height:260px;object-fit:cover;border-radius:var(--radius);border:1px solid var(--border);display:block;cursor:pointer;"
          loading="lazy"
        />
      </a>
      <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;display:flex;align-items:center;gap:5px;"><svg class="ui-icon" width="13" height="13" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6M8 11h6"/></svg> Click image to open high-resolution photo in new tab</div>
    </div>` : ''}
  `;

  overlay.classList.add('visible');
}

function closeHomeModal() {
  const overlay = document.getElementById('home-modal-overlay');
  if (overlay) overlay.classList.remove('visible');
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

/* ── Boot ─────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initComplaintForm();
  initCameraFeature();
  loadHomeStats();
  fetchAndRenderHomeComplaints();

  /* Show More Button */
  const showMoreBtn = document.getElementById('show-more-btn');
  if (showMoreBtn) {
    showMoreBtn.addEventListener('click', () => {
      homeDisplayLimit += 5;
      renderHomeComplaints();
    });
  }

  /* Modal Close Listeners */
  const closeBtn = document.getElementById('home-modal-close-btn');
  const closeActionBtn = document.getElementById('home-modal-close-action');
  const overlay = document.getElementById('home-modal-overlay');

  if (closeBtn) closeBtn.addEventListener('click', closeHomeModal);
  if (closeActionBtn) closeActionBtn.addEventListener('click', closeHomeModal);
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeHomeModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeHomeModal();
  });
});
