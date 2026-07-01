/* ===================================
   Tabs — Modo Auto / Manual
   =================================== */

let currentMode = 'auto'; // 'auto' | 'manual' | 'backup'
let manualItems = [];

const tabAuto           = document.getElementById('tab-auto');
const tabManual         = document.getElementById('tab-manual');
const tabBackup         = document.getElementById('tab-backup');
const autoProfileGroup  = document.getElementById('auto-profile-group');
const autoSourceGroup   = document.getElementById('auto-source-group');
const manualSourceGroup = document.getElementById('manual-source-group');
const backupGroup       = document.getElementById('backup-group');
const backupFoldersList = document.getElementById('backup-folders-list');
const btnAddFiles     = document.getElementById('btn-add-files');
const btnAddFolder    = document.getElementById('btn-add-folder');
const btnClearManual  = document.getElementById('btn-clear-manual');
const manualItemsList = document.getElementById('manual-items-list');

/**
 * Cambia entre modos de la aplicación.
 */
function toggleMode(mode) {
    currentMode = mode;

    tabAuto.classList.toggle('active', mode === 'auto');
    tabManual.classList.toggle('active', mode === 'manual');
    tabBackup.classList.toggle('active', mode === 'backup');

    autoProfileGroup.style.display  = mode === 'auto' ? 'block' : 'none';
    if (autoSourceGroup) autoSourceGroup.style.display = mode === 'auto' ? 'block' : 'none';
    manualSourceGroup.style.display = mode === 'manual' ? 'block' : 'none';
    backupGroup.style.display       = mode === 'backup' ? 'block' : 'none';

    if (mode === 'backup') {
        loadBackupFolders();
    }
}

if (tabAuto && tabManual && tabBackup) {
    tabAuto.addEventListener('click', () => toggleMode('auto'));
    tabManual.addEventListener('click', () => toggleMode('manual'));
    tabBackup.addEventListener('click', () => toggleMode('backup'));
}

let defaultBackupFolders = [];
let customBackupItems = [];

const btnBackupAddFiles = document.getElementById('btn-backup-add-files');
const btnBackupAddFolder = document.getElementById('btn-backup-add-folder');

/**
 * Carga el estado de las carpetas estándar de usuario del equipo.
 */
async function loadBackupFolders() {
    if (!backupFoldersList) return;
    
    // Si ya los cargamos antes, solo renderizamos para no hacer llamadas lentas al backend
    if (defaultBackupFolders.length > 0) {
        renderBackupFoldersList();
        return;
    }
    
    backupFoldersList.innerHTML = '<div class="loading-container"><i class="ph ph-spinner ph-spin"></i> Detectando carpetas...</div>';
    
    try {
        defaultBackupFolders = await api.get_backup_folders_status();
        // Inicializar checked a True para carpetas que existen
        defaultBackupFolders.forEach(f => {
            f.checked = f.exists;
        });
        renderBackupFoldersList();
    } catch (e) {
        console.error("Error al cargar carpetas de usuario:", e);
        backupFoldersList.innerHTML = '<div class="text-muted" style="padding:10px;">Error al consultar las carpetas del sistema.</div>';
    }
}

/**
 * Renderiza la lista de carpetas estándar más los elementos adicionales agregados por el usuario.
 */
function renderBackupFoldersList() {
    if (!backupFoldersList) return;
    backupFoldersList.innerHTML = '';
    
    // 1. Renderizar carpetas por defecto
    defaultBackupFolders.forEach(folder => {
        const disabledClass = folder.exists ? '' : 'disabled';
        const checkedAttribute = folder.exists ? (folder.checked ? 'checked' : '') : 'disabled';
        const icon = getFolderIcon(folder.id);
        
        const html = `
            <div class="backup-folder-item ${disabledClass}">
                <div class="backup-folder-left">
                    <i class="ph ${icon}"></i>
                    <div class="backup-folder-info">
                        <span class="backup-folder-name">${folder.name} <span class="backup-folder-size" id="size-${folder.id}" style="font-size: 0.75rem; color: var(--text-secondary); margin-left: 8px;">(${folder.size_str || 'Calculando...'})</span></span>
                        <span class="backup-folder-path" title="${folder.path}">${folder.path}</span>
                    </div>
                </div>
                <input type="checkbox" class="backup-folder-checkbox" value="${folder.path}" data-id="${folder.id}" ${checkedAttribute}>
            </div>
        `;
        backupFoldersList.insertAdjacentHTML('beforeend', html);
    });
    
    // 2. Renderizar carpetas/archivos adicionales del usuario
    customBackupItems.forEach((item, index) => {
        const itemPath = item.path;
        const isFile = itemPath.includes('.') && !itemPath.endsWith('\\') && !itemPath.endsWith('/');
        const icon = isFile ? 'ph-file' : 'ph-folder';
        const name = itemPath.replace(/\\/g, '/').split('/').pop() || itemPath;
        const checkedAttribute = item.checked ? 'checked' : '';
        
        const html = `
            <div class="backup-folder-item">
                <div class="backup-folder-left">
                    <i class="ph ${icon}"></i>
                    <div class="backup-folder-info">
                        <span class="backup-folder-name">${name}</span>
                        <span class="backup-folder-path" title="${itemPath}">${itemPath}</span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <input type="checkbox" class="backup-folder-checkbox" value="${itemPath}" data-id="custom-${index}" ${checkedAttribute}>
                    <button class="icon-btn" onclick="removeCustomBackupItem(${index})" style="color:#ef4444; font-size:1rem; border:none; background:none; cursor:pointer;" title="Quitar"><i class="ph ph-trash"></i></button>
                </div>
            </div>
        `;
        backupFoldersList.insertAdjacentHTML('beforeend', html);
    });

    // Vincular eventos de cambio para guardar el estado en tiempo real
    const checkboxes = backupFoldersList.querySelectorAll('.backup-folder-checkbox');
    checkboxes.forEach(cb => {
        cb.addEventListener('change', () => {
            const id = cb.getAttribute('data-id');
            if (id.startsWith('custom-')) {
                const idx = parseInt(id.replace('custom-', ''), 10);
                if (customBackupItems[idx]) {
                    customBackupItems[idx].checked = cb.checked;
                }
            } else {
                const folder = defaultBackupFolders.find(f => f.id === id);
                if (folder) {
                    folder.checked = cb.checked;
                }
            }
        });
    });
}

