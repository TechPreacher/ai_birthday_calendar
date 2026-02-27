// Global state
let token = null;
let birthdays = [];
let currentYear = new Date().getFullYear();
let editingBirthdayId = null;
let currentUser = null;
let allUsers = [];

// Month names
const MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    setupEventListeners();
    populateYearSelector();
    populateDaySelector();
});

function setupEventListeners() {
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('logoutBtn').addEventListener('click', handleLogout);
    document.getElementById('addBirthdayBtn').addEventListener('click', () => openBirthdayModal());
    document.getElementById('birthdayForm').addEventListener('submit', handleBirthdaySave);
    document.getElementById('deleteBirthdayBtn').addEventListener('click', handleBirthdayDelete);
    document.getElementById('yearSelector').addEventListener('change', handleYearChange);
    document.getElementById('todayBtn').addEventListener('click', goToToday);
    document.getElementById('settingsBtn').addEventListener('click', openSettingsModal);
    document.getElementById('bdayMonth').addEventListener('change', updateDayOptions);
    document.getElementById('emailEnabled').addEventListener('change', toggleEmailSettings);
    document.getElementById('aiEnabled').addEventListener('change', toggleAISettings);
    document.getElementById('createUserForm').addEventListener('submit', handleCreateUser);
    document.getElementById('changePasswordForm').addEventListener('submit', handleChangePassword);
    
    // Close modals on click outside
    window.onclick = function(event) {
        if (event.target.className === 'modal') {
            event.target.style.display = 'none';
        }
    };
}

// Auth functions
function checkAuth() {
    token = localStorage.getItem('token');
    if (token) {
        showApp();
        loadBirthdays();
    } else {
        showLogin();
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        
        const response = await fetch('/api/auth/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData
        });
        
        if (response.ok) {
            const data = await response.json();
            token = data.access_token;
            localStorage.setItem('token', token);
            showApp();
            loadBirthdays();
        } else {
            document.getElementById('loginError').textContent = 'Invalid username or password';
        }
    } catch (error) {
        document.getElementById('loginError').textContent = 'Login failed. Please try again.';
    }
}

function handleLogout() {
    token = null;
    localStorage.removeItem('token');
    showLogin();
}

function showLogin() {
    document.getElementById('loginScreen').style.display = 'block';
    document.getElementById('appScreen').style.display = 'none';
}

async function showApp() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appScreen').style.display = 'block';
    await loadCurrentUser();
    
    // Hide settings button for non-admin users
    if (currentUser && !currentUser.is_admin) {
        const settingsBtn = document.getElementById('settingsBtn');
        if (settingsBtn) {
            settingsBtn.style.display = 'none';
        }
    }
}

// Birthday functions
async function loadBirthdays() {
    try {
        const response = await fetch('/api/birthdays', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            birthdays = await response.json();
            renderCalendar();
        } else if (response.status === 401) {
            handleLogout();
        }
    } catch (error) {
        console.error('Failed to load birthdays:', error);
    }
}

function renderCalendar() {
    const calendar = document.getElementById('calendar');
    calendar.innerHTML = '';
    
    const today = new Date();
    const currentMonth = today.getMonth() + 1; // JavaScript months are 0-indexed
    const currentYearActual = today.getFullYear();
    
    // Find the next upcoming birthday
    const nextBirthday = findNextBirthday();
    
    for (let month = 1; month <= 12; month++) {
        const monthCard = document.createElement('div');
        monthCard.className = 'month-card';
        
        // Highlight current month if viewing current year
        if (month === currentMonth && currentYear === currentYearActual) {
            monthCard.classList.add('current-month');
        }
        
        const monthTitle = document.createElement('h3');
        monthTitle.textContent = MONTHS[month - 1];
        monthCard.appendChild(monthTitle);
        
        const monthBirthdays = birthdays
            .filter(b => b.month === month && b.day !== null)
            .sort((a, b) => a.day - b.day);
        
        if (monthBirthdays.length === 0) {
            const noBirthdays = document.createElement('div');
            noBirthdays.className = 'no-birthdays';
            noBirthdays.textContent = 'No birthdays this month';
            monthCard.appendChild(noBirthdays);
        } else {
            monthBirthdays.forEach(birthday => {
                const item = createBirthdayElement(birthday, nextBirthday);
                monthCard.appendChild(item);
            });
        }
        
        calendar.appendChild(monthCard);
    }
}

