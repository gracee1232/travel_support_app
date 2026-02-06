/**
 * Travel Planner - Frontend Application
 * Toggle Form, Dual Views, Q&A, Suggestions, Pro Tips
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

// Required fields for progress tracking
const requiredFields = [
    'destinations', 'group_type', 'traveler_count',
    'trip_duration_days', 'start_date', 'end_date',
    'daily_start_time', 'daily_end_time', 'sightseeing_pace', 'travel_mode'
];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await initSession();
    setupEventListeners();
    updateFormProgress();
    setDefaultDates();
});

// Session Management
async function initSession() {
    try {
        const response = await fetch(`${API_BASE}/session`, { method: 'POST' });
        const data = await response.json();
        sessionId = data.session_id;
        console.log('Session created:', sessionId);
    } catch (error) {
        console.error('Failed to create session:', error);
        showError('Failed to connect to server. Please refresh.');
    }
}

// Event Listeners
function setupEventListeners() {
    // Form field changes
    form.addEventListener('input', () => {
        updateFormProgress();
        autoCalculateEndDate();
    });

    // Lock form button
    lockFormBtn.addEventListener('click', handleLockForm);

    // New session
    newSessionBtn.addEventListener('click', async () => {
        location.reload();
    });

    // Chat form
    chatForm.addEventListener('submit', handleChatSubmit);
}

// Toggle Section
function toggleSection(sectionName) {
    const section = document.querySelector(`[data-section="${sectionName}"]`);
    if (section) {
        section.classList.toggle('collapsed');
    }
}

// Make toggle function globally accessible
window.toggleSection = toggleSection;

// Set Default Dates
function setDefaultDates() {
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(today.getDate() + 7); // Week from now

    document.getElementById('start_date').value = startDate.toISOString().split('T')[0];
    autoCalculateEndDate();
}

// Auto Calculate End Date
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

// Update Form Progress
function updateFormProgress() {
    let filled = 0;

    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field && field.value && field.value.trim() !== '') {
            filled++;
        }
    });

    const progress = (filled / requiredFields.length) * 100;
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `${filled}/${requiredFields.length} fields`;

    // Enable/disable lock button
    lockFormBtn.disabled = filled < requiredFields.length;

    if (filled === requiredFields.length) {
        lockFormBtn.classList.add('ready');
        sessionStatus.textContent = 'Ready';
        sessionStatus.classList.add('ready');
    }
}

// Get Form Data
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
        max_travel_distance_km: parseFloat(document.getElementById('max_travel_distance_km').value) || 100,
        cab_pickup_required: document.getElementById('cab_pickup_required').checked,
        traffic_consideration: document.getElementById('traffic_consideration').checked
    };
}

// Handle Lock Form
async function handleLockForm() {
    if (lockFormBtn.disabled) return;

    const formData = getFormData();
    showLoading(true);

    try {
        // Submit and lock form
        const response = await fetch(`${API_BASE}/form/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            throw new Error('Failed to lock form');
        }

        formLocked = true;
        disableFormInputs();
        sessionStatus.textContent = 'Form Locked';
        sessionStatus.classList.add('locked');
        lockFormBtn.textContent = '✓ Form Locked';
        lockFormBtn.disabled = true;

        // Generate itinerary
        await generateItinerary();

    } catch (error) {
        console.error('Error:', error);
        showError('Failed to submit form. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Generate Itinerary
async function generateItinerary() {
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                message: 'generate itinerary'
            })
        });

        const data = await response.json();

        if (data.itinerary) {
            currentItinerary = data.itinerary;
            renderItinerary(data.itinerary);
            itineraryPanel.style.display = 'block';
        }

    } catch (error) {
        console.error('Failed to generate itinerary:', error);
        showError('Failed to generate itinerary. Please try again.');
    }
}

// Render Itinerary
function renderItinerary(itinerary) {
    // Summary
    const summary = document.getElementById('itinerary-summary');
    const totalDays = itinerary.days?.length || 0;
    const totalDistance = itinerary.total_distance_km ||
        itinerary.days?.reduce((sum, day) => sum + (day.total_distance_km || 0), 0) || 0;

    summary.innerHTML = `
        <h3>${itinerary.summary || 'Your Personalized Itinerary'}</h3>
        <div class="stats">
            <span>📅 ${totalDays} days</span>
            <span>📍 ${totalDistance.toFixed(1)} km total</span>
            <span>🎫 Version ${itinerary.version || 1}</span>
        </div>
    `;

    // Day-wise view
    renderDaywiseView(itinerary);

    // Hour-wise view
    renderHourwiseView(itinerary);

    // Suggestions
    renderSuggestions(itinerary);

    // Pro Tips
    renderProTips(itinerary);
}

// Render Day-wise View
function renderDaywiseView(itinerary) {
    const container = document.getElementById('daywise-content');

    if (!itinerary.days || itinerary.days.length === 0) {
        container.innerHTML = '<p class="empty-state">No days in itinerary</p>';
        return;
    }

    container.innerHTML = itinerary.days.map(day => {
        const activities = day.activities || [];
        const displayActivities = activities;
        const remainingCount = 0;

        return `
            <div class="day-card">
                <div class="day-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <h4>Day ${day.day_number} - ${day.date || ''}</h4>
                    <span class="day-theme">${day.theme || ''}</span>
                </div>
                <div class="day-activities">
                    ${displayActivities.map(act => `
                        <div class="activity-item">
                            <span class="activity-time">${act.time_slot || act.time || ''}</span>
                            <span class="activity-icon">${getActivityIcon(act.type || act.activity_type)}</span>
                            <div class="activity-details">
                                <div class="activity-location">${act.location || ''}</div>
                                <div class="activity-description">${act.description || ''}</div>
                            </div>
                        </div>
                    `).join('')}
                    ${remainingCount > 0 ? `<p class="more-activities">... and ${remainingCount} more activities</p>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// Render Hour-wise View
function renderHourwiseView(itinerary) {
    const container = document.getElementById('hourwise-content');

    if (!itinerary.days || itinerary.days.length === 0) {
        container.innerHTML = '<p class="empty-state">No activities to display</p>';
        return;
    }

    // Flatten all activities with day info
    let allActivities = [];
    itinerary.days.forEach(day => {
        (day.activities || []).forEach(act => {
            allActivities.push({
                ...act,
                dayNumber: day.day_number,
                date: day.date
            });
        });
    });

    container.innerHTML = `
        <div class="timeline">
            ${allActivities.map(act => `
                <div class="timeline-item">
                    <span class="time-tag">Day ${act.dayNumber} • ${act.time_slot || act.time || ''}</span>
                    <h5>${getActivityIcon(act.type || act.activity_type)} ${act.location || ''}</h5>
                    <p>${act.description || ''}</p>
                </div>
            `).join('')}
        </div>
    `;
}

// Render Suggestions
function renderSuggestions(itinerary) {
    const container = document.getElementById('suggestions-content');

    // Use backend-provided suggestions or fallback
    const suggestions = itinerary.suggestions && itinerary.suggestions.length > 0
        ? itinerary.suggestions
        : [
            { name: 'Local Cafe', type: 'cafe', desc: 'Find a cozy spot nearby', rating: '4.5' },
            { name: 'Relaxation', type: 'rest', desc: 'Take a break', rating: '4.8' }
        ];

    container.innerHTML = suggestions.map(s => `
        <div class="suggestion-item">
            <span class="suggestion-icon">${getSuggestionIcon(s.type)}</span>
            <div class="suggestion-details">
                <span class="suggestion-name">${s.name}</span>
                <span class="suggestion-desc">${s.desc}</span>
            </div>
            ${s.rating ? `<span class="suggestion-rating">⭐ ${s.rating}</span>` : ''}
        </div>
    `).join('');
}

// Render Pro Tips
function renderProTips(itinerary) {
    const container = document.getElementById('protips-content');

    // Use backend-provided pro tips
    const tips = itinerary.pro_tips && itinerary.pro_tips.length > 0
        ? itinerary.pro_tips
        : [
            'Book tickets in advance to skip lines.',
            'Keep water handy and stay hydrated.',
            'Check local weather before heading out.'
        ];

    container.innerHTML = tips.map(tip => `
        <div class="protip-item">
            <span class="protip-icon">💡</span>
            <span>${tip}</span>
        </div>
    `).join('');
}

// Get Suggestion Icon
function getSuggestionIcon(type) {
    const icons = {
        cafe: '☕',
        restaurant: '🍽️',
        nightlife: '🍹',
        relaxation: '💆',
        outdoor: '🌳',
        lounge: '🍸',
        food: '🥘'
    };
    return icons[type] || '✨';
}

// Switch View (Day-wise / Hour-wise)
function switchView(view) {
    const daywiseView = document.getElementById('daywise-view');
    const hourwiseView = document.getElementById('hourwise-view');
    const daywiseBtn = document.getElementById('view-daywise');
    const hourwiseBtn = document.getElementById('view-hourwise');

    if (view === 'daywise') {
        daywiseView.style.display = 'block';
        hourwiseView.style.display = 'none';
        daywiseBtn.classList.add('active');
        hourwiseBtn.classList.remove('active');
    } else {
        daywiseView.style.display = 'none';
        hourwiseView.style.display = 'block';
        daywiseBtn.classList.remove('active');
        hourwiseBtn.classList.add('active');
    }
}

// Make switch view globally accessible
window.switchView = switchView;

// Get Activity Icon
function getActivityIcon(type) {
    const icons = {
        sightseeing: '📍',
        meal: '🍽️',
        shopping: '🛍️',
        adventure: '🎢',
        cultural: '🏛️',
        checkin: '🏨',
        checkout: '🧳',
        rest: '☕',
        travel: '🚗'
    };
    return icons[type?.toLowerCase()] || '📍';
}

// Handle Chat Submit
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
            body: JSON.stringify({
                session_id: sessionId,
                message: message
            })
        });

        const data = await response.json();
        addChatMessage(data.message, 'assistant');

        if (data.itinerary) {
            currentItinerary = data.itinerary;
            renderItinerary(data.itinerary);
        }

    } catch (error) {
        console.error('Chat error:', error);
        addChatMessage('Sorry, something went wrong. Please try again.', 'assistant');
    }
}

// Ask Question (Quick Questions)
async function askQuestion(question) {
    chatInput.value = question;
    chatForm.dispatchEvent(new Event('submit'));
}

// Make askQuestion globally accessible
window.askQuestion = askQuestion;

// Modify Itinerary
async function modifyItinerary() {
    const input = document.getElementById('modify-input');
    const message = input.value.trim();
    if (!message) return;

    showLoading(true);

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                message: message
            })
        });

        const data = await response.json();

        if (data.itinerary) {
            currentItinerary = data.itinerary;
            renderItinerary(data.itinerary);
            input.value = '';

            // Show change summary in chat
            if (data.message) {
                addChatMessage(data.message, 'assistant');
            }
        }

    } catch (error) {
        console.error('Modification error:', error);
        showError('Failed to modify itinerary. Please try again.');
    } finally {
        showLoading(false);
    }
}

// Make modifyItinerary globally accessible
window.modifyItinerary = modifyItinerary;

// Add Chat Message
function addChatMessage(content, role) {
    // Remove welcome message if present
    const welcome = chatMessages.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${role}`;
    msgDiv.textContent = content;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Disable Form Inputs
function disableFormInputs() {
    form.querySelectorAll('input, select').forEach(el => {
        el.disabled = true;
    });

    // Collapse all sections except basic
    document.querySelectorAll('.toggle-section').forEach(section => {
        if (section.dataset.section !== 'basic') {
            section.classList.add('collapsed');
        }
    });
}

// Show Loading
function showLoading(show) {
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

// Show Error
function showError(message) {
    alert(message); // Simple for now, can be enhanced with a toast
}
