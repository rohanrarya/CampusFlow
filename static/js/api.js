/**
 * CampusFlow — API Module (api.js)
 * Handles all communication with the backend REST API.
 */

// Automatic origin detection (works seamlessly on localhost and production hosting)
const API_BASE = (typeof window !== 'undefined' && window.location.origin && window.location.protocol.startsWith('http'))
  ? (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port && !['8000'].includes(window.location.port)
    ? 'http://127.0.0.1:8000'
    : window.location.origin
  : 'http://127.0.0.1:8000';

/**
 * Helper to convert Base64 Data URL to a native Blob
 * @param {string} dataURI - Base64 Data URL
 * @returns {Promise<Blob>}
 */
async function dataURItoBlob(dataURI) {
  const res = await fetch(dataURI);
  return await res.blob();
}

/**
 * Generate a unique submission ID for complaint idempotency
 * @returns {string}
 */
function generateSubmissionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'sub_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
}

/**
 * Direct client-to-Cloudinary upload helper.
 * Uploads photo directly to Cloudinary using signed authorization from backend,
 * completely bypassing Vercel/serverless 4.5MB payload limits.
 * @param {Blob} photoBlob
 * @returns {Promise<string>} Secure Cloudinary image URL
 */
async function uploadDirectToCloudinary(photoBlob) {
  // 1. Fetch upload authorization signature from backend
  const signRes = await fetch(`${API_BASE}/cloudinary-sign`);
  if (!signRes.ok) {
    throw new Error('Failed to retrieve Cloudinary upload authorization');
  }
  const signData = await signRes.json();

  // 2. Post file directly to Cloudinary REST API
  const cldFormData = new FormData();
  cldFormData.append('file', photoBlob);
  cldFormData.append('api_key', signData.api_key);
  cldFormData.append('timestamp', signData.timestamp);
  cldFormData.append('signature', signData.signature);

  const uploadRes = await fetch(`https://api.cloudinary.com/v1_1/${signData.cloud_name}/image/upload`, {
    method: 'POST',
    body: cldFormData
  });

  if (!uploadRes.ok) {
    const errorJson = await uploadRes.json().catch(() => ({}));
    throw new Error(errorJson.error?.message || 'Direct Cloudinary upload failed');
  }

  const uploadData = await uploadRes.json();
  return uploadData.secure_url;
}

/**
 * Submit a new complaint.
 * 1. If photo is attached, uploads directly to Cloudinary
 * 2. Sends complaint details + Cloudinary image_url to backend
 * 3. Falls back gracefully to backend multipart upload if needed
 * @param {string} text - The complaint description text.
 * @param {Blob|File|string|null} photo - Optional photo (Blob, File, or Base64 Data URL).
 * @param {Function|null} onStatusUpdate - Status callback during upload
 * @param {string|null} collegeId - Verified College ID of the student/faculty
 * @returns {Promise<Object>} Ticket object
 */
