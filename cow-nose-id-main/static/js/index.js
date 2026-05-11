document.addEventListener('DOMContentLoaded', async () => {
  const user = await requireUser();
  if (!user) return;

  renderUser(user);
  setAdminLinkVisibility(user.role);
  document.getElementById('identifyForm')?.addEventListener('submit', handleIdentify);
  document.getElementById('logoutButton')?.addEventListener('click', logout);
});

async function requireUser() {
  try {
    const response = await fetch('/auth/me');
    if (response.status === 401) {
      window.location.href = '/login';
      return null;
    }
    if (response.status === 403) {
      window.location.href = '/block';
      return null;
    }
    if (!response.ok) {
      showMessage('uploadMessage', '사용자 정보를 확인할 수 없습니다.', true);
      return null;
    }
    return await response.json();
  } catch (_error) {
    showMessage('uploadMessage', '서버에 연결할 수 없습니다.', true);
    return null;
  }
}

function renderUser(user) {
  const label = `${user.username || '사용자'} | ${user.role || 'role 없음'}`;
  const currentUser = document.getElementById('currentUser');
  const sidebarUser = document.getElementById('sidebarUser');
  if (currentUser) currentUser.textContent = label;
  if (sidebarUser) sidebarUser.textContent = user.username || '사용자';
}

async function handleIdentify(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const fileInput = document.getElementById('file');
  const resultPanel = document.getElementById('identifyResult');

  if (!fileInput?.files?.length) {
    showMessage('uploadMessage', '이미지를 선택하세요.', true);
    return;
  }

  const formData = new FormData(form);
  showMessage('uploadMessage', '식별을 진행 중입니다.');

  try {
    const response = await fetch('/api/identify', {
      method: 'POST',
      body: formData
    });
    const result = await response.json();

    if (response.status === 401) {
      window.location.href = '/login';
      return;
    }
    if (response.status === 403) {
      window.location.href = '/block';
      return;
    }
    if (!response.ok || result.success === false) {
      renderResult(resultPanel, null);
      showMessage('uploadMessage', result.error || result.message || '식별에 실패했습니다.', true);
      return;
    }

    renderResult(resultPanel, result.data || result);
    appendHistory(result.data || result);
    showMessage('uploadMessage', '식별이 완료되었습니다.');
  } catch (_error) {
    renderResult(resultPanel, null);
    showMessage('uploadMessage', '업로드 중 오류가 발생했습니다.', true);
  }
}

function renderResult(container, data) {
  if (!container) return;
  if (!data) {
    container.className = 'empty-state';
    container.textContent = '표시할 식별 결과가 없습니다.';
    return;
  }

  container.className = 'result-details';
  const entries = normalizeResult(data);
  container.innerHTML = '';
  entries.forEach(([label, value]) => {
    const row = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = `${label}: `;
    row.append(strong, document.createTextNode(value ?? '-'));
    container.appendChild(row);
  });
}

function normalizeResult(data) {
  return [
    ['소 ID', data.cow_id ?? data.id],
    ['이름', data.name],
    ['이표 번호', data.ear_tag],
    ['소유자', data.owner_name ?? data.owner],
    ['신뢰도', data.confidence ?? data.score],
    ['상태', data.status ?? data.message]
  ].filter(([, value]) => value !== undefined && value !== null && value !== '');
}

function appendHistory(data) {
  const list = document.getElementById('historyList');
  if (!list) return;
  if (list.classList.contains('empty-state')) {
    list.className = 'history-list';
    list.innerHTML = '';
  }

  const item = document.createElement('div');
  item.className = 'history-item';
  const name = data.name || data.cow_id || data.id || '식별 결과';
  item.textContent = `${new Date().toLocaleString()} - ${name}`;
  list.prepend(item);
}

function showMessage(id, text, isError = false) {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = text;
  element.classList.toggle('error-message', isError);
}

function isAdmin(role) {
  const normalizedRole = String(role || '').toLowerCase();
  return normalizedRole === 'admin' || normalizedRole === 'super';
}

async function logout() {
  await fetch('/auth/logout', { method: 'POST' }).catch(() => {});
  window.location.href = '/login';
}

function setAdminLinkVisibility(role) {
  const adminLink = document.getElementById('adminLink');
  if (!adminLink) return;
  const allowed = isAdmin(role);
  adminLink.hidden = !allowed;
  adminLink.setAttribute('aria-hidden', String(!allowed));
  adminLink.tabIndex = allowed ? 0 : -1;
}