function createBirthdayElement(birthday, nextBirthday = null) {
    const item = document.createElement('div');
    item.className = 'birthday-item';
    
    // Check if this is the next upcoming birthday
    const isNextBirthday = nextBirthday && 
                          birthday.id === nextBirthday.id;
    
    if (isNextBirthday) {
        item.classList.add('next-birthday');
    }
    
    item.onclick = () => openBirthdayModal(birthday);
    
    const date = document.createElement('div');
    date.className = 'birthday-date';
    date.textContent = `${MONTHS[birthday.month - 1]} ${birthday.day}`;
    
    // Add "NEXT!" badge for upcoming birthday
    if (isNextBirthday) {
        const badge = document.createElement('span');
        badge.className = 'next-birthday-badge';
        badge.textContent = 'NEXT!';
        date.appendChild(badge);
    }
    
    item.appendChild(date);
    
    const name = document.createElement('div');
    name.className = 'birthday-name';
    name.textContent = birthday.name;
    item.appendChild(name);
    
    if (birthday.birth_year) {
        const age = currentYear - birthday.birth_year;
        const ageDiv = document.createElement('div');
        ageDiv.className = 'birthday-age';
        ageDiv.textContent = `Turns ${age} in ${currentYear}`;
        item.appendChild(ageDiv);
    }
    
    if (birthday.note) {
        const note = document.createElement('div');
        note.className = 'birthday-note';
        note.textContent = birthday.note;
        item.appendChild(note);
    }
    
    // Display contact type badge
    if (birthday.contact_type) {
        const contactBadge = document.createElement('div');
        contactBadge.className = 'contact-type-badge';
        contactBadge.className += birthday.contact_type === 'Business' ? ' contact-business' : ' contact-friend';
        contactBadge.textContent = birthday.contact_type === 'Business' ? '💼 Business' : '👤 Friend';
        item.appendChild(contactBadge);
    }
    
    return item;
}

// Modal functions
function openBirthdayModal(birthday = null) {
    const modal = document.getElementById('birthdayModal');
    const form = document.getElementById('birthdayForm');
    const deleteBtn = document.getElementById('deleteBirthdayBtn');
    
    form.reset();
    editingBirthdayId = null;
    
    if (birthday) {
        document.getElementById('modalTitle').textContent = 'Edit Birthday';
        document.getElementById('bdayName').value = birthday.name;
        document.getElementById('bdayMonth').value = birthday.month;
        updateDayOptions();
        document.getElementById('bdayDay').value = birthday.day;
        document.getElementById('bdayYear').value = birthday.birth_year || '';
        document.getElementById('bdayNote').value = birthday.note || '';
        document.getElementById('bdayContactType').value = birthday.contact_type || 'Friend';
        document.getElementById('editBirthdayId').value = birthday.id;
        editingBirthdayId = birthday.id;
        deleteBtn.style.display = 'inline-block';
    } else {
        document.getElementById('modalTitle').textContent = 'Add Birthday';
        deleteBtn.style.display = 'none';
    }
    
    modal.style.display = 'block';
}

function closeBirthdayModal() {
    document.getElementById('birthdayModal').style.display = 'none';
}

