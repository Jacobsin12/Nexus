/* ===================================
   App — Entry Point & Inicialización
   =================================== */

// Error handler global
window.addEventListener('error', function (e) {
    console.error("Error JS:", e.message);
});

/**
 * Splash Screen — Simula la carga de la app con progreso animado.
 */
function runSplashScreen() {
    return new Promise((resolve) => {
        const splash = document.getElementById('splash-screen');
        const progressBar = document.getElementById('splash-progress-bar');
        const appContainer = document.querySelector('.app-container');

        if (!splash || !progressBar) {
            if (appContainer) appContainer.classList.replace('app-hidden', 'app-visible');
            resolve();
            return;
        }

        let progress = 0;
        const steps = [
            { target: 25, speed: 40, label: 'Detectando discos' },
            { target: 50, speed: 35, label: 'Cargando perfiles' },
            { target: 75, speed: 30, label: 'Preparando motor' },
            { target: 95, speed: 50, label: 'Conectando interfaz' },
        ];

        const statusEl = splash.querySelector('.splash-status');
        let stepIndex = 0;

        function animateProgress() {
            if (stepIndex >= steps.length) {
                // Final burst to 100%
                progressBar.style.width = '100%';
                if (statusEl) statusEl.innerHTML = 'Listo<span class="splash-status-dots"></span>';

                setTimeout(() => {
                    splash.classList.add('fade-out');
                    setTimeout(() => {
                        splash.style.display = 'none';
                        if (appContainer) appContainer.classList.replace('app-hidden', 'app-visible');
                        resolve();
                    }, 600);
                }, 300);
                return;
            }

            const step = steps[stepIndex];
            if (statusEl) statusEl.innerHTML = step.label + '<span class="splash-status-dots"></span>';

            const interval = setInterval(() => {
                progress += 1;
                progressBar.style.width = progress + '%';

                if (progress >= step.target) {
                    clearInterval(interval);
                    stepIndex++;
                    setTimeout(animateProgress, 150);
                }
            }, step.speed);
        }

        // Pequeña pausa inicial para que las animaciones de reveal se vean
        setTimeout(animateProgress, 500);
    });
}

/**
 * Obtiene el nombre del dispositivo desde el backend y lo muestra en el menú.
 */
async function loadSystemInfo() {
    const sysInfo = await api.get_system_info();
    const deviceNameEl = document.getElementById('device-name');
    if (deviceNameEl && sysInfo && sysInfo.hostname) {
        deviceNameEl.textContent = sysInfo.hostname;
        deviceNameEl.title = `Usuario: ${sysInfo.username} (${sysInfo.user_profile})`;
        
        const card = document.getElementById('device-info-card');
        if (card) {
            card.addEventListener('click', () => {
                navigator.clipboard.writeText(sysInfo.hostname).then(() => {
                    showToast(`Nombre del equipo (${sysInfo.hostname}) copiado al portapapeles.`, 'success');
                }).catch(err => {
                    console.error('Error al copiar al portapapeles:', err);
                    showToast('No se pudo copiar automáticamente.', 'error');
                });
            });
        }
    }
}

// Inicialización al cargar el DOM
window.addEventListener('DOMContentLoaded', async () => {
    await runSplashScreen();
    loadSystemInfo().catch(e => console.error("Error loadSystemInfo:", e));
    loadDisks();
    loadProfiles().catch(e => console.error("Error loadProfiles:", e));

    // Consola maximizable al dar click en cabecera o botón
    const btnMaximizeConsole = document.getElementById('btn-maximize-console');
    const consoleSection = document.querySelector('.console-section');
    const consoleHeader = document.querySelector('.console-header');
    
    function toggleConsoleMaximize(e) {
        if (e.target.closest('button') && e.target.closest('button') !== btnMaximizeConsole) {
            return;
        }
        consoleSection.classList.toggle('maximized');
        const icon = btnMaximizeConsole.querySelector('i');
        if (consoleSection.classList.contains('maximized')) {
            icon.className = 'ph ph-corners-in';
            btnMaximizeConsole.title = "Restaurar Consola";
        } else {
            icon.className = 'ph ph-corners-out';
            btnMaximizeConsole.title = "Maximizar Consola";
        }
    }
    
    if (btnMaximizeConsole && consoleSection) {
        btnMaximizeConsole.addEventListener('click', toggleConsoleMaximize);
    }
    if (consoleHeader && consoleSection) {
        consoleHeader.addEventListener('click', toggleConsoleMaximize);
        consoleHeader.style.cursor = 'pointer';
        consoleHeader.title = "Clic en el encabezado para maximizar o restaurar la consola";
    }
});
