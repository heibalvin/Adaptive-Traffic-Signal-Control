const socket = io();

let devices = {};
let selectedDeviceId = null;

// ── DOM elements ─────────────────────────────────────────────────
const devicesContainer = document.getElementById('devices-container');
const eventsList = document.getElementById('events-list');
const connectionStatus = document.getElementById('connection-status');
const addDeviceModal = document.getElementById('add-device-modal');
const addDeviceForm = document.getElementById('add-device-form');
const addDeviceBtn = document.getElementById('add-device-btn');
const cancelAddBtn = document.getElementById('cancel-add');
const refreshBtn = document.getElementById('refresh-btn');

// ── Connection ───────────────────────────────────────────────────
socket.on('connect', () => {
    connectionStatus.textContent = 'Connected';
    connectionStatus.className = 'status-connected';
});

socket.on('disconnect', () => {
    connectionStatus.textContent = 'Disconnected';
    connectionStatus.className = 'status-disconnected';
});

socket.on('traffic_event', (event) => {
    addEvent(event);
    if (event.device_id) {
        refreshDevice(event.device_id);
    }
});

// ── Device rendering ─────────────────────────────────────────────
function renderDevices() {
    devicesContainer.innerHTML = '';
    Object.values(devices).forEach(device => {
        devicesContainer.appendChild(createDeviceCard(device));
    });
}

function createDeviceCard(device) {
    const card = document.createElement('div');
    card.className = 'traffic-light-card';
    card.dataset.id = device.id;

    const colour = (device.colour || 'RED').toLowerCase();

    card.innerHTML = `
        <div class="card-header">
            <h3>${device.id}</h3>
            <button class="delete-btn" onclick="deleteDevice('${device.id}')">Delete</button>
        </div>
        <div class="light-display">
            <div class="light-circle ${colour}"></div>
        </div>
        <div class="card-info">
            <div>State: <strong>${device.state}</strong></div>
            <div>Colour: <strong>${device.colour}</strong></div>
            <div>Green: <strong>${device.green_timer}s</strong></div>
            <div>Orange: <strong>${device.orange_timer}s</strong></div>
            <div>Red: <strong>${device.red_timer}s</strong></div>
            <div>Updated: <strong>${new Date(device.updated_at * 1000).toLocaleTimeString()}</strong></div>
        </div>
    `;
    return card;
}

function refreshDevice(deviceId) {
    fetch(`/api/devices/${deviceId}`)
        .then(r => r.json())
        .then(device => {
            if (device.error) return;
            devices[device.id] = device;
            const card = document.querySelector(`.traffic-light-card[data-id="${device.id}"]`);
            if (card) {
                card.replaceWith(createDeviceCard(device));
            }
        });
}

// ── Events ───────────────────────────────────────────────────────
function addEvent(event) {
    const div = document.createElement('div');
    div.className = 'event-item';
    const time = new Date((event.timestamp || 0) * 1000).toLocaleTimeString();
    div.innerHTML = `<span class="timestamp">[${time}]</span> <span class="type">${event.type}</span> device=${event.device_id}`;
    eventsList.prepend(div);
    while (eventsList.children.length > 100) {
        eventsList.removeChild(eventsList.lastChild);
    }
}

// ── Actions ──────────────────────────────────────────────────────
async function loadDevices() {
    try {
        const res = await fetch('/api/devices');
        const data = await res.json();
        devices = {};
        data.forEach(d => devices[d.id] = d);
        renderDevices();
    } catch (e) {
        console.error('Failed to load devices:', e);
    }
}

function deleteDevice(deviceId) {
    if (!confirm(`Delete device ${deviceId}?`)) return;
    fetch(`/api/devices/${deviceId}`, { method: 'DELETE' })
        .then(() => loadDevices());
}

addDeviceBtn.addEventListener('click', () => addDeviceModal.classList.add('show'));
cancelAddBtn.addEventListener('click', () => addDeviceModal.classList.remove('show'));

addDeviceForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(addDeviceForm);
    const data = {
        id: formData.get('id') || undefined,
        greenTimer: parseInt(formData.get('greenTimer')),
        orangeTimer: parseInt(formData.get('orangeTimer')),
        redTimer: parseInt(formData.get('redTimer')),
    };
    await fetch('/api/devices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    addDeviceForm.reset();
    addDeviceModal.classList.remove('show');
    loadDevices();
});

refreshBtn.addEventListener('click', loadDevices);

// ── Init ─────────────────────────────────────────────────────────
loadDevices();