async function handleBirthdaySave(e) {
    e.preventDefault();
    
    const birthdayData = {
        name: document.getElementById('bdayName').value,
        month: parseInt(document.getElementById('bdayMonth').value),
        day: parseInt(document.getElementById('bdayDay').value),
        birth_year: document.getElementById('bdayYear').value ? parseInt(document.getElementById('bdayYear').value) : null,
        note: document.getElementById('bdayNote').value || null,
        contact_type: document.getElementById('bdayContactType').value
    };
    
    try {
        let response;
        if (editingBirthdayId) {
            response = await fetch(`/api/birthdays/${editingBirthdayId}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(birthdayData)
            });
        } else {
            response = await fetch('/api/birthdays', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(birthdayData)
            });
        }
        
        if (response.ok) {
            closeBirthdayModal();
            await loadBirthdays();
        } else {
            alert('Failed to save birthday');
        }
    } catch (error) {
        console.error('Failed to save birthday:', error);
        alert('Failed to save birthday');
    }
}

async function handleBirthdayDelete() {
    if (!editingBirthdayId || !confirm('Are you sure you want to delete this birthday?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/birthdays/${editingBirthdayId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            closeBirthdayModal();
            await loadBirthdays();
        } else {
            alert('Failed to delete birthday');
        }
    } catch (error) {
        console.error('Failed to delete birthday:', error);
        alert('Failed to delete birthday');
    }
}

// Year selector functions
function populateYearSelector() {
    const selector = document.getElementById('yearSelector');
    const startYear = 2020;
    const endYear = 2040;
    
    for (let year = startYear; year <= endYear; year++) {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        if (year === currentYear) {
            option.selected = true;
        }
        selector.appendChild(option);
    }
}

function handleYearChange(e) {
    currentYear = parseInt(e.target.value);
    renderCalendar();
}

function goToToday() {
    currentYear = new Date().getFullYear();
    document.getElementById('yearSelector').value = currentYear;
    renderCalendar();
}

// Day selector functions
function populateDaySelector() {
    const daySelect = document.getElementById('bdayDay');
    for (let day = 1; day <= 31; day++) {
        const option = document.createElement('option');
        option.value = day;
        option.textContent = day;
        daySelect.appendChild(option);
    }
}

function updateDayOptions() {
    const month = parseInt(document.getElementById('bdayMonth').value);
    const daySelect = document.getElementById('bdayDay');
    const currentDay = daySelect.value;
    
    // Days in each month (non-leap year)
    const daysInMonth = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    
    if (month) {
        const maxDay = daysInMonth[month - 1];
        daySelect.innerHTML = '<option value="">Day</option>';
        
        for (let day = 1; day <= maxDay; day++) {
            const option = document.createElement('option');
            option.value = day;
            option.textContent = day;
            if (day == currentDay) {
                option.selected = true;
            }
            daySelect.appendChild(option);
        }
    }
}

// Settings functions
async function openSettingsModal() {
    const modal = document.getElementById('settingsModal');
    
    // Load current user info to check admin status
    await loadCurrentUser();
    
    // Check if user is admin
    const isAdmin = currentUser && currentUser.is_admin;
    
    // Show/hide tabs based on admin status
    const emailTab = document.querySelector('.tab-button:nth-child(1)');
    const usersTab = document.querySelector('.tab-button:nth-child(2)');
    
    if (!isAdmin) {
        // Non-admin: show message and hide email tab
        if (emailTab) emailTab.style.display = 'none';
        if (usersTab) usersTab.style.display = 'none';
        
        // Show a message for non-admin users
        document.getElementById('emailTab').innerHTML = '<p style="color: #718096; padding: 20px;">Settings are only accessible to administrators.</p>';
        document.getElementById('usersTab').style.display = 'none';
        
        modal.style.display = 'block';
        return;
    }
    
    // Admin users: show all tabs and load settings
    if (emailTab) emailTab.style.display = 'inline-block';
    if (usersTab) usersTab.style.display = 'inline-block';
    
    try {
        const response = await fetch('/api/settings/email', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const settings = await response.json();
            
            // Just populate the existing form (don't rebuild HTML)
            document.getElementById('emailEnabled').checked = settings.enabled;
            document.getElementById('smtpServer').value = settings.smtp_server;
            document.getElementById('smtpPort').value = settings.smtp_port;
            document.getElementById('smtpUsername').value = settings.smtp_username;
            document.getElementById('smtpPassword').value = settings.smtp_password;
            document.getElementById('fromEmail').value = settings.from_email;
            document.getElementById('recipients').value = settings.recipients.join('\n');
            document.getElementById('reminderTime').value = settings.reminder_time;
            document.getElementById('testMode').checked = settings.test_mode;
            document.getElementById('aiEnabled').checked = settings.ai_enabled || false;
            document.getElementById('openaiApiKey').value = settings.openai_api_key || '';
            
            // Re-attach event listeners
            document.getElementById('emailEnabled').addEventListener('change', toggleEmailSettings);
            document.getElementById('aiEnabled').addEventListener('change', toggleAISettings);
            
            toggleEmailSettings();
            toggleAISettings();
            modal.style.display = 'block';
        } else if (response.status === 403) {
            alert('You must be an administrator to access settings.');
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
        alert('Failed to load settings');
    }
}

function closeSettingsModal() {
    document.getElementById('settingsModal').style.display = 'none';
}

function toggleEmailSettings() {
    const enabled = document.getElementById('emailEnabled').checked;
    document.getElementById('emailSettings').style.display = enabled ? 'block' : 'none';
}

function toggleAISettings() {
    const enabled = document.getElementById('aiEnabled').checked;
    document.getElementById('aiSettings').style.display = enabled ? 'block' : 'none';
}

async function saveSettings() {
    const settings = {
        enabled: document.getElementById('emailEnabled').checked,
        smtp_server: document.getElementById('smtpServer').value,
        smtp_port: parseInt(document.getElementById('smtpPort').value),
        smtp_username: document.getElementById('smtpUsername').value,
        smtp_password: document.getElementById('smtpPassword').value,
        from_email: document.getElementById('fromEmail').value,
        recipients: document.getElementById('recipients').value.split('\n').filter(r => r.trim()),
        reminder_time: document.getElementById('reminderTime').value,
        test_mode: document.getElementById('testMode').checked,
        ai_enabled: document.getElementById('aiEnabled').checked,
        openai_api_key: document.getElementById('openaiApiKey').value
    };
    
    try {
        const response = await fetch('/api/settings/email', {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            alert('Settings saved successfully');
            closeSettingsModal();
        } else {
            alert('Failed to save settings');
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings');
    }
}

async function testEmail() {
    try {
        const response = await fetch('/api/settings/email/test', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            alert('Test email triggered. Check your email!');
        } else {
            const error = await response.json();
            alert('Failed to send test email: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to test email:', error);
        alert('Failed to test email');
    }
}

async function testEmailWithAI() {
    try {
        // Show loading message
        const button = event.target;
        const originalText = button.textContent;
        button.textContent = '⏳ Generating AI content...';
        button.disabled = true;
        
        const response = await fetch('/api/settings/email/test-ai', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        button.textContent = originalText;
        button.disabled = false;
        
        if (response.ok) {
            const result = await response.json();
            alert(`AI test email sent!\n\nTested with: ${result.birthday_tested}\nDays until birthday: ${result.days_until}\n\nCheck your inbox for the AI-enhanced birthday reminder!`);
        } else {
            const error = await response.json();
            alert('Failed to send AI test email:\n' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to test AI email:', error);
        alert('Failed to test AI email: ' + error.message);
    }
}

function findNextBirthday() {
    if (birthdays.length === 0) return null;
    
    const today = new Date();
    const currentYear = today.getFullYear();
    const currentMonth = today.getMonth() + 1;
    const currentDay = today.getDate();
    
    let nextBirthday = null;
    let minDaysUntil = Infinity;
    
    birthdays.forEach(birthday => {
        // Skip birthdays without a day
        if (!birthday.day) return;
        
        // Calculate this year's occurrence
        let birthdayThisYear = new Date(currentYear, birthday.month - 1, birthday.day);
        let birthdayNextYear = new Date(currentYear + 1, birthday.month - 1, birthday.day);
        
        // Calculate days until birthday
        let daysUntil;
        if (birthdayThisYear >= today) {
            // Birthday hasn't happened yet this year
            daysUntil = Math.ceil((birthdayThisYear - today) / (1000 * 60 * 60 * 24));
        } else {
            // Birthday already happened, use next year
            daysUntil = Math.ceil((birthdayNextYear - today) / (1000 * 60 * 60 * 24));
        }
        
        // Find the minimum
        if (daysUntil < minDaysUntil) {
            minDaysUntil = daysUntil;
            nextBirthday = birthday;
        }
    });
    
    return nextBirthday;
}

// Settings tabs
function switchTab(tabName) {
    // Hide all tabs
    document.getElementById('emailTab').style.display = 'none';
    document.getElementById('usersTab').style.display = 'none';
    
    // Remove active class from all buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    if (tabName === 'email') {
        document.getElementById('emailTab').style.display = 'block';
        document.querySelectorAll('.tab-button')[0].classList.add('active');
    } else if (tabName === 'users') {
        document.getElementById('usersTab').style.display = 'block';
        document.querySelectorAll('.tab-button')[1].classList.add('active');
        loadUsers();
    }
}

// User management functions
async function loadCurrentUser() {
    try {
        const response = await fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            currentUser = await response.json();
        }
    } catch (error) {
        console.error('Failed to load current user:', error);
    }
}

async function loadUsers() {
    try {
        const response = await fetch('/api/auth/users', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            allUsers = await response.json();
            renderUsers();
        } else if (response.status === 403) {
            document.getElementById('usersList').innerHTML = '<p style="color: #e53e3e;">You must be an administrator to manage users.</p>';
        }
    } catch (error) {
        console.error('Failed to load users:', error);
        alert('Failed to load users');
    }
}

function renderUsers() {
    const usersList = document.getElementById('usersList');
    usersList.innerHTML = '';
    
    if (allUsers.length === 0) {
        usersList.innerHTML = '<p style="color: #a0aec0;">No users found.</p>';
        return;
    }
    
    allUsers.forEach(user => {
        const userItem = document.createElement('div');
        userItem.className = 'user-item';
        
        const userInfo = document.createElement('div');
        userInfo.className = 'user-info';
        
        const userName = document.createElement('div');
        userName.className = 'user-name';
        userName.textContent = user.username;
        if (user.is_admin) {
            const badge = document.createElement('span');
            badge.className = 'user-badge';
            badge.textContent = 'ADMIN';
            userName.appendChild(badge);
        }
        userInfo.appendChild(userName);
        
        const userRole = document.createElement('div');
        userRole.className = 'user-role';
        userRole.textContent = user.disabled ? 'Disabled' : 'Active';
        userInfo.appendChild(userRole);
        
        userItem.appendChild(userInfo);
        
        // Action buttons
        const actionsDiv = document.createElement('div');
        actionsDiv.style.display = 'flex';
        actionsDiv.style.gap = '10px';
        
        // Change password button (for all users)
        const changePasswordBtn = document.createElement('button');
        changePasswordBtn.className = 'btn-secondary';
        changePasswordBtn.textContent = '🔑 Change Password';
        changePasswordBtn.onclick = () => openChangePasswordModal(user.username);
        actionsDiv.appendChild(changePasswordBtn);
        
        // Delete button (only if not the current user)
        if (currentUser && user.username !== currentUser.username) {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-danger';
            deleteBtn.textContent = 'Delete';
            deleteBtn.onclick = () => deleteUser(user.username);
            actionsDiv.appendChild(deleteBtn);
        }
        
        userItem.appendChild(actionsDiv);
        usersList.appendChild(userItem);
    });
}

function openCreateUserModal() {
    document.getElementById('createUserModal').style.display = 'block';
    document.getElementById('createUserForm').reset();
}

function closeCreateUserModal() {
    document.getElementById('createUserModal').style.display = 'none';
}

async function handleCreateUser(e) {
    e.preventDefault();
    
    const userData = {
        username: document.getElementById('newUsername').value,
        password: document.getElementById('newPassword').value,
        is_admin: document.getElementById('newUserIsAdmin').checked
    };
    
    try {
        const response = await fetch('/api/auth/users', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        if (response.ok) {
            alert('User created successfully');
            closeCreateUserModal();
            await loadUsers();
        } else {
            const error = await response.json();
            alert('Failed to create user: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to create user:', error);
        alert('Failed to create user');
    }
}

function openChangePasswordModal(username) {
    document.getElementById('passwordChangeUsername').textContent = username;
    document.getElementById('passwordChangeUsernameHidden').value = username;
    document.getElementById('changePasswordForm').reset();
    document.getElementById('changePasswordModal').style.display = 'block';
}

function closeChangePasswordModal() {
    document.getElementById('changePasswordModal').style.display = 'none';
}

async function handleChangePassword(e) {
    e.preventDefault();
    
    const username = document.getElementById('passwordChangeUsernameHidden').value;
    const newPassword = document.getElementById('changePasswordInput').value;
    const confirmPassword = document.getElementById('confirmPasswordInput').value;
    
    if (newPassword !== confirmPassword) {
        alert('Passwords do not match!');
        return;
    }
    
    if (newPassword.length < 6) {
        alert('Password must be at least 6 characters');
        return;
    }
    
    try {
        const response = await fetch(`/api/auth/users/${username}/password`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ password: newPassword })
        });
        
        if (response.ok) {
            alert(`Password changed successfully for ${username}`);
            closeChangePasswordModal();
            
            // If changing own password, inform user they'll need to log in again
            if (currentUser && username === currentUser.username) {
                alert('You changed your own password. You will need to log in again.');
                handleLogout();
            }
        } else {
            const error = await response.json();
            alert('Failed to change password: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to change password:', error);
        alert('Failed to change password');
    }
}

async function deleteUser(username) {
    if (!confirm(`Are you sure you want to delete user "${username}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/auth/users/${username}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            alert('User deleted successfully');
            await loadUsers();
        } else {
            const error = await response.json();
            alert('Failed to delete user: ' + (error.detail || 'Unknown error'));
        }
    } catch (error) {
        console.error('Failed to delete user:', error);
        alert('Failed to delete user');
    }
}
