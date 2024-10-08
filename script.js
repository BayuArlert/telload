document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM Content Loaded');

    const loginForm = document.getElementById('loginForm');
    const verifyForm = document.getElementById('verifyForm');
    const logoutButton = document.getElementById('logoutButton');
    const mainContent = document.getElementById('mainContent');
    const phoneNumberDisplay = document.getElementById('phoneNumberDisplay');

    console.log('Elements found:', {
        loginForm: !!loginForm,
        verifyForm: !!verifyForm,
        logoutButton: !!logoutButton,
        mainContent: !!mainContent,
        phoneNumberDisplay: !!phoneNumberDisplay
    });

    // Initially hide all sections except login form
    loginForm.style.display = 'block';
    verifyForm.style.display = 'none';
    logoutButton.style.display = 'none';
    mainContent.style.display = 'none';

    // Function to switch between forms
    function showVerifyForm() {
        console.log('Showing verify form');
        loginForm.style.display = 'none';
        verifyForm.style.display = 'block';
        logoutButton.style.display = 'none';
        mainContent.style.display = 'none';
    }

    // Event listener for login form
    loginForm.querySelector('button').addEventListener('click', async function (e) {
        console.log('Login button clicked');
        e.preventDefault();
        const phoneInput = loginForm.querySelector('input');
        const phoneNumber = phoneInput.value;

        if (!phoneNumber) {
            alert('Silakan masukkan nomor telepon');
            return;
        }

        try {
            console.log('Sending code to:', phoneNumber);
            const response = await fetch('http://localhost:5000/send_code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ phone_number: phoneNumber })
            });

            const data = await response.json();
            console.log('Server response:', data);

            if (response.ok) {
                alert(data.message || 'Kode verifikasi telah dikirim');
                showVerifyForm();
            } else {
                alert(data.message || 'Gagal mengirim kode verifikasi');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error saat mengirim kode: ' + error.message);
        }
    });

    // Event listener for verification form
    verifyForm.querySelector('button').addEventListener('click', async function (e) {
        console.log('Verify button clicked');
        e.preventDefault();
        const codeInput = verifyForm.querySelector('input');
        const code = codeInput.value;

        if (!code) {
            alert('Silakan masukkan kode verifikasi');
            return;
        }

        try {
            const response = await fetch('http://localhost:5000/verify_code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({ code: code })
            });

            const data = await response.json();
            console.log('Verify response:', data);

            if (response.ok && data.success) {
                alert('Verifikasi berhasil');
                checkAuthStatus();
            } else {
                alert(data.message || 'Verifikasi gagal');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error saat verifikasi: ' + error.message);
        }
    });

    // Event listener for logout button
    logoutButton.querySelector('button').addEventListener('click', async function () {
        try {
            const response = await fetch('http://localhost:5000/logout', {
                method: 'POST',
                credentials: 'include'
            });

            const data = await response.json();

            if (response.ok && data.success) {
                alert('Logout berhasil');
                checkAuthStatus();
            } else {
                alert(data.message || 'Logout gagal');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error saat logout: ' + error.message);
        }
    });

    // Function to check authentication status
    async function checkAuthStatus() {
        try {
            const response = await fetch('http://localhost:5000/check_auth', { credentials: 'include' });
            const data = await response.json();

            console.log('Auth status response', data);

            if (data.authenticated) {
                loginForm.style.display = 'none';
                verifyForm.style.display = 'none';
                logoutButton.style.display = 'block';
                mainContent.style.display = 'block';
                phoneNumberDisplay.textContent = data.phone_number;
            } else {
                loginForm.style.display = 'block';
                verifyForm.style.display = 'none';
                logoutButton.style.display = 'none';
                mainContent.style.display = 'none';
            }
        } catch (error) {
            console.error('Error saat memeriksa status autentikasi:', error);
        }
    }

    // Initial auth check
    checkAuthStatus();

});