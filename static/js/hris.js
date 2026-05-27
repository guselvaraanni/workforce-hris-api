(function () {
  'use strict';

  const themeKey = 'hris_theme';
  const sidebarKey = 'hris_sidebar_collapsed';

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const sun = document.querySelector('[data-theme-icon="sun"]');
    const moon = document.querySelector('[data-theme-icon="moon"]');
    if (sun && moon) {
      sun.style.display = theme === 'dark' ? 'none' : 'block';
      moon.style.display = theme === 'dark' ? 'block' : 'none';
    }
  }

  const storedTheme = localStorage.getItem(themeKey) || 'dark';
  applyTheme(storedTheme);

  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      localStorage.setItem(themeKey, next);
      applyTheme(next);
    });
  }

  const sidebar = document.getElementById('app-sidebar');
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const collapseBtn = document.getElementById('sidebar-collapse');

  function closeMobileSidebar() {
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('visible');
  }

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      if (window.innerWidth <= 1024) {
        sidebar.classList.toggle('mobile-open');
        if (sidebarBackdrop) sidebarBackdrop.classList.toggle('visible');
      }
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', closeMobileSidebar);
  }

  if (collapseBtn) {
    const collapsed = localStorage.getItem(sidebarKey) === '1';
    if (collapsed && window.innerWidth > 1024) {
      document.body.classList.add('sidebar-collapsed');
    }
    collapseBtn.addEventListener('click', () => {
      document.body.classList.toggle('sidebar-collapsed');
      localStorage.setItem(
        sidebarKey,
        document.body.classList.contains('sidebar-collapsed') ? '1' : '0'
      );
    });
  }

  window.addEventListener('resize', () => {
    if (window.innerWidth > 1024) closeMobileSidebar();
  });

  const profileTrigger = document.getElementById('profile-trigger');
  const profileDropdown = document.getElementById('profile-dropdown');
  if (profileTrigger && profileDropdown) {
    profileTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      profileDropdown.classList.toggle('open');
    });
    document.addEventListener('click', () => profileDropdown.classList.remove('open'));
    profileDropdown.addEventListener('click', (e) => e.stopPropagation());
  }

  window.logoutAction = function (event) {
    if (event) event.preventDefault();
    const logoutUrl = document.body.dataset.logoutUrl || '/logout/';
    fetch(logoutUrl, { method: 'GET', credentials: 'include' }).finally(() => {
      try { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); } catch (err) {}
      window.location.href = '/';
    });
  };

  window.hrisAttendance = {
    async checkIn(btn) {
      return window.hrisAttendance._action('/api/v1/attendance/check_in/', btn, 'Check In');
    },
    async checkOut(btn) {
      return window.hrisAttendance._action('/api/v1/attendance/check_out/', btn, 'Check Out');
    },
    async _action(url, btn, label) {
      const statusEl = document.getElementById('attendance-action-status');
      if (btn) { btn.disabled = true; }
      if (statusEl) statusEl.textContent = 'Processing...';

      try {
        const res = await fetch(url, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
          },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          if (statusEl) statusEl.textContent = data.error || data.detail || 'Action failed.';
          if (btn) btn.disabled = false;
          return;
        }
        if (statusEl) statusEl.textContent = 'Updated. Reloading...';
        setTimeout(() => window.location.reload(), 800);
      } catch (err) {
        if (statusEl) statusEl.textContent = 'Network error.';
        if (btn) btn.disabled = false;
      }
    },
  };

  window.submitQuickLeave = async function () {
    const statusEl = document.getElementById('quick-leave-status');
    if (statusEl) statusEl.textContent = 'Submitting...';

    const payload = {
      leave_type: document.getElementById('quick_leave_type')?.value,
      start_date: document.getElementById('quick_start_date')?.value,
      end_date: document.getElementById('quick_end_date')?.value,
      reason: document.getElementById('quick_reason')?.value,
    };

    if (!payload.start_date || !payload.end_date || !payload.reason) {
      if (statusEl) statusEl.textContent = 'Please fill all fields.';
      return;
    }

    try {
      const res = await fetch('/api/v1/leave-requests/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(payload),
      });
      const result = await res.json();
      if (!res.ok) {
        if (statusEl) statusEl.textContent = result.detail || result.error || 'Validation error.';
        return;
      }
      if (statusEl) statusEl.textContent = 'Submitted. Reloading...';
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      if (statusEl) statusEl.textContent = 'Network error.';
    }
  };
})();
