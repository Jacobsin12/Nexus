/* ===================================
   Transfer — Lógica de transferencia
   =================================== */

const inputDest      = document.getElementById('input-dest');
const btnDest        = document.getElementById('btn-dest');
const btnStart       = document.getElementById('btn-start');
const btnCancel      = document.getElementById('btn-cancel');
const consoleOutput  = document.getElementById('console-output');
const statusDot      = document.getElementById('status-dot');
const statusText     = document.getElementById('status-text');
const adminActionContainer = document.getElementById('admin-action-container');

// Elementos del Modal ETA
const etaConfirmModal = document.getElementById('eta-confirm-modal');
const btnEtaConfirm   = document.getElementById('btn-eta-confirm');
const btnEtaCancel    = document.getElementById('btn-eta-cancel');
const etaSizeText     = document.getElementById('eta-size');
const etaTimeText     = document.getElementById('eta-time');

let pendingTransfer = null;

// Seleccionar carpeta destino
btnDest.addEventListener('click', async () => {
    const folder = await api.select_folder();
    if (folder) inputDest.value = folder;
});

// Seleccionar carpeta origen (modo auto)
btnSource.addEventListener('click', async () => {
    const folder = await api.select_folder();
    if (folder) inputSource.value = folder;
});

// Iniciar transferencia
btnStart.addEventListener('click', async () => {
    let src;
    const dest = inputDest.value;

    if (currentMode === 'manual') {
        if (manualItems.length === 0) {
            showToast("Por favor añade al menos un archivo o carpeta.", 'error');
            return;
        }
        if (!dest) {
            showToast("Por favor selecciona la carpeta de destino.", 'error');
            return;
        }
        src = manualItems;

        // Calcular ETA antes de transferir
        btnStart.disabled = true;
        btnStart.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Calculando...';

        const etaResult = await api.calculate_transfer_eta(src, dest);

        btnStart.disabled = false;
        btnStart.innerHTML = '<i class="ph ph-rocket-launch"></i> Iniciar Transferencia';

        if (!etaResult.success) {
            showToast(etaResult.message, 'error');
            return;
        }

        // Mostrar Modal ETA
        etaSizeText.textContent = etaResult.size_str;
        etaTimeText.textContent = etaResult.eta_str;
        pendingTransfer = { profile: "manual", src: src, dest: dest };
        etaConfirmModal.style.display = 'block';

    } else if (currentMode === 'backup') {
        const checkedCheckboxes = document.querySelectorAll('.backup-folder-checkbox:checked');
        if (checkedCheckboxes.length === 0) {
            showToast("Por favor selecciona al menos una carpeta para respaldar.", 'error');
            return;
        }
        if (!dest) {
            showToast("Por favor selecciona la carpeta de destino.", 'error');
            return;
        }
        src = Array.from(checkedCheckboxes).map(cb => cb.value);

        // Calcular ETA antes de transferir
        btnStart.disabled = true;
        btnStart.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Calculando...';

        const etaResult = await api.calculate_transfer_eta(src, dest);

        btnStart.disabled = false;
        btnStart.innerHTML = '<i class="ph ph-rocket-launch"></i> Iniciar Transferencia';

        if (!etaResult.success) {
            showToast(etaResult.message, 'error');
            return;
        }

        // Mostrar Modal ETA
        etaSizeText.textContent = etaResult.size_str;
        etaTimeText.textContent = etaResult.eta_str;
        pendingTransfer = { profile: "backup", src: src, dest: dest };
        etaConfirmModal.style.display = 'block';

    } else {
        src = inputSource.value;
        if (!src || !dest) {
            showToast("Por favor selecciona origen y destino.", 'error');
            return;
        }
        if (src === dest) {
            showToast("El origen y el destino no pueden ser los mismos.", 'error');
            return;
        }
        executeTransferPhase(profileSelect.value, src, dest);
    }
});

// Botones del Modal ETA
if (btnEtaCancel) {
    btnEtaCancel.addEventListener('click', () => {
        etaConfirmModal.style.display = 'none';
        pendingTransfer = null;
    });
}

if (btnEtaConfirm) {
    btnEtaConfirm.addEventListener('click', () => {
        etaConfirmModal.style.display = 'none';
        if (pendingTransfer) {
            executeTransferPhase(pendingTransfer.profile, pendingTransfer.src, pendingTransfer.dest);
            pendingTransfer = null;
        }
    });
}

/**
 * Ejecuta la fase de transferencia: actualiza UI y llama al backend.
 */
async function executeTransferPhase(profile, src, dest) {
    // Actualizar estado UI
    btnStart.style.display = 'none';
    btnCancel.style.display = 'flex';
    statusDot.className = 'dot active';
    statusText.textContent = 'Transfiriendo';
    consoleOutput.innerHTML = '';

    // Reset y mostrar barra de progreso
    const progressContainer = document.getElementById('transfer-progress-container');
    const progressBar     = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const progressSpeed   = document.getElementById('progress-speed');
    const progressEta     = document.getElementById('progress-eta');

    if (progressContainer) progressContainer.style.display = 'flex';
    if (progressBar) {
        progressBar.style.width = '0%';
    }
    if (progressPercent) progressPercent.textContent = '0%';
    if (progressSpeed) progressSpeed.innerHTML = '<i class="ph ph-gauge"></i> Calculando...';
    if (progressEta) progressEta.innerHTML = '<i class="ph ph-clock"></i> ETA: --:--';

    // Iniciar transferencia en Python
    const customBackupNameInput = document.getElementById('custom-backup-name');
    const customBackupName = (profile === 'backup' && customBackupNameInput) ? customBackupNameInput.value : '';
    await api.start_transfer(profile, src, dest, customBackupName);
}

