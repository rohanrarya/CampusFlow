/**
 * CampusFlow — Authentication & Navigation Controller (auth.js)
 * Manages mobile drawer navigation and user helpers.
 */

// Key names in localStorage
const AUTH_TOKEN_KEY = 'cf_user_token';
const AUTH_USER_KEY  = 'cf_user_data';

function getUserToken() {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function getCurrentUser() {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function isUserLoggedIn() {
  return !!getUserToken();
}

function saveUserSession(token, user) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

function logoutUser() {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    localStorage.removeItem('cf_verified_member');
  }
  window.location.reload();
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

/**
 * Mobile Navigation Drawer Handler
 */
function initMobileNavbar() {
  const navbar = document.querySelector('.navbar');
  const navContainer = document.querySelector('.navbar-nav');
  if (!navbar || !navContainer) return;

  let overlay = document.querySelector('.navbar-mobile-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'navbar-mobile-overlay';
    document.body.appendChild(overlay);
  }

  let toggleBtn = document.getElementById('navbar-toggle');
  if (!toggleBtn) {
    toggleBtn = document.createElement('button');
    toggleBtn.id = 'navbar-toggle';
    toggleBtn.className = 'navbar-toggle';
    toggleBtn.setAttribute('aria-label', 'Toggle navigation menu');
    toggleBtn.innerHTML = `
      <svg class="ui-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="4" y1="6" x2="20" y2="6"/>
        <line x1="4" y1="12" x2="20" y2="12"/>
        <line x1="4" y1="18" x2="20" y2="18"/>
      </svg>
    `;
    navbar.appendChild(toggleBtn);
  }

  const closeMenu = () => {
    navContainer.classList.remove('active');
    overlay.classList.remove('active');
    toggleBtn.innerHTML = `
      <svg class="ui-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="4" y1="6" x2="20" y2="6"/>
        <line x1="4" y1="12" x2="20" y2="12"/>
        <line x1="4" y1="18" x2="20" y2="18"/>
      </svg>
    `;
  };

  const openMenu = () => {
    navContainer.classList.add('active');
    overlay.classList.add('active');
    toggleBtn.innerHTML = `
      <svg class="ui-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    `;
  };

  toggleBtn.onclick = (e) => {
    e.stopPropagation();
    if (navContainer.classList.contains('active')) {
      closeMenu();
    } else {
      openMenu();
    }
  };

  overlay.onclick = closeMenu;

  navContainer.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) {
        closeMenu();
      }
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    initMobileNavbar();
  });
}
