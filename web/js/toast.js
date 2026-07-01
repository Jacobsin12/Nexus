/* ===================================
   Toast — Sistema unificado de alertas
   =================================== */

/**
 * Muestra una notificación toast.
 * @param {string} message - Mensaje a mostrar
 * @param {string} type - Tipo: 'success', 'error', 'info'
 */
function showToast(message, type = 'error') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    // Icono según tipo
    const icons = {
        error:   'ph-warning-circle',
        success: 'ph-check-circle',
        info:    'ph-info'
    };
    const iconClass = icons[type] || icons.info;

    toast.innerHTML = `
        <i class="ph ${iconClass}"></i>
        <span class="toast-message" style="flex: 1; padding-right: 8px;">${message}</span>
        <div style="display: flex; gap: 4px; align-items: center; margin-left: auto;">
            <button class="toast-copy-btn" title="Copiar mensaje">
                <i class="ph ph-copy"></i>
            </button>
            <button class="toast-close-btn" title="Cerrar">
                <i class="ph ph-x"></i>
            </button>
        </div>
    `;

    container.appendChild(toast);

    const copyBtn = toast.querySelector('.toast-copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            navigator.clipboard.writeText(message).then(() => {
                const icon = copyBtn.querySelector('i');
                icon.className = 'ph ph-check';
                copyBtn.style.color = '#10b981';
                setTimeout(() => {
                    icon.className = 'ph ph-copy';
                    copyBtn.style.color = '';
                }, 1500);
            }).catch(err => {
                console.error("Error al copiar toast:", err);
            });
        });
    }

    // Botón de cerrar manual
    const closeBtn = toast.querySelector('.toast-close-btn');
    let autoDismissTimeout = null;

    function dismissToast() {
        if (autoDismissTimeout) clearTimeout(autoDismissTimeout);
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            dismissToast();
        });
    }

    // Animar entrada
    requestAnimationFrame(() => toast.classList.add('show'));

    // Animar salida y remover automáticamente tras 4 segundos
    autoDismissTimeout = setTimeout(() => {
        dismissToast();
    }, 4000);
}
