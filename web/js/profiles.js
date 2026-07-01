/* ===================================
   Profiles — Carga y búsqueda de perfiles
   =================================== */

const profileSelect = document.getElementById('profile-select'); // Hidden input for compatibility
const searchProfile = document.getElementById('search-profile');
const profileSelectTrigger = document.getElementById('profile-select-trigger');
const profileOptionsPanel = document.getElementById('profile-options-panel');
const customProfileList = document.getElementById('custom-profile-list');
const btnScanMemory = document.getElementById('btn-scan-memory');
const btnSource     = document.getElementById('btn-source');
const inputSource   = document.getElementById('input-source');

let selectedProfileValue = 'manual';
let allLoadedProfiles = [];

/**
 * Carga los perfiles disponibles desde el backend.
 */
async function loadProfiles() {
    customProfileList.innerHTML = '';
    try {
        const profiles = await api.get_available_profiles();
        allLoadedProfiles = profiles;
        profiles.forEach(p => {
            const opt = document.createElement('div');
            opt.className = 'custom-select-option';
            if (p.id === selectedProfileValue) {
                opt.classList.add('active');
            }
            opt.setAttribute('data-value', p.id);
            
            opt.style.display = 'flex';
            opt.style.justifyContent = 'space-between';
            opt.style.alignItems = 'center';
            opt.style.width = '100%';
            
            let html = `<div style="display: flex; align-items: center; gap: 10px;"><i class="ph ph-cube"></i> <span>${p.name}</span></div>`;
            if (p.is_custom) {
                html += `<button class="delete-profile-btn" data-id="${p.id}" data-name="${p.name}" style="background: transparent; border: none; color: var(--danger-color, #ff4d4d); cursor: pointer; padding: 4px 8px; border-radius: 4px; transition: all 0.2s; display: flex; align-items: center; justify-content: center; margin-top: 0; margin-bottom: 0;"><i class="ph ph-trash" style="font-size: 0.95rem;"></i></button>`;
            }
            opt.innerHTML = html;
            
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                selectProfile(p.id, p.name);
                profileOptionsPanel.style.display = 'none';
            });
            
            if (p.is_custom) {
                const delBtn = opt.querySelector('.delete-profile-btn');
                if (delBtn) {
                    delBtn.addEventListener('mouseenter', () => {
                        delBtn.style.background = 'rgba(255, 77, 77, 0.2)';
                    });
                    delBtn.addEventListener('mouseleave', () => {
                        delBtn.style.background = 'transparent';
                    });
                    delBtn.addEventListener('click', async (e) => {
                        e.stopPropagation(); // Evitar seleccionar el perfil al borrar
                        const confirmDel = confirm(`¿Estás seguro de que deseas eliminar el perfil "${p.name}"?`);
                        if (confirmDel) {
                            try {
                                const res = await api.delete_custom_profile(p.id);
                                if (res.success) {
                                    showToast(res.message, "success");
                                    if (selectedProfileValue === p.id) {
                                        selectProfile('manual', 'Manual (Buscar origen manualmente)');
                                    }
                                    await loadProfiles();
                                } else {
                                    showToast(res.message, "error");
                                }
                            } catch (err) {
                                showToast("Error al eliminar perfil: " + err, "error");
                            }
                        }
                    });
                }
            }
            
            customProfileList.appendChild(opt);
        });
    } catch (e) {
        showToast("Fallo al obtener perfiles: " + e, 'error');
    }
}

// Configurar opción manual fija
const manualOption = document.querySelector('.custom-select-option[data-value="manual"]');
if (manualOption) {
    manualOption.addEventListener('click', (e) => {
        e.stopPropagation();
        selectProfile('manual', 'Manual (Buscar origen manualmente)');
        profileOptionsPanel.style.display = 'none';
    });
}

/**
 * Selecciona un perfil y actualiza su estado.
 */
