/**
 * app.js - Prestige School of Nursing
 * Master Frontend Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- 1. UTILITY: Toast Notification System ---
    const showToast = (message, type = 'info') => {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = 'ℹ️';
        if (type === 'error') icon = '⚠️';
        if (type === 'success') icon = '✅';

        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // Make showToast globally available if needed by inline scripts
    window.showToast = showToast;

    // --- 2. UTILITY: Spinner Overlay Setup ---
    const showSpinner = () => {
        let spinner = document.querySelector('.spinner-overlay');
        if (!spinner) {
            spinner = document.createElement('div');
            spinner.className = 'spinner-overlay';
            spinner.innerHTML = '<div class="spinner"></div>';
            document.body.appendChild(spinner);
        }
        spinner.classList.add('active');
    };

    const hideSpinner = () => {
        const spinner = document.querySelector('.spinner-overlay');
        if (spinner) spinner.classList.remove('active');
    };

    // --- 3. REGISTRATION FLOW (New JAMB Verification) ---
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            showSpinner();
            
            try {
                // FormData automatically captures jamb_no, email, and password from the form
                const formData = new FormData(registerForm);

                const response = await fetch('/register', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json().catch(() => ({}));
                
                if (response.ok) {
                    showToast(data.message || 'Registration successful!', 'success');
                    setTimeout(() => window.location.href = '/login', 2000); // Send to login on success
                } else {
                    showToast(data.detail || 'Registration failed. Check your JAMB number.', 'error');
                }
            } catch (error) {
                console.error('Registration error:', error);
                showToast('A network error occurred during registration.', 'error');
            } finally {
                hideSpinner();
            }
        });
    }

    // --- 4. LOGIN FLOW (The Traffic Cop) ---
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
                // Backend expects application/x-www-form-urlencoded format
                const formData = new URLSearchParams();
                formData.append('email', email); 
                formData.append('password', password);

                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: formData.toString()
                });

                if (response.ok) {
                    // Backend returns a flat object: {id, email, role}
                    const user = await response.json();
                    
                    // Store the user session in localStorage
                    localStorage.setItem('user', JSON.stringify(user));
                    
                    showToast('Login successful! Redirecting...', 'success');
                    
                    // --- THE TRAFFIC COP ROUTING ---
                    setTimeout(() => {
                        if (user.role && user.role.trim().toLowerCase() === 'admin') {
                            window.location.href = '/admin'; // Send ICT Admin here
                        } else {
                            window.location.href = '/dashboard'; // Send Students here
                        }
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

    // --- 5. ADMISSION APPLICATION FLOW ---
    const applyForm = document.getElementById('applyForm');
    if (applyForm) {
        applyForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Verify user is logged in before allowing submission
            const userString = localStorage.getItem('user');
            if (!userString) {
                showToast('Session expired. Please log in again.', 'error');
                setTimeout(() => window.location.href = '/login', 2000);
                return;
            }

            const user = JSON.parse(userString);
            showSpinner();
            
            try {
                // Grabs fullName, phoneNumber, stateOfOrigin, passport, results
                const formData = new FormData(applyForm);
                
                // Append the required userId from the stored session
                formData.append('userId', user.id);

                const response = await fetch('/apply', {
                    method: 'POST',
                    body: formData // Fetch sets multipart/form-data automatically
                });

                if (response.ok) {
                    showToast('Application submitted successfully!', 'success');
                    setTimeout(() => window.location.href = '/dashboard', 1500);
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    showToast(errorData.detail || 'Failed to submit application.', 'error');
                }
            } catch (error) {
                console.error('Apply error:', error);
                showToast('An error occurred uploading your application. Please try again.', 'error');
            } finally {
                hideSpinner();
            }
        });
    }
    
    // --- 6. FILE UPLOAD VISUAL FEEDBACK ---
    const fileInputs = document.querySelectorAll('.file-upload input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                const label = e.target.parentElement.querySelector('span') || e.target.parentElement;
                label.innerHTML = `Selected: <strong>${e.target.files[0].name}</strong>`;
            }
        });
    });
    // --- 7. ADMIN: CSV JAMB LIST UPLOAD ---
    const csvUploadForm = document.getElementById('csvUploadForm');
    if (csvUploadForm) {
        csvUploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            showSpinner();
            
            const formData = new FormData(csvUploadForm);
            
            try {
                const response = await fetch('/admin/import-jamb-list', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json().catch(() => ({}));
                
                if (response.ok) {
                    showToast(data.message || 'CSV Uploaded Successfully!', 'success');
                    csvUploadForm.reset(); // Clear the file input
                } else {
                    showToast(data.detail || 'Failed to upload CSV.', 'error');
                }
            } catch (error) {
                console.error('CSV Upload Error:', error);
                showToast('Network error while uploading CSV.', 'error');
            } finally {
                hideSpinner();
            }
        });
    }
});