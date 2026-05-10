document.addEventListener('DOMContentLoaded', async () => {
  const user = await requireAdmin();
  if (!user) return;

  renderUser(user);
  bindForms();
  await Promise.all([loadAccounts(), loadCows()]);
});

async function requireAdmin() {
  try {
    const response = await fetch('/auth/me');
    if (response.status === 401) {
      window.location.href = '/login';
      return null;
    }
    if (!response.ok) {
      window.location.href = '/block';
      return null;
    }
    const user = await response.json();
    if (!isAdmin(user.role)) {
      window.location.href = '/block';
      return null;
    }
    return user;
  } catch (_error) {
    window.location.href = '/block';
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

function bindForms() {
  document.getElementById('accountForm')?.addEventListener('submit', event => {
    event.preventDefault();
    addAccount();
  });
  document.getElementById('cowForm')?.addEventListener('submit', event => {
    event.preventDefault();
    saveCow();
  });
  document.getElementById('resetCowForm')?.addEventListener('click', resetCowForm);
  document.getElementById('logoutButton')?.addEventListener('click', logout);
}

async function loadAccounts() {
  const data = await apiJson('/admin/accounts', { messageId: 'accountMessage' });
  renderAccounts(data?.accounts || []);
}

async function loadCows() {
  const data = await apiJson('/admin/cows', { messageId: 'cowMessage' });
  renderCows(data?.cows || []);
}

function renderAccounts(accounts) {
  const tbody = document.getElementById('accountList');
  if (!tbody) return;
  tbody.innerHTML = '';
  accounts.forEach(account => {
    const tr = document.createElement('tr');
    appendCell(tr, account.user_id);
    appendCell(tr, account.username);
    appendCell(tr, account.role);
    appendCell(tr, account.status);
    const action = document.createElement('td');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = '삭제';
    button.addEventListener('click', () => removeAccount(account.user_id));
    action.appendChild(button);
    tr.appendChild(action);
    tbody.appendChild(tr);
  });
}

async function addAccount() {
  const username = document.getElementById('accountUsername')?.value.trim();
  const password = document.getElementById('accountPassword')?.value;
  const role = document.getElementById('accountRole')?.value;

  if (!username || !password || !role) {
    showMessage('accountMessage', '아이디, 비밀번호, 권한은 필수입니다.', true);
    return;
  }

  const result = await apiJson('/admin/accounts', {
    method: 'POST',
    messageId: 'accountMessage',
    body: { username, password, role }
  });

  if (!result) return;
  document.getElementById('accountForm')?.reset();
  showMessage('accountMessage', '계정을 생성했습니다.');
  loadAccounts();
}

async function removeAccount(userId) {
  const result = await apiJson(`/admin/accounts/${userId}`, {
    method: 'DELETE',
    messageId: 'accountMessage'
  });
  if (!result) return;
  showMessage('accountMessage', '계정을 삭제했습니다.');
  loadAccounts();
}

function renderCows(cows) {
  const tbody = document.getElementById('cowList');
  if (!tbody) return;
  tbody.innerHTML = '';
  cows.forEach(cow => {
    const tr = document.createElement('tr');
    appendCell(tr, cow.cow_id);
    appendCell(tr, cow.ear_tag);
    appendCell(tr, cow.name);
    appendCell(tr, cow.owner_name);
    appendCell(tr, cow.notes);
    const action = document.createElement('td');
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.textContent = '수정';
    edit.addEventListener('click', () => fillCowForm(cow));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = '삭제';
    remove.addEventListener('click', () => removeCow(cow.cow_id));
    action.append(edit, remove);
    tr.appendChild(action);
    tbody.appendChild(tr);
  });
}

async function saveCow() {
  const cowId = document.getElementById('cowId')?.value;
  const payload = {
    name: document.getElementById('cowName')?.value.trim(),
    ear_tag: document.getElementById('earTag')?.value.trim(),
    owner_name: document.getElementById('ownerName')?.value.trim(),
    breed: document.getElementById('breed')?.value.trim(),
    sex: document.getElementById('sex')?.value.trim(),
    birth_date: document.getElementById('birthDate')?.value,
    notes: document.getElementById('notes')?.value.trim()
  };

  if (!payload.ear_tag) {
    showMessage('cowMessage', '이표 번호는 필수입니다.', true);
    return;
  }

  const result = await apiJson(cowId ? `/admin/cows/${cowId}` : '/admin/cows', {
    method: cowId ? 'PUT' : 'POST',
    messageId: 'cowMessage',
    body: payload
  });

  if (!result) return;
  resetCowForm();
  showMessage('cowMessage', '소 정보를 저장했습니다.');
  loadCows();
}

function fillCowForm(cow) {
  setValue('cowId', cow.cow_id);
  setValue('cowName', cow.name);
  setValue('earTag', cow.ear_tag);
  setValue('ownerName', cow.owner_name);
  setValue('breed', cow.breed);
  setValue('sex', cow.sex);
  setValue('birthDate', cow.birth_date);
  setValue('notes', cow.notes);
}

function resetCowForm() {
  document.getElementById('cowForm')?.reset();
  setValue('cowId', '');
}

async function removeCow(cowId) {
  const result = await apiJson(`/admin/cows/${cowId}`, {
    method: 'DELETE',
    messageId: 'cowMessage'
  });
  if (!result) return;
  showMessage('cowMessage', '소 정보를 삭제했습니다.');
  loadCows();
}

async function apiJson(url, options = {}) {
  const fetchOptions = {
    method: options.method || 'GET',
    headers: {}
  };
  if (options.body) {
    fetchOptions.headers['Content-Type'] = 'application/json';
    fetchOptions.body = JSON.stringify(options.body);
  }

  try {
    const response = await fetch(url, fetchOptions);
    if (response.status === 401) {
      window.location.href = '/login';
      return null;
    }
    if (response.status === 403) {
      window.location.href = '/block';
      return null;
    }
    const data = await response.json();
    if (!response.ok || data.success === false) {
      showMessage(options.messageId, data.error || data.message || '요청에 실패했습니다.', true);
      return null;
    }
    return data;
  } catch (_error) {
    showMessage(options.messageId, '서버에 연결할 수 없습니다.', true);
    return null;
  }
}

function appendCell(row, value) {
  const cell = document.createElement('td');
  cell.textContent = value ?? '-';
  row.appendChild(cell);
}

function setValue(id, value) {
  const element = document.getElementById(id);
  if (element) element.value = value ?? '';
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