async function selectProfile(profileId, profileName) {
    selectedProfileValue = profileId;
    if (profileSelect) {
        profileSelect.value = profileId;
    }
    if (searchProfile) {
        searchProfile.value = profileName;
    }

    // Quitar active de todas las opciones y ponerlo en la seleccionada
    document.querySelectorAll('.custom-select-option').forEach(opt => {
        if (opt.getAttribute('data-value') === profileId) {
            opt.classList.add('active');
        } else {
            opt.classList.remove('active');
        }
    });

    if (profileId === 'manual') {
        btnSource.style.display = 'block';
        inputSource.value = '';
    } else {
        btnSource.style.display = 'none';
        inputSource.value = 'Buscando carpeta del perfil en USBs...';
        const folderPath = await api.find_profile_folder(profileId);
        if (folderPath) {
            inputSource.value = folderPath;
        } else {
            inputSource.value = '';
            showToast(`No se encontró el instalador para ${profileName}.`, 'error');
            selectProfile('manual', 'Manual (Buscar origen manualmente)');
        }
    }
}

// Abrir/Cerrar Dropdown interactivo
if (profileSelectTrigger) {
    profileSelectTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = profileOptionsPanel.style.display === 'none' || !profileOptionsPanel.style.display;
        
        if (e.target === searchProfile) {
            // Si hacen clic en el campo de texto, siempre queremos que se mantenga abierto
            profileOptionsPanel.style.display = 'block';
        } else {
            // Si hacen clic en el caret o en el contenedor, alterna abrir/cerrar
            profileOptionsPanel.style.display = isHidden ? 'block' : 'none';
        }
        
        if (profileOptionsPanel.style.display === 'block' && searchProfile) {
            searchProfile.select(); // Selecciona el texto para facilitar la edición
        }
    });
}

if (searchProfile) {
    // Si escribe en el buscador, filtrar los elementos
    searchProfile.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        profileOptionsPanel.style.display = 'block'; // Asegurar que esté abierto

        // Filtrar opción manual
        const manualOpt = document.querySelector('.custom-select-option[data-value="manual"]');
        if (manualOpt) {
            const manualText = manualOpt.textContent.toLowerCase();
            manualOpt.style.display = manualText.includes(searchTerm) ? 'flex' : 'none';
        }

        // Filtrar perfiles cargados
        const options = customProfileList.querySelectorAll('.custom-select-option');
        options.forEach(opt => {
            const text = opt.textContent.toLowerCase();
            opt.style.display = text.includes(searchTerm) ? 'flex' : 'none';
        });
    });

    // Abrir dropdown al enfocar el buscador
    searchProfile.addEventListener('focus', (e) => {
        e.stopPropagation();
        profileOptionsPanel.style.display = 'block';
    });
}

// Cerrar dropdown si se hace click en cualquier otra parte
document.addEventListener('click', () => {
    if (profileOptionsPanel) {
        profileOptionsPanel.style.display = 'none';
    }
});

// Escanear memorias USB
if (btnScanMemory) {
    btnScanMemory.addEventListener('click', async () => {
        try {
            showToast("Escaneando memoria...", "info");
            const result = await api.scan_usb_installers();
            if (result.success) {
                showToast("Carpeta INSTALADORES encontrada con éxito.", "success");
                await loadProfiles();
                if (result.source_path) {
                    inputSource.value = result.source_path;
                }
            } else {
                showToast(result.message, "error");
            }
        } catch (e) {
            showToast("Fallo el escaneo: " + e, "error");
        }
    });
}

// --- Creación de Perfiles y Credenciales Admin (NUEVO) ---

// Elementos del panel de Creación de Perfil
const btnCreateProfileToggle = document.getElementById('btn-create-profile-toggle');
const createProfilePanel = document.getElementById('create-profile-panel');
const btnNewProfileBrowse = document.getElementById('btn-new-profile-browse');
const newProfileName = document.getElementById('new-profile-name');
const newProfileFolder = document.getElementById('new-profile-folder');
const profileInstallersContainer = document.getElementById('profile-installers-container');
const btnAddProfileInstaller = document.getElementById('btn-add-profile-installer');
const btnSaveProfile = document.getElementById('btn-save-profile');
const btnCancelProfile = document.getElementById('btn-cancel-profile');



