/* ===================================
   Disks — Carga y renderizado de discos
   =================================== */

const diskList = document.getElementById('disk-list');
const btnRefresh = document.getElementById('btn-refresh');

/**
 * Carga la lista de discos desde el backend y los renderiza.
 */
async function loadDisks() {
    diskList.innerHTML = '<div class="loading-container"><i class="ph ph-spinner ph-spin"></i> Cargando discos...</div>';

    const disks = await api.get_disks();

    diskList.innerHTML = '';

    if (!disks || disks.length === 0) {
        diskList.innerHTML = '<div class="text-muted">No se encontraron discos.</div>';
        return;
    }

    disks.forEach(disk => {
        const percent = ((disk.total - disk.free) / disk.total) * 100;
        const safeId = disk.device.replace(/[:\\\\]/g, '');

        const html = `
            <div class="disk-item">
                <div class="disk-header">
                    <span class="disk-letter">${disk.device}</span>
                    <span class="disk-type" id="type-${safeId}">${disk.type}</span>
                </div>
                <div class="disk-space">
                    ${disk.free_gb} libres de ${disk.total_gb}
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" style="width: ${percent}%"></div>
                </div>
            </div>
        `;
        diskList.insertAdjacentHTML('beforeend', html);
    });

    // Pedir tipos detallados (SSD, HDD, NVMe) en segundo plano
    api.get_disk_types_map_async().then(diskMap => {
        if (!diskMap) return;
        for (const [device, label] of Object.entries(diskMap)) {
            const safeId = device.replace(/[:\\\\]/g, '');
            const typeSpan = document.getElementById(`type-${safeId}`);
            if (typeSpan) {
                typeSpan.textContent = label;
            }
        }
    });
}

// Botón de refrescar
btnRefresh.addEventListener('click', loadDisks);

// Función global para que Python la llame vía evaluate_js
window.trigger_reload_disks = function () {
    console.log("Cambio en discos detectado. Actualizando...");
    loadDisks();
};
