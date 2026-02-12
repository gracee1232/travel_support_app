/**
 * Wanderlust AI - Premium Travel Platform
 * Dark Theme Frontend
 */

const API_BASE = '/api';

// State
let sessionId = null;
let currentItinerary = null;
let formLocked = false;

// DOM Elements
const form = document.getElementById('trip-form');
const lockFormBtn = document.getElementById('lock-form-btn');
const newSessionBtn = document.getElementById('new-session-btn');
const sessionStatus = document.getElementById('session-status');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const itineraryPanel = document.getElementById('itinerary-panel');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');

const requiredFields = [
    'destinations', 'traveler_count', 'trip_duration_days',
    'start_date', 'end_date'
];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await initSession();
    setupEventListeners();
    updateFormProgress();
    setDefaultDates();
});

// Session
async function initSession() {
    try {
        const response = await fetch(`${API_BASE}/session`, { method: 'POST' });
        const data = await response.json();
        sessionId = data.session_id;
    } catch (error) {
        console.error('Session init failed:', error);
        showError('Failed to connect to server. Please refresh.');
    }
}

// Events
function setupEventListeners() {
    form.addEventListener('input', () => {
        updateFormProgress();
        autoCalculateEndDate();
    });
    lockFormBtn.addEventListener('click', handleLockForm);
    newSessionBtn.addEventListener('click', () => location.reload());
    chatForm.addEventListener('submit', handleChatSubmit);
}

function toggleSection(sectionName) {
    const section = document.querySelector(`[data-section="${sectionName}"]`);
    if (section) {
        section.classList.toggle('collapsed');
        const icon = section.querySelector('.toggle-icon');
        if (icon) {
            icon.style.transform = section.classList.contains('collapsed') ? 'rotate(-90deg)' : 'rotate(0deg)';
        }
    }
}
window.toggleSection = toggleSection;

function setDefaultDates() {
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() + 7);
    const startInput = document.getElementById('start_date');
    if (startInput) startInput.value = startDate.toISOString().split('T')[0];
    autoCalculateEndDate();
}

function autoCalculateEndDate() {
    const startDate = document.getElementById('start_date').value;
    const duration = parseInt(document.getElementById('trip_duration_days').value) || 3;
    if (startDate) {
        const start = new Date(startDate);
        const end = new Date(start);
        end.setDate(start.getDate() + duration - 1);
        document.getElementById('end_date').value = end.toISOString().split('T')[0];
    }
}

function updateFormProgress() {
    let filled = 0;
    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field && field.value && field.value.trim() !== '') filled++;
    });

    const progress = (filled / requiredFields.length) * 100;
    if (progressFill) progressFill.style.width = `${progress}%`;
    if (progressText) progressText.textContent = `${filled}/${requiredFields.length} completed`;

    lockFormBtn.disabled = filled < requiredFields.length;
    if (filled === requiredFields.length) {
        lockFormBtn.classList.add('ready');
        sessionStatus.textContent = 'Ready to Plan';
        sessionStatus.classList.add('ready');
    }
}

function getFormData() {
    const destinations = document.getElementById('destinations').value.split(',').map(d => d.trim()).filter(d => d);
    return {
        destinations,
        group_type: document.getElementById('group_type').value,
        traveler_count: parseInt(document.getElementById('traveler_count').value) || 2,
        trip_duration_days: parseInt(document.getElementById('trip_duration_days').value) || 3,
        start_date: document.getElementById('start_date').value,
        end_date: document.getElementById('end_date').value,
        daily_start_time: document.getElementById('daily_start_time').value,
        daily_end_time: document.getElementById('daily_end_time').value,
        sightseeing_pace: document.getElementById('sightseeing_pace').value,
        travel_mode: document.getElementById('travel_mode').value,
        budget: document.getElementById('budget').value,
        max_travel_distance_km: 100,
        cab_pickup_required: document.getElementById('cab_pickup_required').checked,
        traffic_consideration: document.getElementById('traffic_consideration').checked
    };
}