// Toggle del panel de Creación de Perfil
if (btnCreateProfileToggle && createProfilePanel) {
    btnCreateProfileToggle.addEventListener('click', () => {
        const isHidden = createProfilePanel.style.display === 'none';
        createProfilePanel.style.display = isHidden ? 'flex' : 'none';
    });
}

if (btnCancelProfile) {
    btnCancelProfile.addEventListener('click', () => {
        createProfilePanel.style.display = 'none';
        clearProfileForm();
    });
}

function clearProfileForm() {
    if (newProfileName) newProfileName.value = '';
    if (newProfileFolder) newProfileFolder.value = '';
    
    if (profileInstallersContainer) {
        const blocks = profileInstallersContainer.querySelectorAll('.installer-block');
        // Remover bloques de dependencia
        for (let i = 1; i < blocks.length; i++) {
            blocks[i].remove();
        }
        // Resetear primer bloque
        const firstBlock = blocks[0];
        if (firstBlock) {
            const exeInput = firstBlock.querySelector('.new-profile-exe');
            const argsInput = firstBlock.querySelector('.new-profile-args');
            const adminCheck = firstBlock.querySelector('.new-profile-admin');
            if (exeInput) exeInput.value = '';
            if (argsInput) argsInput.value = '/quiet /norestart';
            if (adminCheck) adminCheck.checked = true;
        }
    }
}

// Buscar carpeta origen para el nuevo perfil
if (btnNewProfileBrowse) {
    btnNewProfileBrowse.addEventListener('click', async () => {
        const path = await api.select_folder();
        if (path) {
            newProfileFolder.value = path;
            const parts = path.replace(/\\/g, '/').split('/');
            const folderName = parts.pop() || parts.pop();
            if (folderName && newProfileName && !newProfileName.value) {
                newProfileName.value = folderName;
            }
        }
    });
}

// Registrar busqueda en un bloque de instalador
function registerBrowseButton(block) {
    const btn = block.querySelector('.btn-new-profile-exe-browse');
    const input = block.querySelector('.new-profile-exe');
    if (btn && input) {
        btn.addEventListener('click', async () => {
            const exePath = await api.select_file();
            if (exePath) {
                let relativePath = exePath;
                const folderVal = newProfileFolder.value.trim();
                if (folderVal && exePath.toLowerCase().startsWith(folderVal.toLowerCase())) {
                    relativePath = exePath.substring(folderVal.length).replace(/^[\\/]+/, '');
                } else {
                    const parts = exePath.replace(/\\/g, '/').split('/');
                    relativePath = parts.pop();
                }
                input.value = relativePath;
            }
        });
    }
}

// Inicializar el primer bloque
const firstBlock = document.querySelector('.installer-block');
if (firstBlock) {
    registerBrowseButton(firstBlock);
}

// Reindexar nombres de bloques
function reindexInstallers() {
    if (!profileInstallersContainer) return;
    const blocks = profileInstallersContainer.querySelectorAll('.installer-block');
    blocks.forEach((block, idx) => {
        const titleSpan = block.querySelector('span');
        if (titleSpan) {
            if (idx === 0) {
                titleSpan.textContent = "Ejecutable 1 (Principal)";
                titleSpan.style.color = "var(--accent-color)";
            } else {
                titleSpan.textContent = `Ejecutable ${idx + 1} (Dependencia)`;
                titleSpan.style.color = "var(--accent-hover)";
            }
        }
    });
}

