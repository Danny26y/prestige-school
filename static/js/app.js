/**
 * app.js - Prestige School of Health Benue
 * Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Toast Notification System
    const createToastContainer = () => {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    };

    window.showToast = (message, type = 'info') => {
        const container = createToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = 'ℹ️';
        if (type === 'error') icon = '⚠️';
        if (type === 'success') icon = '✅';

        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);

        // Animate in
        setTimeout(() => toast.classList.add('show'), 10);

        // Remove after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // 2. Spinner Overlay Setup
    const createSpinner = () => {
        let spinner = document.querySelector('.spinner-overlay');
        if (!spinner) {
            spinner = document.createElement('div');
            spinner.className = 'spinner-overlay';
            spinner.innerHTML = '<div class="spinner"></div>';
            document.body.appendChild(spinner);
        }
        return spinner;
    };

    window.showSpinner = () => {
        const spinner = createSpinner();
        spinner.classList.add('active');
    };

    window.hideSpinner = () => {
        const spinner = createSpinner();
        spinner.classList.remove('active');
    };

    // 3. Login Form Handling
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            
            if (!email || !password) {
                showToast('Please enter both email and password', 'error');
                return;
            }

            showSpinner();
            
            try {
                // Application/x-www-form-urlencoded format
                const formData = new URLSearchParams();
                formData.append('username', email); // Assuming standard OAuth2/FastAPI naming or mapping
                formData.append('password', password);

                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: formData.toString()
                });

                if (response.ok) {
                    const data = await response.json();
                    // Store user data in localStorage
                    if (data.user) {
                        localStorage.setItem('user', JSON.stringify(data.user));
                    }
                    if (data.access_token) {
                        localStorage.setItem('token', data.access_token);
                    }
                    
                    showToast('Login successful! Redirecting...', 'success');
                    
                    // Redirect to dashboard (assuming backend handles redirect or frontend does it based on response)
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/dashboard';
                    }, 1000);
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    showToast(errorData.detail || 'Invalid Credentials', 'error');
                }
            } catch (error) {
                console.error('Login error:', error);
                showToast('A network error occurred. Please try again.', 'error');
            } finally {
                hideSpinner();
            }
        });
    }

    // 4. Admission Apply Form Handling
    const applyForm = document.getElementById('applyForm');
    if (applyForm) {
        applyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            showSpinner();
            
            try {
                // Fetch automatically sets Content-Type to multipart/form-data when passing FormData
                const formData = new FormData(applyForm);
                
                // Add Authorization header if a token exists
                const token = localStorage.getItem('token');
                const headers = {};
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
                }

                const response = await fetch('/apply', {
                    method: 'POST',
                    headers: headers,
                    body: formData
                });

                if (response.ok) {
                    showToast('Application submitted successfully!', 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1500);
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    showToast(errorData.detail || 'Failed to submit application. Ensure all fields are valid.', 'error');
                }
            } catch (error) {
                console.error('Apply error:', error);
                showToast('An error occurred uploading your application. Please try again.', 'error');
            } finally {
                hideSpinner();
            }
        });
    }
    
    // File inputs display name when selected
    const fileInputs = document.querySelectorAll('.file-upload input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const label = e.target.parentElement.querySelector('span') || e.target.parentElement;
                label.innerHTML = `Selected: <strong>${e.target.files[0].name}</strong>`;
            }
        });
    });
});