// Cancelar transferencia
btnCancel.addEventListener('click', async () => {
    btnCancel.disabled = true;
    btnCancel.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Cancelando...';
    await api.cancel_transfer();
});

// --- Funciones globales llamadas desde Python vía evaluate_js ---

window.update_progress = function(percent_str, speed_str, eta_sec) {
    const progressBar     = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const progressSpeed   = document.getElementById('progress-speed');
    const progressEta     = document.getElementById('progress-eta');

    if (progressBar) progressBar.style.width = percent_str + '%';
    if (progressPercent) progressPercent.textContent = percent_str + '%';
    if (progressSpeed) progressSpeed.innerHTML = '<i class="ph ph-gauge"></i> ' + speed_str;

    let eta_text = '--:--';
    if (eta_sec > 0) {
        let m = Math.floor(eta_sec / 60);
        let s = Math.floor(eta_sec % 60);
        eta_text = `ETA: ${m}m ${s}s`;
    } else if (percent_str >= 100.0 || percent_str === "100.0") {
        eta_text = "Completado";
    }
    if (progressEta) progressEta.innerHTML = '<i class="ph ph-clock"></i> ' + eta_text;
};

window.add_log = function(message, type = 'normal') {
    // Filtrar porcentajes para la barra de progreso
    const percentMatch = message.trim().match(/^(\d+(\.\d+)?)%$/);
    if (percentMatch) {
        const percent = percentMatch[1] + '%';
        const progressBar  = document.getElementById('transfer-progress-bar');
        const progressText = document.getElementById('transfer-progress-text');
        if (progressBar)  progressBar.style.width = percent;
        if (progressText) progressText.textContent = percent;
        return;
    }

    // Ocultar líneas de robocopy innecesarias
    if (message.includes('ROBOCOPY     ::') || message.includes('-------------------------------------')) return;
    if (message.includes('Opciones: *.* /NDL /NFL')) return;

    const div = document.createElement('div');
    div.className = 'log-line';

    if (type === 'success')    div.classList.add('log-success');
    else if (type === 'error') div.classList.add('log-error');
    else if (type === 'header') div.classList.add('log-header');

    div.textContent = message;
    if (type === 'error') {
        div.style.cursor = 'pointer';
        div.title = 'Hacer clic para copiar el error';
        div.addEventListener('click', () => {
            navigator.clipboard.writeText(message).then(() => {
                showToast("Error copiado al portapapeles.", "success");
            }).catch(err => {
                console.error("Error al copiar log de consola:", err);
            });
        });
    }
    consoleOutput.appendChild(div);

    // Limitar líneas para rendimiento
    while (consoleOutput.children.length > 250) {
        consoleOutput.removeChild(consoleOutput.firstChild);
    }

    // Auto-scroll
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
};

window.transfer_complete = function(success, message, has_executables = true) {
    btnStart.style.display = 'flex';
    btnStart.disabled = false;
    btnStart.innerHTML = '<i class="ph ph-rocket-launch"></i> Iniciar Transferencia';
    btnCancel.style.display = 'none';
    btnCancel.disabled = false;
    btnCancel.innerHTML = '<i class="ph ph-stop-circle"></i> Cancelar';

    if (success) {
        statusDot.className = 'dot idle';
        statusText.textContent = 'Completado';
        window.add_log(message, 'success');
        showToast('¡Transferencia Completada Exitosamente!', 'success');

        // Forzar barra al 100%
        const progressBar     = document.getElementById('progress-bar');
        const progressPercent = document.getElementById('progress-percent');
        const progressStatus  = document.getElementById('progress-status');
        if (progressBar)     progressBar.style.width = '100%';
        if (progressPercent) progressPercent.textContent = '100%';
        if (progressStatus)  progressStatus.textContent = 'Completado';

        // Mostrar botón de Admin Install si hay ejecutables
        if (adminActionContainer) {
            adminActionContainer.style.display = has_executables ? 'block' : 'none';
        }
    } else {
        statusDot.className = 'dot error';
        statusText.textContent = 'Error / Cancelado';

        let displayMessage = message;
        if (message && message.includes("cancelada por el usuario")) {
            displayMessage = "Proceso cancelado por el usuario";
        }

        // Poner barra en rojo
        const progressBar     = document.getElementById('progress-bar');
        const progressPercent = document.getElementById('progress-percent');
        const progressStatus  = document.getElementById('progress-status');
        const progressSpeed   = document.getElementById('progress-speed');
        const progressEta     = document.getElementById('progress-eta');

        if (progressBar)     progressBar.style.background = 'linear-gradient(90deg, #ff1744, #d50000)';
        if (progressPercent) progressPercent.textContent = 'Cancelado';
        if (progressStatus)  progressStatus.textContent = 'Proceso Fallido';
        if (progressSpeed)   progressSpeed.innerHTML = '<i class="ph ph-warning-circle"></i> Detenido';
        if (progressEta)     progressEta.innerHTML = '<i class="ph ph-x-circle"></i> Error';

        showToast(displayMessage || "Ocurrió un error en la transferencia", "error");
        window.add_log(message, 'error');
    }

    loadDisks(); // Refrescar discos al terminar
};
