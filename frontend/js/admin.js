/**
 * AeroPark GOMA - Admin Functions
 * Admin-specific utilities
 */

const Admin = {
    // Format date for display
    formatDate(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleDateString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // Format money
    formatMoney(amount) {
        return (amount || 0).toLocaleString('fr-FR') + ' FC';
    },

    // Export data to CSV
    exportToCSV(data, filename) {
        if (!data || data.length === 0) return;

        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(h => '"' + (row[h] || '') + '"').join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
    },

    // Show notification
    showNotification(message, type) {
        type = type || 'success';
        
        const existing = document.querySelector('.admin-notification');
        if (existing) existing.remove();

        const notification = document.createElement('div');
        notification.className = 'admin-notification ' + type;
        notification.innerHTML = 
            '<i class="fas fa-' + (type === 'success' ? 'check-circle' : 'exclamation-triangle') + '"></i>' +
            '<span>' + message + '</span>' +
            '<button onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>';
        
        notification.style.cssText = 
            'position:fixed;bottom:2rem;right:2rem;padding:1rem 1.5rem;background:white;' +
            'border-radius:10px;box-shadow:0 5px 20px rgba(0,0,0,0.15);display:flex;' +
            'align-items:center;gap:0.75rem;z-index:10000;' +
            'border-left:4px solid ' + (type === 'success' ? '#10b981' : '#ef4444');

        document.body.appendChild(notification);

        setTimeout(function() { notification.remove(); }, 4000);
    },

    // Initialize sidebar
    initSidebar() {
        const sidebar = document.getElementById('sidebar');
        const sidebarToggle = document.getElementById('sidebar-toggle');
        const mobileToggle = document.getElementById('mobile-menu-toggle');
        const logoutBtn = document.getElementById('admin-logout');

        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', function() {
                sidebar.classList.toggle('collapsed');
            });
        }

        if (mobileToggle) {
            mobileToggle.addEventListener('click', function() {
                sidebar.classList.toggle('mobile-open');
            });
        }

        if (logoutBtn) {
            logoutBtn.addEventListener('click', function() {
                Auth.clear();
                window.location.href = 'login.html';
            });
        }

        // Set admin name
        const adminName = document.getElementById('admin-name');
        if (adminName) {
            const user = Auth.getUser();
            adminName.textContent = user?.name || 'Admin';
        }
    },

    // Check admin auth
    checkAuth() {
        if (!Auth.isLoggedIn() || !Auth.isAdmin()) {
            window.location.href = 'login.html';
            return false;
        }
        return true;
    }
};