// Boton Añadir Ejecutable
if (btnAddProfileInstaller && profileInstallersContainer) {
    btnAddProfileInstaller.addEventListener('click', () => {
        const count = profileInstallersContainer.children.length + 1;
        const div = document.createElement('div');
        div.className = 'installer-block';
        div.style.background = 'rgba(255,255,255,0.01)';
        div.style.padding = '10px';
        div.style.borderRadius = '6px';
        div.style.border = '1px solid rgba(255,255,255,0.03)';
        div.style.display = 'flex';
        div.style.flexDirection = 'column';
        div.style.gap = '8px';
        div.style.marginTop = '10px';

        div.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.85rem; font-weight: bold; color: var(--accent-hover);">Ejecutable ${count} (Dependencia)</span>
                <button type="button" class="btn-danger btn-remove-installer" style="padding: 4px 8px; font-size: 0.75rem; margin-top:0; border-radius: 4px;"><i class="ph ph-trash"></i> Quitar</button>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                <span style="font-size: 0.8rem; color: var(--text-secondary);">Archivo Ejecutable (ej. hotfix.exe)</span>
                <div style="display: flex; gap: 10px;">
                    <input type="text" class="new-profile-exe" placeholder="Ej. hotfix.exe o update.exe" style="flex: 1; background: var(--input-bg); border: 1px solid var(--panel-border); border-radius: 6px; padding: 8px 10px; color: var(--text-primary); outline: none; font-size: 0.9rem;">
                    <button type="button" class="btn-new-profile-exe-browse btn-secondary" style="padding: 8px 12px; font-size: 0.85rem; margin-top:0;">Buscar</button>
                </div>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
                <span style="font-size: 0.8rem; color: var(--text-secondary);">Argumentos de Instalación Silenciosa</span>
                <input type="text" class="new-profile-args" placeholder="Ej. /quiet /norestart" value="/quiet /norestart" style="background: var(--input-bg); border: 1px solid var(--panel-border); border-radius: 6px; padding: 8px 10px; color: var(--text-primary); outline: none; font-size: 0.9rem;">
            </div>
            <div style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                <input type="checkbox" class="new-profile-admin" checked style="width: 16px; height: 16px; accent-color: var(--accent-color);">
                <span style="font-size: 0.85rem; color: var(--text-primary);">Ejecutar como Administrador</span>
            </div>
        `;

        // Registrar remover
        div.querySelector('.btn-remove-installer').addEventListener('click', () => {
            div.remove();
            reindexInstallers();
        });

        // Registrar buscar
        registerBrowseButton(div);

        profileInstallersContainer.appendChild(div);
    });
}

// Guardar nuevo perfil
if (btnSaveProfile) {
    btnSaveProfile.addEventListener('click', async () => {
        const name = newProfileName.value.trim();
        const folder = newProfileFolder.value.trim();

        // Obtener todos los ejecutables configurados
        const installers = [];
        const blocks = profileInstallersContainer.querySelectorAll('.installer-block');
        let isValid = true;
        
        blocks.forEach(block => {
            const exeInput = block.querySelector('.new-profile-exe');
            const argsInput = block.querySelector('.new-profile-args');
            const adminCheck = block.querySelector('.new-profile-admin');
            
            const exeVal = exeInput ? exeInput.value.trim() : '';
            const argsVal = argsInput ? argsInput.value.trim() : '';
            const adminVal = adminCheck ? adminCheck.checked : true;
            
            if (!exeVal) {
                isValid = false;
            } else {
                installers.push({
                    exe: exeVal,
                    args: argsVal,
                    requireAdmin: adminVal
                });
            }
        });

        if (!name || !folder || !isValid || installers.length === 0) {
            showToast("Por favor completa los campos obligatorios (Nombre, Carpeta y al menos el Ejecutable Principal).", "error");
            return;
        }

        btnSaveProfile.disabled = true;
        btnSaveProfile.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Guardando...';

        try {
            const res = await api.create_custom_profile({ name, folder, installers });
            if (res.success) {
                showToast(res.message, "success");
                createProfilePanel.style.display = 'none';
                clearProfileForm();
                await loadProfiles();
                // Seleccionar el nuevo perfil creado utilizando el ID retornado por el backend
                const profileId = res.profile_id || name.replace(/[^a-zA-Z0-9_-]/g, '').toLowerCase();
                selectProfile(profileId, name);
            } else {
                showToast(res.message, "error");
            }
        } catch (e) {
            showToast("Error al guardar perfil: " + e, "error");
        } finally {
            btnSaveProfile.disabled = false;
            btnSaveProfile.innerHTML = '<i class="ph ph-floppy-disk"></i> Guardar Perfil';
        }
    });
}


