/* ===================================
   Modals — Dashboard & Installer Picker
   =================================== */

const dashboardModal = document.getElementById('dashboard-modal');
const btnDashboard   = document.getElementById('btn-dashboard');
const closeBtn       = document.querySelector('.close-btn');

// Dashboard Modal
if (btnDashboard) {
    btnDashboard.addEventListener('click', async () => {
        dashboardModal.style.display = 'block';
        const stats = await api.get_dashboard_stats();
        document.getElementById('stat-total').textContent = stats.total_transfers;
        document.getElementById('stat-success').textContent = stats.success_rate + '%';

        const logsList = document.getElementById('recent-logs');
        logsList.innerHTML = '';
        stats.recent_logs.forEach(log => {
            const li = document.createElement('li');
            li.style.cursor = 'pointer';
            li.style.padding = '8px 12px';
            li.style.borderRadius = '6px';
            li.style.margin = '4px 0';
            li.style.transition = 'background 0.2s';
            li.style.display = 'flex';
            li.style.justifyContent = 'space-between';
            
            li.addEventListener('mouseenter', () => {
                li.style.background = 'rgba(255, 255, 255, 0.05)';
            });
            li.addEventListener('mouseleave', () => {
                li.style.background = 'transparent';
            });
            
            const statusClass = log.status === 'Success' ? 'log-success' : 'log-error';
            li.innerHTML = `<span>${log.date} - <b>${log.profile}</b></span> <span class="${statusClass}">${log.status} (${log.duration})</span>`;
            
            li.addEventListener('click', () => {
                const detailModal = document.getElementById('log-detail-modal');
                if (!detailModal) return;
                
                let detailsObj = null;
                try {
                    if (log.details) {
                        detailsObj = JSON.parse(log.details);
                    }
                } catch(e) {}
                
                document.getElementById('log-detail-date').textContent = log.date;
                document.getElementById('log-detail-duration').textContent = log.duration;
                document.getElementById('log-detail-src').textContent = log.src || '--';
                document.getElementById('log-detail-dst').textContent = log.dst || '--';
                
                if (detailsObj) {
                    document.getElementById('log-detail-op-type').textContent = detailsObj.op_type || log.profile;
                    document.getElementById('log-detail-flow').textContent = detailsObj.disk_flow || '--';
                    document.getElementById('log-detail-size').textContent = detailsObj.total_size || '--';
                    document.getElementById('log-detail-speed').textContent = detailsObj.avg_speed || 'N/A';
                    
                    const errContainer = document.getElementById('log-detail-error-container');
                    const errMsg = document.getElementById('log-detail-error-msg');
                    if (detailsObj.error_msg) {
                        errContainer.style.display = 'flex';
                        errMsg.textContent = detailsObj.error_msg;
                    } else {
                        errContainer.style.display = 'none';
                    }
                } else {
                    document.getElementById('log-detail-op-type').textContent = log.profile === 'backup' ? 'Backup Rápido' : (log.profile === 'manual' ? 'Transferencia Manual' : `Instalación (${log.profile})`);
                    document.getElementById('log-detail-flow').textContent = 'Desconocido (Log Antiguo)';
                    document.getElementById('log-detail-size').textContent = 'Desconocido';
                    document.getElementById('log-detail-speed').textContent = 'N/A';
                    
                    const errContainer = document.getElementById('log-detail-error-container');
                    const errMsg = document.getElementById('log-detail-error-msg');
                    if (log.status !== 'Success' && log.details) {
                        errContainer.style.display = 'flex';
                        errMsg.textContent = log.details;
                    } else {
                        errContainer.style.display = 'none';
                    }
                }
                
                detailModal.style.display = 'block';
            });
            
            logsList.appendChild(li);
        });
    });
}

const logDetailModal = document.getElementById('log-detail-modal');
const closeLogDetail = document.getElementById('close-log-detail');

if (closeBtn) {
    closeBtn.addEventListener('click', () => {
        dashboardModal.style.display = 'none';
    });
}

if (closeLogDetail) {
    closeLogDetail.addEventListener('click', () => {
        if (logDetailModal) logDetailModal.style.display = 'none';
    });
}

// Cerrar modales al click en el fondo
window.addEventListener('click', (e) => {
    if (e.target === dashboardModal) dashboardModal.style.display = 'none';
    if (e.target === logDetailModal) {
        if (logDetailModal) logDetailModal.style.display = 'none';
    }
});

// Installer Picker — Función global llamada desde Python vía evaluate_js
window.show_installer_list = function(executables) {
    const modal = document.getElementById('installer-picker-modal');
    const list  = document.getElementById('installer-list');
    const closePicker = document.getElementById('close-installer-picker');

    list.innerHTML = '';
    executables.forEach(exePath => {
        const li = document.createElement('li');
        li.className = 'installer-list-item';

        const fileName = exePath.split('\\').pop();
        li.innerHTML = `
            <i class="ph ph-file-exe installer-icon"></i>
            <span class="installer-name" title="${exePath}">${fileName}</span>
            <i class="ph ph-arrow-right installer-arrow"></i>
        `;

        li.addEventListener('click', async () => {
            modal.style.display = 'none';
            await api.run_single_installer_as_admin(exePath);
        });

        list.appendChild(li);
    });

    modal.style.display = 'flex';

    closePicker.onclick = () => { modal.style.display = 'none'; };
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
    });
};
