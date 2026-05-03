document.addEventListener('DOMContentLoaded', () => {
    loadAccounts();
    loadCattle();
    document.getElementById('accountForm')?.addEventListener('submit', event => {
        event.preventDefault();
        addAccount();
    });
    document.getElementById('cattleForm')?.addEventListener('submit', event => {
        event.preventDefault();
        addCattle();
    });
});

async function loadAccounts() {
    const response = await fetch('/api/admin/accounts');
    const data = await response.json();
    renderAccounts(data.accounts || []);
}

async function loadCattle() {
    const response = await fetch('/api/admin/cattle');
    const data = await response.json();
    renderCattleList(data.data || []);
}

function renderAccounts(accounts) {
    const tbody = document.getElementById('account_list');
    if (!tbody) return;
    tbody.innerHTML = '';
    accounts.forEach(account => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${account.userid}</td>
            <td>${account.name}</td>
            <td>${account.permit}</td>
            <td><button type="button" onclick="removeAccount('${account.userid}')">삭제</button></td>
        `;
        tbody.appendChild(tr);
    });
}

async function addAccount() {
    const userid = document.getElementById('accountId')?.value.trim();
    const name = document.getElementById('accountName')?.value.trim();
    const password = document.getElementById('accountPassword')?.value.trim();
    const permit = document.getElementById('accountPermit')?.value;

    if (!userid || !name || !password) {
        alert('아이디, 이름, 비밀번호는 필수입니다.');
        return;
    }

    const response = await fetch('/api/admin/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userid, name, password, permit })
    });
    const result = await response.json();
    if (!result.success) {
        alert(result.message || '추가에 실패했습니다.');
        return;
    }

    document.getElementById('accountForm')?.reset();
    loadAccounts();
}

function renderCattleList(items) {
    const tbody = document.getElementById('cattle_list');
    if (!tbody) return;
    tbody.innerHTML = '';
    items.forEach(cattle => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${cattle.id}</td>
            <td>${cattle.name}</td>
            <td>${cattle.owner}</td>
            <td>${cattle.note}</td>
            <td><button type="button" onclick="removeCattle('${cattle.id}')">삭제</button></td>
        `;
        tbody.appendChild(tr);
    });
}

async function addCattle() {
    const id = document.getElementById('cattleId')?.value.trim();
    const name = document.getElementById('cattleName')?.value.trim();
    const owner = document.getElementById('ownerName')?.value.trim();
    const note = document.getElementById('note')?.value.trim();

    if (!id || !name || !owner) {
        alert('소 ID, 이름, 소유자는 필수입니다.');
        return;
    }

    const response = await fetch('/api/admin/cattle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cattleId: id, name, owner, note })
    });
    const result = await response.json();
    if (!result.success) {
        alert(result.message || '추가에 실패했습니다.');
        return;
    }

    document.getElementById('cattleForm')?.reset();
    loadCattle();
}

async function removeAccount(userid) {
    const response = await fetch(`/api/admin/accounts/${userid}`, {
        method: 'DELETE'
    });
    const result = await response.json();
    if (!result.success) {
        alert(result.message || '삭제에 실패했습니다.');
        return;
    }
    loadAccounts();
}

async function removeCattle(cattleId) {
    const response = await fetch('/api/admin/cattle', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cattleId })
    });
    const result = await response.json();
    if (!result.success) {
        alert(result.message || '삭제에 실패했습니다.');
        return;
    }
    loadCattle();
}