async function handleLockForm() {
    if (lockFormBtn.disabled) return;
    const formData = getFormData();

    await showLoadingSequence([
        "Analyzing destination trends...",
        "Checking weather forecasts...",
        "Finding top-rated stays...",
        "Building your itinerary...",
        "Finalizing your trip plan..."
    ]);

    try {
        const response = await fetch(`${API_BASE}/form/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        if (!response.ok) throw new Error('Failed to lock form');

        formLocked = true;
        disableFormInputs();
        sessionStatus.textContent = 'Planning...';
        await generateItinerary();
        itineraryPanel.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to submit form. Please try again.');
        showLoading(false);
    }
}

async function showLoadingSequence(messages) {
    showLoading(true);
    for (const msg of messages) {
        loadingText.textContent = msg;
        await new Promise(r => setTimeout(r, 800));
    }
}

async function generateItinerary() {
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message: 'generate itinerary' })
        });
        const data = await response.json();
        if (data.itinerary) {
            currentItinerary = data.itinerary;
            renderItinerary(data.itinerary);
            itineraryPanel.style.display = 'block';
            showLoading(false);
            sessionStatus.textContent = 'Trip Ready';
        }
    } catch (error) {
        console.error('Failed to generate itinerary:', error);
        showLoading(false);
        showError('Failed to generate itinerary. Please try again.');
    }
}

// ===== RENDER ITINERARY =====

function renderItinerary(itinerary) {
    const summary = document.getElementById('itinerary-summary');
    const totalDays = itinerary.days?.length || 0;
    const firstCity = itinerary.days?.[0]?.activities?.[0]?.location || 'Your Destination';

    summary.innerHTML = `
        <h3>${itinerary.summary || 'Your Personalized Itinerary'}</h3>
        <div class="summary-stats">
            <div class="stat-item">
                <span class="stat-icon">${totalDays}</span>
                <span>Days</span>
            </div>
            <div class="stat-item">
                <span class="stat-icon">A</span>
                <span>${firstCity}</span>
            </div>
            <div class="stat-item">
                <span class="stat-icon">AI</span>
                <span>Custom Curated</span>
            </div>
        </div>
    `;

    renderHotels(itinerary);
    renderDaywiseView(itinerary);
    renderHourwiseView(itinerary);
    renderSuggestions(itinerary);
    renderProTips(itinerary);
}

// ===== HOTELS =====

function renderHotels(itinerary) {
    const container = document.getElementById('hotel-content');
    const panel = document.getElementById('hotel-panel');

    if (!itinerary.hotel_recommendations || itinerary.hotel_recommendations.length === 0) {
        panel.style.display = 'none';
        return;
    }

    panel.style.display = 'block';

    // Group by category
    const categories = { 'Budget': [], 'Mid-Range': [], 'Luxury': [] };
    itinerary.hotel_recommendations.forEach(h => {
        const rating = (h.rating || '').toLowerCase();
        if (rating.includes('budget') || rating.includes('economy')) categories['Budget'].push(h);
        else if (rating.includes('mid') || rating.includes('standard') || rating.includes('3') || rating.includes('4')) categories['Mid-Range'].push(h);
        else if (rating.includes('luxury') || rating.includes('premium') || rating.includes('5')) categories['Luxury'].push(h);
        else categories['Mid-Range'].push(h); // default
    });

    let html = '';
    for (const [category, hotels] of Object.entries(categories)) {
        if (hotels.length === 0) continue;
        const cls = category.toLowerCase().replace('-', '-');
        html += `<div class="hotel-category">
            <div class="category-label ${cls}">${category}</div>
            <div class="hotel-grid">
                ${hotels.map(h => {
            const badgeCls = category.toLowerCase().replace('-', '-');
            const img = `https://source.unsplash.com/400x200/?hotel,${category.toLowerCase()}&sig=${Math.random()}`;
            return `
                    <div class="hotel-card">
                        <div class="hotel-image-placeholder" style="background-image: url('${img}')">
                            <span class="hotel-badge ${badgeCls}">${category}</span>
                        </div>
                        <div class="hotel-content">
                            <h4>${h.name}</h4>
                            <div class="hotel-location">${h.location}</div>
                            <p class="hotel-desc">${h.description}</p>
                            <div class="hotel-price">${h.price_range || '---'}</div>
                        </div>
                    </div>`;
        }).join('')}
            </div>
        </div>`;
    }

    container.innerHTML = html;
}

// ===== DAY VIEW =====

function renderDaywiseView(itinerary) {
    const container = document.getElementById('daywise-content');
    if (!itinerary.days || itinerary.days.length === 0) {
        container.innerHTML = '<p class="text-muted">No days generated.</p>';
        return;
    }

    container.innerHTML = itinerary.days.map(day => {
        return `
            <div class="day-card">
                <div class="day-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <div>
                        <div class="day-number">Day ${day.day_number}</div>
                        <h4>${day.theme || 'Explore'}</h4>
                    </div>
                    <div class="day-meta">
                        <span>${day.date || ''}</span>
                        ${day.weather ? `<span class="weather-tag">${day.weather}</span>` : ''}
                    </div>
                </div>
                <div class="day-activities">
                    ${(day.activities || []).map(act => {
            const type = (act.type || act.activity_type || 'sightseeing').toLowerCase();
            return `
                        <div class="activity-item">
                            <div class="activity-time">${act.time_slot || act.time || ''}</div>
                            <div class="activity-dot ${type}"></div>
                            <div class="activity-card">
                                <div class="activity-type-tag ${type}">${formatType(type)}</div>
                                <div class="activity-title">${act.location}</div>
                                <p class="activity-desc">${act.description}</p>
                                ${act.duration_minutes ? `<div class="activity-duration">${act.duration_minutes} min</div>` : ''}
                            </div>
                        </div>`;
        }).join('')}
                </div>
            </div>`;
    }).join('');
}

function formatType(type) {
    const labels = {
        sightseeing: 'Sightseeing',
        meal: 'Dining',
        food: 'Dining',
        cultural: 'Culture',
        shopping: 'Shopping',
        adventure: 'Adventure',
        checkin: 'Check-in',
        checkout: 'Checkout',
        rest: 'Rest',
        travel: 'Transit',
        walk: 'Walking',
        nature: 'Nature'
    };
    return labels[type] || type.charAt(0).toUpperCase() + type.slice(1);
}

// ===== TIMELINE VIEW =====

function renderHourwiseView(itinerary) {
    const container = document.getElementById('hourwise-content');
    let allActivities = [];
    (itinerary.days || []).forEach(day => {
        (day.activities || []).forEach(act => {
            allActivities.push({ ...act, day: day.day_number });
        });
    });

    container.innerHTML = allActivities.map(act => {
        const type = (act.type || act.activity_type || 'sightseeing').toLowerCase();
        return `
        <div class="activity-item">
            <div class="activity-time">Day ${act.day}<br>${act.time_slot || act.time || ''}</div>
            <div class="activity-dot ${type}"></div>
            <div class="activity-card">
                <div class="activity-type-tag ${type}">${formatType(type)}</div>
                <div class="activity-title">${act.location}</div>
                <p class="activity-desc">${act.description}</p>
            </div>
        </div>`;
    }).join('');
}

// ===== SUGGESTIONS =====

function renderSuggestions(itinerary) {
    const container = document.getElementById('suggestions-content');
    const suggestions = itinerary.suggestions || [];
    if (suggestions.length === 0) {
        document.getElementById('suggestions-panel').style.display = 'none';
        return;
    }

    container.innerHTML = suggestions.map(s => `
        <div class="suggestion-item">
            <strong>${s.title || s.name || 'Recommendation'}</strong>
            <p>${s.description || s.desc || ''}</p>
        </div>
    `).join('');
}

// ===== PRO TIPS =====

function renderProTips(itinerary) {
    const container = document.getElementById('protips-content');
    const tips = itinerary.pro_tips || [];
    if (tips.length === 0) {
        document.getElementById('protips-panel').style.display = 'none';
        return;
    }

    container.innerHTML = tips.map(t => `
        <div class="protip-item">
            <span class="protip-bullet"></span>
            <span>${t}</span>
        </div>
    `).join('');
}

// ===== VIEW TOGGLE =====

function switchView(view) {
    document.getElementById('daywise-view').style.display = view === 'daywise' ? 'block' : 'none';
    document.getElementById('hourwise-view').style.display = view === 'hourwise' ? 'block' : 'none';
    document.getElementById('view-daywise').classList.toggle('active', view === 'daywise');
    document.getElementById('view-hourwise').classList.toggle('active', view === 'hourwise');
}
window.switchView = switchView;

function askQuestion(q) {
    chatInput.value = q;
    handleChatSubmit(new Event('submit'));
}
window.askQuestion = askQuestion;

// ===== CHAT =====

async function handleChatSubmit(e) {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    addChatMessage(message, 'user');
    chatInput.value = '';

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message })
        });
        const data = await response.json();
        addChatMessage(data.message, 'assistant');
        if (data.itinerary) renderItinerary(data.itinerary);
    } catch (error) {
        console.error(error);
        addChatMessage("Sorry, I encountered an error. Please try again.", 'assistant');
    }
}

function addChatMessage(content, role) {
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.textContent = content;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ===== UTILITIES =====

function disableFormInputs() {
    form.querySelectorAll('input, select, button').forEach(el => el.disabled = true);
    document.querySelectorAll('.form-section').forEach(s => s.classList.add('collapsed'));
}

function showLoading(show) {
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

function showError(msg) {
    alert(msg);
}