// Quitar un elemento personalizado de la lista
window.removeCustomBackupItem = function (index) {
    customBackupItems.splice(index, 1);
    renderBackupFoldersList();
};

// Agregar archivos personalizados
if (btnBackupAddFiles) {
    btnBackupAddFiles.addEventListener('click', async () => {
        const paths = await api.select_files();
        if (paths && paths.length > 0) {
            paths.forEach(p => {
                if (!customBackupItems.some(item => item.path === p)) {
                    customBackupItems.push({ path: p, checked: true });
                }
            });
            renderBackupFoldersList();
        }
    });
}

// Agregar carpetas personalizadas
if (btnBackupAddFolder) {
    btnBackupAddFolder.addEventListener('click', async () => {
        const path = await api.select_folder();
        if (path) {
            if (!customBackupItems.some(item => item.path === path)) {
                customBackupItems.push({ path: path, checked: true });
            }
            renderBackupFoldersList();
        }
    });
}

// Botones de selección masiva
const btnBackupSelectAll = document.getElementById('btn-backup-select-all');
const btnBackupDeselectAll = document.getElementById('btn-backup-deselect-all');

if (btnBackupSelectAll) {
    btnBackupSelectAll.addEventListener('click', () => {
        defaultBackupFolders.forEach(f => {
            if (f.exists) f.checked = true;
        });
        customBackupItems.forEach(item => {
            item.checked = true;
        });
        renderBackupFoldersList();
    });
}

if (btnBackupDeselectAll) {
    btnBackupDeselectAll.addEventListener('click', () => {
        defaultBackupFolders.forEach(f => {
            f.checked = false;
        });
        customBackupItems.forEach(item => {
            item.checked = false;
        });
        renderBackupFoldersList();
    });
}

function getFolderIcon(id) {
    switch (id) {
        case 'Desktop': return 'ph-desktop';
        case 'Documents': return 'ph-file-text';
        case 'Downloads': return 'ph-download-simple';
        case 'Pictures': return 'ph-image';
        case 'Videos': return 'ph-video-camera';
        default: return 'ph-folder';
    }
}

/**
 * Renderiza la lista de archivos/carpetas manuales.
 */
function renderManualList() {
    manualItemsList.innerHTML = '';
    manualItems.forEach((item, index) => {
        const li = document.createElement('li');
        const isFile = item.includes('.') && !item.endsWith('\\');
        const icon = isFile ? '<i class="ph ph-file"></i>' : '<i class="ph ph-folder"></i>';

        li.innerHTML = `
            <span style="flex:1; margin-left:8px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${item}">${icon} ${item}</span>
            <button onclick="removeManualItem(${index})"><i class="ph ph-trash"></i></button>
        `;
        manualItemsList.appendChild(li);
    });
}

window.removeManualItem = function (index) {
    manualItems.splice(index, 1);
    renderManualList();
};

// Añadir archivos
if (btnAddFiles) {
    btnAddFiles.addEventListener('click', async () => {
        const paths = await api.select_files();
        if (paths && paths.length > 0) {
            manualItems.push(...paths);
            renderManualList();
        }
    });
}

// Añadir carpeta
if (btnAddFolder) {
    btnAddFolder.addEventListener('click', async () => {
        const path = await api.select_folder();
        if (path) {
            manualItems.push(path);
            renderManualList();
        }
    });
}

// Limpiar lista
if (btnClearManual) {
    btnClearManual.addEventListener('click', () => {
        manualItems = [];
        renderManualList();
    });
}

// Actualizar tamaño de carpeta en la pestaña de respaldo rápido
window.update_backup_folder_size = function(folderId, sizeStr) {
    // Actualizar en el caché local
    const folder = defaultBackupFolders.find(f => f.id === folderId);
    if (folder) {
        folder.size_str = sizeStr;
    }
    
    // Actualizar elemento en el DOM
    const el = document.getElementById(`size-${folderId}`);
    if (el) {
        el.textContent = `(${sizeStr})`;
    }
};