async function submitComplaint(text, photo = null, onStatusUpdate = null, collegeId = null, isAnonymous = false) {
  let photoBlob = null;
  if (photo) {
    if (photo instanceof Blob || (typeof File !== 'undefined' && photo instanceof File)) {
      photoBlob = photo;
    } else if (typeof photo === 'string' && photo.startsWith('data:')) {
      photoBlob = await dataURItoBlob(photo);
    }
  }

  let imageUrl = null;
  if (photoBlob) {
    if (onStatusUpdate) onStatusUpdate('Uploading photo to Cloudinary…');
    try {
      imageUrl = await uploadDirectToCloudinary(photoBlob);
    } catch (cldErr) {
      console.warn('Direct Cloudinary upload failed, falling back to backend upload:', cldErr);
    }
  }

  if (onStatusUpdate) onStatusUpdate('Analyzing with AI & submitting…');

  const formData = new FormData();
  formData.append('message', text);
  formData.append('submission_id', generateSubmissionId());

  if (collegeId) {
    formData.append('college_id', collegeId);
  }
  
  if (isAnonymous) {
    formData.append('is_anonymous', 'true');
  }

  if (imageUrl) {
    formData.append('image_url', imageUrl);
  } else if (photoBlob) {
    formData.append('photo', photoBlob, 'complaint_photo.jpg');
  }

  // Attach session token if present
  const userToken = (typeof localStorage !== 'undefined') ? localStorage.getItem('cf_user_token') : null;
  if (userToken) {
    formData.append('token', userToken);
  }

  const reqHeaders = {};
  if (userToken) {
    reqHeaders['Authorization'] = `Bearer ${userToken}`;
  }

  const response = await fetch(`${API_BASE}/complaint`, {
    method: 'POST',
    headers: reqHeaders,
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const msg = errorData.detail || errorData.message || `Server error: ${response.status}`;
    throw new Error(msg);
  }

  const data = await response.json();
  if (data.ticket) {
    return {
      ...data.ticket,
      description: data.ticket.problem || text,
      created_at: normalizeTicketDate(data.ticket.created_at) || new Date().toISOString(),
    };
  }
  return data;
}

/**
 * Normalize UTC ISO date strings from backend.
 * @param {string|null} dateStr
 * @returns {string|null}
 */
function normalizeTicketDate(dateStr) {
  if (!dateStr) return null;
  let s = String(dateStr).trim();
  if (s.includes(' ') && !s.includes('T')) {
    s = s.replace(' ', 'T');
  }
  if (!s.endsWith('Z') && !/[+-]\d{2}(:\d{2})?$/.test(s)) {
    s += 'Z';
  }
  return s;
}

/**
 * Retrieve all tickets.
 * GET /tickets
 * @returns {Promise<Array>} Array of ticket objects.
 */
async function getAllTickets() {
  const response = await fetch(`${API_BASE}/tickets`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const msg = errorData.detail || errorData.message || `Server error: ${response.status}`;
    throw new Error(msg);
  }

  const tickets = await response.json();
  return tickets.map(t => ({
    ...t,
    description: t.problem || t.description || 'No description provided.',
    created_at: normalizeTicketDate(t.created_at),
  }));
}

/**
 * Retrieve a single ticket by ID.
 * GET /tickets/:ticket_id
 * @param {string|number} ticketId
 * @returns {Promise<Object>} Ticket object
 */
async function getTicket(ticketId) {
  const response = await fetch(`${API_BASE}/tickets/${ticketId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const msg = errorData.detail || errorData.message || `Server error: ${response.status}`;
    throw new Error(msg);
  }

  const ticket = await response.json();
  return {
    ...ticket,
    description: ticket.problem || ticket.description || 'No description provided.',
    created_at: normalizeTicketDate(ticket.created_at),
  };
}

/**
 * Update the status of a specific ticket.
 * PATCH /tickets/:ticket_id
 * @param {string|number} id - The ticket_id (or ID) to update.
 * @param {string} status - New status: "Pending", "In Progress", or "Resolved"
 * @returns {Promise<Object>} Updated ticket response.
 */
async function updateTicketStatus(id, status) {
  const reqHeaders = {
    'Content-Type': 'application/json',
  };
  const adminToken = (typeof sessionStorage !== 'undefined') ? sessionStorage.getItem('cf_token') : null;
  if (adminToken) {
    reqHeaders['Authorization'] = `Bearer ${adminToken}`;
  }

  const response = await fetch(`${API_BASE}/tickets/${id}`, {
    method: 'PATCH',
    headers: reqHeaders,
    body: JSON.stringify({ status: status }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const msg = errorData.detail || errorData.message || `Server error: ${response.status}`;
    throw new Error(msg);
  }

  return response.json();
}

/**
 * Resolve a specific ticket.
 * @param {string|number} id
 * @returns {Promise<Object>}
 */
async function resolveTicket(id) {
  return updateTicketStatus(id, 'Resolved');
}

/**
 * Check backend health
 * @returns {Promise<boolean>}
 */
async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Authenticate an admin user.
 * @param {string} username
 * @param {string} password
 * @returns {Promise<Object>}
 */
async function adminLogin(username, password) {
  if (!username || !password) {
    throw new Error('Please enter both username and password.');
  }

  const response = await fetch(`${API_BASE}/admin/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: username.trim(),
      password: password,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const msg = errorData.detail || errorData.message || 'Invalid admin credentials. Access denied.';
    throw new Error(msg);
  }

  const data = await response.json();
  return {
    token: data.token,
    username: data.username || username,
  };
}

/* ─────────────────────────────────────────────────────────── */
/*  Spreadsheet & Campus Member Verification Functions        */
/* ─────────────────────────────────────────────────────────── */

/**
 * Verify a student or faculty member's College ID against the spreadsheet roster.
 * GET /members/verify/:college_id
 * @param {string} collegeId
 * @returns {Promise<Object>} { verified: boolean, member?: Object, message?: string }
 */
async function verifyMemberCollegeId(collegeId) {
  const cleanId = (collegeId || '').trim();
  if (!cleanId) {
    return { verified: false, message: 'Please enter a College ID.' };
  }

  
  const response = await fetch(`${API_BASE}/members/verify/${encodeURIComponent(cleanId)}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    return { verified: false, message: err.detail || 'Verification request failed.' };
  }

  return response.json();
}



/**
 * Helper to get Admin Authorization header
 */
function getAdminAuthHeader() {
  const token = (typeof sessionStorage !== 'undefined') ? sessionStorage.getItem('cf_token') : null;
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

/**
 * List all members in the roster for Admin Dashboard.
 * GET /admin/members
 * @param {string} search
 * @returns {Promise<Array>}
 */
async function fetchAdminMembers(search = '') {
  const query = search ? `?search=${encodeURIComponent(search)}` : '';
  const response = await fetch(`${API_BASE}/admin/members${query}`, {
    method: 'GET',
    headers: {
      ...getAdminAuthHeader(),
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch members roster');
  }

  return response.json();
}

/**
 * Add a new student or faculty member via Admin UI.
 * POST /admin/members
 * @param {Object} memberData { college_id, name, department, email, role }
 * @returns {Promise<Object>}
 */
async function addAdminMember(memberData) {
  const response = await fetch(`${API_BASE}/admin/members`, {
    method: 'POST',
    headers: {
      ...getAdminAuthHeader(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(memberData)
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to add new student');
  }

  return response.json();
}

/**
 * Delete a member from roster by College ID.
 * DELETE /admin/members/:college_id
 * @param {string} collegeId
 * @returns {Promise<Object>}
 */
async function deleteAdminMember(collegeId) {
  const response = await fetch(`${API_BASE}/admin/members/${encodeURIComponent(collegeId)}`, {
    method: 'DELETE',
    headers: getAdminAuthHeader()
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to remove member');
  }

  return response.json();
}

/**
 * Get current Google Sheet config and sync status.
 * GET /admin/spreadsheet/config
 * @returns {Promise<Object>}
 */
async function fetchSpreadsheetConfig() {
  const response = await fetch(`${API_BASE}/admin/spreadsheet/config`, {
    method: 'GET',
    headers: getAdminAuthHeader()
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch spreadsheet configuration');
  }

  return response.json();
}

/**
 * Save Google Sheet configuration.
 * POST /admin/spreadsheet/config
 * @param {Object} config { google_sheet_url, webhook_url }
 * @returns {Promise<Object>}
 */
async function saveSpreadsheetConfig(config) {
  const response = await fetch(`${API_BASE}/admin/spreadsheet/config`, {
    method: 'POST',
    headers: {
      ...getAdminAuthHeader(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(config)
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save spreadsheet settings');
  }

  return response.json();
}

/**
 * Trigger on-demand sync from Google Sheet.
 * POST /admin/spreadsheet/sync
 * @param {string} sheetUrl
 * @returns {Promise<Object>}
 */
async function syncSpreadsheet(sheetUrl = '') {
  const response = await fetch(`${API_BASE}/admin/spreadsheet/sync`, {
    method: 'POST',
    headers: {
      ...getAdminAuthHeader(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ sheet_url: sheetUrl })
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to sync with Google Sheet');
  }

  return response.json();
}

/**
 * Bulk import members via CSV file.
 * POST /admin/members/import-csv
 * @param {File} file
 * @returns {Promise<Object>}
 */
async function importMembersCSV(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/admin/members/import-csv`, {
    method: 'POST',
    headers: getAdminAuthHeader(),
    body: formData
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to import CSV');
  }

  return response.json();
}

/**
 * Submit student 1-5 star feedback rating for a resolved complaint
 */
async function submitTicketFeedback(ticketId, rating, feedback = '') {
  const res = await fetch(`${API_BASE}/tickets/${ticketId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rating: parseInt(rating), feedback })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Could not submit feedback');
  }
  return await res.json();
}

/**
 * Fetch UGC & NAAC compliance grievance statistics
 */
async function fetchComplianceReport() {
  const token = sessionStorage.getItem('cf_token');
  const res = await fetch(`${API_BASE}/admin/compliance-report`, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
  });
  if (!res.ok) throw new Error('Failed to fetch compliance report');
  return await res.json();
}
