import os
import json
import psutil
import string

def get_drives():
    drives = [p.mountpoint for p in psutil.disk_partitions(all=False) if p.fstype]
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.exists(desktop_path):
        drives.append(desktop_path)
    return drives

def discover_and_generate_profiles():
    target_folder = "INSTALADORES"
    found_root = None
    
    # 1. Buscar la carpeta INSTALADORES en todas las unidades
    for drive in get_drives():
        test_path = os.path.join(drive, target_folder)
        if os.path.isdir(test_path):
            found_root = test_path
            break
            
    if not found_root:
        return {"success": False, "message": "No se encontró la carpeta INSTALADORES en ninguna unidad."}

    pipelines_dir = _get_writable_pipelines_dir()
    generated = 0
    
    # 2. Escanear recursivamente buscando patrones de instaladores
    for root, dirs, files in os.walk(found_root):
        rel_path = os.path.relpath(root, found_root)
        profile_id = rel_path.replace("\\", "_").replace(" ", "")
        
        # Ignorar subcarpetas internas de PSAppDeployToolkit
        if "AppDeployToolkit" in dirs:
            dirs.remove("AppDeployToolkit")
        if "Files" in dirs:
            dirs.remove("Files")
            
        lower_files = [f.lower() for f in files]
        
        # Patrón 1: PSAppDeployToolkit
        if "deploy-application.exe" in lower_files:
            create_psadt_profile(profile_id, target_folder + "\\" + rel_path)
            generated += 1
            dirs.clear() # No buscar más profundo aquí
            continue
            
        # Patrón 2: Instalador setup.exe estándar
        if "setup.exe" in lower_files:
            create_standard_profile(profile_id, target_folder + "\\" + rel_path, "setup.exe")
            generated += 1
            if rel_path != ".": dirs.clear()
            continue
            
        # Patrón 3: Archivos MSI sueltos
        msi_files = [f for f in files if f.lower().endswith('.msi')]
        if msi_files:
            create_standard_profile(profile_id, target_folder + "\\" + rel_path, msi_files[0])
            generated += 1
            if rel_path != ".": dirs.clear()
            continue

    return {"success": True, "message": f"Se generaron {generated} perfiles automáticamente."}

def create_psadt_profile(profile_id, source_folder):
    profile_name = profile_id[:25] # Acortar el nombre si es muy largo
    data = {
        "profile_name": profile_name,
        "source_folder_name": source_folder,
        "steps": [
            {
                "type": "copy",
                "description": f"Copiando {profile_name} a local",
                "fail_on_error": True
            },
            {
                "type": "installer",
                "description": "Lanzando PSAppDeployToolkit",
                "executable": "Deploy-Application.exe",
                "arguments": "-DeployMode \"Silent\"",
                "fail_on_error": True
            }
        ]
    }
    _save_json(profile_id, data)

def create_standard_profile(profile_id, source_folder, executable):
    profile_name = profile_id[:25]
    data = {
        "profile_name": profile_name,
        "source_folder_name": source_folder,
        "steps": [
            {
                "type": "copy",
                "description": f"Copiando {profile_name} a local",
                "fail_on_error": True
            },
            {
                "type": "installer",
                "description": f"Ejecutando {executable}",
                "executable": executable,
                "arguments": "/quiet /norestart",
                "fail_on_error": True
            }
        ]
    }
    _save_json(profile_id, data)

def _get_writable_pipelines_dir():
    import sys
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(".")
    p_dir = os.path.join(base_dir, "pipelines")
    os.makedirs(p_dir, exist_ok=True)
    return p_dir

def _save_json(filename, data):
    # Limpiar nombre de archivo
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in filename if c in valid_chars)
    pipelines_dir = _get_writable_pipelines_dir()
    filepath = os.path.join(pipelines_dir, f"{filename}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
