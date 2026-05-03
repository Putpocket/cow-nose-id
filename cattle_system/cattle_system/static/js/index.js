const cattleData = window.cattleData || [];
const recentAddedData = window.recentAddedData || [];

document.addEventListener('DOMContentLoaded', () => {
    renderCattleList(cattleData);
    renderRecentData(recentAddedData);
    document.getElementById('applyPacketFilter')?.addEventListener('click', applyCattleFilter);
    document.getElementById('applyEventFilter')?.addEventListener('click', applyRecentFilter);
});

function renderCattleList(data) {
    const container = document.getElementById('packet_data');
    if (!container) return;
    container.innerHTML = '';
    data.forEach(item => {
        const row = document.createElement('div');
        row.className = 'packet-row';
        row.append(
            createCell(item.id),
            createCell(item.name),
            createCell(item.status),
            createCell(item.confidence),
            createCell(item.timestamp)
        );
        container.appendChild(row);
    });
}

function renderRecentData(data) {
    const container = document.getElementById('event_data');
    if (!container) return;
    container.innerHTML = '';
    data.forEach(item => {
        const row = document.createElement('div');
        row.className = 'event-row';
        row.append(
            createCell(item.timestamp),
            createCell(item.id),
            createCell(item.name),
            createCell(item.owner),
            createCell(item.note)
        );
        container.appendChild(row);
    });
}

function createCell(text) {
    const cell = document.createElement('div');
    cell.className = 'packet-cell';
    cell.textContent = text ?? '';
    return cell;
}

function applyCattleFilter() {
    const filterText = document.getElementById('packetFilter')?.value.trim().toUpperCase() || '';
    document.querySelectorAll('#packet_data .packet-row').forEach(row => {
        row.style.display = row.innerText.toUpperCase().includes(filterText) ? 'flex' : 'none';
    });
}

function applyRecentFilter() {
    const filterText = document.getElementById('eventFilter')?.value.trim().toUpperCase() || '';
    document.querySelectorAll('#event_data .event-row').forEach(row => {
        row.style.display = row.innerText.toUpperCase().includes(filterText) ? 'flex' : 'none';
    });
}