import webview
import psutil
import subprocess
import threading
import re
import os
import json
import time
import shutil
import socket
import datetime
import ctypes
import logging
import database
import discovery
import sys

# ─── Referencia global a la ventana de pywebview ───
_window = None
_progress_window = None

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller"""
    try:
        # PyInstaller crea una carpeta temporal y almacena la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_app_profile_dir():
    """Retorna el directorio para credenciales y configuraciones locales en AppData."""
    path = os.path.join(database.get_user_data_dir(), ".app_profile")
    os.makedirs(path, exist_ok=True)
    return path


def get_pipelines_search_paths():
    """Retorna una lista de rutas (ordenadas por prioridad) para buscar perfiles."""
    paths = []
    
    # 1. Recursos empaquetados por PyInstaller (sys._MEIPASS o desarrollo)
    bundled_dir = resource_path("pipelines")
    if os.path.exists(bundled_dir):
        paths.append(bundled_dir)
        
    # 2. Directorio de datos del usuario en AppData
    user_dir = os.path.join(database.get_user_data_dir(), "pipelines")
    if os.path.exists(user_dir):
        paths.append(user_dir)
        
    # 3. Junto al ejecutable (para el .exe compilado portátil)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.join(os.path.dirname(sys.executable), "pipelines")
        if exe_dir not in paths:
            paths.append(exe_dir)
            
    # 4. Directorio de trabajo actual (CWD)
    cwd_dir = os.path.abspath("pipelines")
    if cwd_dir not in paths:
        paths.append(cwd_dir)
        
    return paths


def get_writable_pipelines_dir():
    """Retorna el directorio donde se deben guardar los nuevos perfiles personalizados (en AppData)."""
    p_dir = os.path.join(database.get_user_data_dir(), "pipelines")
    os.makedirs(p_dir, exist_ok=True)
    return p_dir


def call_js(func_name, *args):
    """Llama a una función JavaScript desde Python vía pywebview.evaluate_js."""
    global _window
    if _window is None:
        return
    try:
        js_args = ', '.join(json.dumps(a) for a in args)
        _window.evaluate_js(f'{func_name}({js_args})')
    except Exception:
        pass


# ═══════════════════════════════════════════════════
#  Funciones de soporte (sin dependencia de UI)
# ═══════════════════════════════════════════════════

def get_disk_types_map():
    """Obtiene un mapa de las unidades y sus tipos físicos usando PowerShell"""
    disk_map = {}
    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        
        # Obtener discos físicos
        cmd_disks = ['powershell', '-NoProfile', '-Command', 'Get-PhysicalDisk | Select-Object DeviceId, MediaType, BusType | ConvertTo-Json']
        proc_disks = subprocess.run(cmd_disks, capture_output=True, text=True, creationflags=flags)
        
        # Obtener particiones
        cmd_parts = ['powershell', '-NoProfile', '-Command', 'Get-Partition | Select-Object DriveLetter, DiskNumber | ConvertTo-Json']
        proc_parts = subprocess.run(cmd_parts, capture_output=True, text=True, creationflags=flags)
        
        if proc_disks.returncode == 0 and proc_parts.returncode == 0:
            if proc_disks.stdout.strip() and proc_parts.stdout.strip():
                physical_disks = json.loads(proc_disks.stdout)
                partitions = json.loads(proc_parts.stdout)
                
                if isinstance(physical_disks, dict): physical_disks = [physical_disks]
                if isinstance(partitions, dict): partitions = [partitions]
                
                disk_info = {str(d.get("DeviceId")): d for d in physical_disks}
                
                for p in partitions:
                    letter = p.get("DriveLetter")
                    if letter:
                        disk_num = str(p.get("DiskNumber"))
                        if disk_num in disk_info:
                            d_info = disk_info[disk_num]
                            media = d_info.get("MediaType", "")
                            bus = d_info.get("BusType", "")
                            
                            media_str = str(media)
                            if media_str == "3" or media_str == "HDD": media_str = "HDD"
                            elif media_str == "4" or media_str == "SSD": media_str = "SSD"
                            else: media_str = "Disco Fijo"
                            
                            # Formatear la etiqueta
                            if bus == "NVMe":
                                label = "SSD (NVMe)"
                            elif bus == "USB":
                                if media_str in ["HDD", "SSD"]:
                                    label = f"{media_str} Externo (USB)"
                                else:
                                    label = "USB Extraíble"
                            else:
                                label = f"{media_str} ({bus})"
                            
                            disk_map[f"{letter}:\\"] = label
    except Exception as e:
        pass
    return disk_map


def get_dir_size(path):
    """Calcula el peso total de un directorio o una lista de archivos/directorios en bytes de forma rápida, excluyendo offline/junctions."""
    total = 0
    try:
        is_windows = os.name == 'nt'
        if is_windows:
            import ctypes
        
        if isinstance(path, list):
            for p in path:
                if os.path.islink(p):
                    continue
                if os.path.isfile(p):
                    try:
                        if is_windows:
                            attrs = ctypes.windll.kernel32.GetFileAttributesW(p)
                            if attrs != -1 and (attrs & 0x1000): # FILE_ATTRIBUTE_OFFLINE
                                continue
                    except Exception:
                        pass
                    total += os.path.getsize(p)
                elif os.path.isdir(p):
                    try:
                        if is_windows:
                            attrs = ctypes.windll.kernel32.GetFileAttributesW(p)
                            if attrs != -1 and (attrs & 0x400): # FILE_ATTRIBUTE_REPARSE_POINT (junction)
                                continue
                    except Exception:
                        pass
                    for entry in os.scandir(p):
                        try:
                            # follow_symlinks=False para no resolver links
                            stat = entry.stat(follow_symlinks=False)
                            attrs = getattr(stat, 'st_file_attributes', 0)
                            if (attrs & 0x1000) or (attrs & 0x400):
                                continue
                        except Exception:
                            pass
                        
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total += get_dir_size(entry.path)
            return total
            
        if os.path.islink(path):
            return 0
            
        if os.path.isfile(path):
            try:
                if is_windows:
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
                    if attrs != -1 and (attrs & 0x1000):
                        return 0
            except Exception:
                pass
            return os.path.getsize(path)
            
        # Directorio único
        try:
            if is_windows:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
                if attrs != -1 and (attrs & 0x400):
                    return 0
        except Exception:
            pass
            
        for entry in os.scandir(path):
            try:
                stat = entry.stat(follow_symlinks=False)
                attrs = getattr(stat, 'st_file_attributes', 0)
                if (attrs & 0x1000) or (attrs & 0x400):
                    continue
            except Exception:
                pass
                
            if entry.is_file(follow_symlinks=False):
                total += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total


def write_audit_log(profile_name, src, dst, duration_str, status, details=""):
    """Escribe un registro de auditoría de la transferencia usando SQLite."""
    database.log_transfer(profile_name, src, dst, duration_str, status, details)


def check_has_executables(folder):
    """Busca si hay archivos ejecutables en el directorio de destino"""
    try:
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(('.exe', '.msi', '.bat', '.cmd')):
                    return True
    except Exception:
        pass
    return False


def _run_as_admin_and_wait(exe_path, args, working_dir):
    """Ejecuta un programa como administrador usando ShellExecuteEx y espera a que termine."""
    import ctypes
    import ctypes.wintypes
    
    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    INFINITE = 0xFFFFFFFF
    
    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", ctypes.wintypes.HANDLE),
            ("lpVerb", ctypes.c_wchar_p),
            ("lpFile", ctypes.c_wchar_p),
            ("lpParameters", ctypes.c_wchar_p),
            ("lpDirectory", ctypes.c_wchar_p),
            ("nShow", ctypes.c_int),
            ("hInstApp", ctypes.wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", ctypes.c_wchar_p),
            ("hkeyClass", ctypes.wintypes.HKEY),
            ("dwHotKey", ctypes.wintypes.DWORD),
            ("hIcon", ctypes.wintypes.HANDLE),
            ("hProcess", ctypes.wintypes.HANDLE),
        ]
    
    # Para MSI, usar msiexec
    if exe_path.lower().endswith(".msi"):
        params = f'/i "{exe_path}" {args}'
        exe_path = "msiexec.exe"
    else:
        params = args
    
    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.hwnd = None
    sei.lpVerb = "runas"
    sei.lpFile = exe_path
    sei.lpParameters = params
    sei.lpDirectory = working_dir
    sei.nShow = 1  # SW_SHOWNORMAL
    sei.hProcess = None
    
    success = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
    
    if not success:
        raise Exception(f"ShellExecuteEx falló (código {ctypes.GetLastError()})")
    
    if sei.hProcess:
        # Esperar a que el proceso termine
        ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, INFINITE)
        
        # Obtener el código de salida
        exit_code = ctypes.wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
        
        return exit_code.value
    return 0


# ═══════════════════════════════════════════════════
#  Robocopy — Parsing de salida y optimización
# ═══════════════════════════════════════════════════

# Regex para parsear la salida de Robocopy
# Con /BYTES /NP, las líneas tienen este formato:
#   "          New File              12345        archivo.txt"
# Sin /BYTES:  "  100%        New File   1.2 m   archivo.txt"
RE_ROBOCOPY_FILE = re.compile(
    r'^\s*(?:\d+(?:\.\d+)?%\s+)?'
    r'(?:New File|Newer|Older|Changed|Modified|Extra File|Lonely|Tweaked)\s+'
    r'(\d+(?:\.\d+)?)\s*([kmgt]?)\s+(.+)$',
    re.IGNORECASE
)

def _parse_robocopy_size(num_str, unit_str):
    """Convierte el tamaño de archivo de Robocopy a bytes."""
    val = float(num_str)
    unit = unit_str.lower()
    if unit == 'k':   return int(val * 1024)
    elif unit == 'm': return int(val * 1024 * 1024)
    elif unit == 'g': return int(val * 1024 * 1024 * 1024)
    elif unit == 't': return int(val * 1024 * 1024 * 1024 * 1024)
    else:             return int(val)


def _read_robocopy_output(process, progress_state, lock):
    """Hilo que lee stdout de Robocopy, acumula bytes copiados, y logea a consola."""
    try:
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            
            # Intentar parsear como línea de archivo copiado
            match = RE_ROBOCOPY_FILE.match(line)
            if match:
                file_size = _parse_robocopy_size(match.group(1), match.group(2))
                with lock:
                    progress_state['bytes_copied'] += file_size
                    progress_state['files_copied'] += 1
                continue
            
            # Filtrar líneas de ruido de robocopy
            stripped = line.strip()
            if not stripped:
                continue
            if 'ROBOCOPY     ::' in stripped or '---' in stripped:
                continue
            if stripped.startswith('Opciones'):
                continue
            if re.match(r'^\s*\d+(\.\d+)?%\s*$', stripped):
                continue
                
            # Logear el resto a la consola
            call_js('add_log', stripped, 'normal')
    except Exception:
        pass


def get_optimal_robocopy_params(src_path, dst_path):
    """Determina los parámetros óptimos de Robocopy según el tipo de disco origen/destino."""
    disk_map = get_disk_types_map()
    
    src_drive = os.path.splitdrive(src_path)[0] + '\\'
    dst_drive = os.path.splitdrive(dst_path)[0] + '\\'
    
    src_label = disk_map.get(src_drive, 'Desconocido')
    dst_label = disk_map.get(dst_drive, 'Desconocido')
    
    def classify(drive_path, label):
        label_lower = label.lower()
        if 'nvme' in label_lower:
            return 'fast'
        elif 'ssd' in label_lower:
            return 'fast'
        elif 'hdd' in label_lower:
            return 'medium'
            
        # Fallback por tamaño: si es un USB pero tiene más de 110 GB,
        # es muy probable que sea un disco HDD/SSD externo de alta velocidad, no un pendrive lento.
        try:
            usage = psutil.disk_usage(drive_path)
            total_gb = usage.total / (1024**3)
            if total_gb > 110:
                return 'medium'
        except Exception:
            pass
            
        if 'usb' in label_lower or 'extraíble' in label_lower or 'extraible' in label_lower:
            return 'slow'
        else:
            return 'medium'
    
    src_class = classify(src_drive, src_label)
    dst_class = classify(dst_drive, dst_label)
    
    mt = 8
    extra_flags = []
    note = 'Configuración estándar'
    
    if src_class == 'fast' and dst_class == 'fast':
        mt = 16
        extra_flags = ['/J']
        note = 'Máximo paralelismo (SSD/NVMe ↔ SSD/NVMe)'
    elif src_class == 'fast' and dst_class == 'medium':
        mt = 4
        note = 'HDD destino limita paralelismo'
    elif src_class == 'fast' and dst_class == 'slow':
        mt = 2
        note = 'USB destino limita velocidad'
    elif src_class == 'medium' and dst_class == 'fast':
        mt = 4
        note = 'HDD origen limita lectura'
    elif src_class == 'medium' and dst_class == 'medium':
        mt = 2
        note = 'Ambos discos mecánicos — bajo paralelismo'
    elif src_class == 'medium' and dst_class == 'slow':
        mt = 2
        note = 'HDD→USB — velocidad limitada'
    elif src_class == 'slow' and dst_class == 'fast':
        mt = 4
        note = 'USB origen limita lectura'
    elif src_class == 'slow' and dst_class == 'medium':
        mt = 2
        note = 'USB→HDD — velocidad limitada'
    elif src_class == 'slow' and dst_class == 'slow':
        mt = 2
        note = 'USB↔USB — velocidad mínima'
    
    return {
        'mt': mt,
        'extra_flags': extra_flags,
        'src_label': src_label,
        'dst_label': dst_label,
        'src_drive': src_drive,
        'dst_drive': dst_drive,
        'optimization_note': note
    }


# ═══════════════════════════════════════════════════
#  Variables globales de control de transferencia
# ═══════════════════════════════════════════════════

current_process = None
is_cancelled = False

# Variables globales de Credenciales
ADMIN_PASSWORD = None
CURRENT_INSTALLATION = None
admin_password_event = threading.Event()


def execute_robocopy(src, dst, file_filter=None, initial_dst_size=0, global_total_size=None, robocopy_params=None, completed_bytes=0):
    """Ejecuta Robocopy y monitorea el progreso parseando su salida stdout."""
    global current_process, is_cancelled
    is_cancelled = False
    
    if robocopy_params is None:
        robocopy_params = {'mt': 8, 'extra_flags': []}
    
    mt_value = robocopy_params.get('mt', 8)
    extra_flags = robocopy_params.get('extra_flags', [])
    
    is_file = os.path.isfile(src)
    src_dir = os.path.dirname(src) if is_file else src
    file_to_copy = os.path.basename(src) if is_file else ""
    
    base_flags = [f"/MT:{mt_value}", "/R:1", "/W:1", "/NP", "/BYTES", "/XA:O", "/XJD", "/XJF"] + extra_flags
    
    if file_filter:
        file_path = os.path.join(src_dir, file_filter)
        total_size = os.path.getsize(file_path) if os.path.exists(file_path) else 1
        cmd = ["robocopy", src_dir, dst, file_filter] + base_flags
    elif is_file:
        total_size = os.path.getsize(src)
        cmd = ["robocopy", src_dir, dst, file_to_copy] + base_flags
    else:
        total_size = get_dir_size(src)
        cmd = ["robocopy", src, dst, "/E"] + base_flags

    creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    start_time = time.time()
    
    progress_state = {'bytes_copied': 0, 'files_copied': 0}
    lock = threading.Lock()
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding='utf-8', errors='replace', creationflags=creationflags)
    current_process = process
    
    reader_thread = threading.Thread(target=_read_robocopy_output, args=(process, progress_state, lock), daemon=True)
    reader_thread.start()
    
    # Hilo de monitoreo del tamaño físico en el destino (para archivos grandes o backups pesados)
    def monitor_physical_progress():
        init_size = get_dir_size(dst)
        consecutive_slow_runs = 0
        while process.poll() is None and not is_cancelled:
            start_t = time.time()
            current_size = get_dir_size(dst)
            duration = time.time() - start_t
            
            # Si el escaneo es muy lento (más de 150ms), incrementamos el contador
            if duration > 0.150:
                consecutive_slow_runs += 1
            else:
                consecutive_slow_runs = 0
                
            delta = current_size - init_size
            if delta > 0:
                with lock:
                    if delta > progress_state['bytes_copied']:
                        progress_state['bytes_copied'] = delta
                        
            # Si es recurrentemente lento (ej. miles de archivos pequeños), dejamos de monitorear
            if consecutive_slow_runs >= 3:
                break
            time.sleep(1.0)

    monitor_thread = threading.Thread(target=monitor_physical_progress, daemon=True)
    monitor_thread.start()
    
    while process.poll() is None:
        if global_total_size and global_total_size > 0:
            with lock:
                current_copied = progress_state['bytes_copied']
            net_copied = max(0, current_copied)
            percent = min(99.9, ((completed_bytes + net_copied) / global_total_size) * 100)
            elapsed = time.time() - start_time
            if elapsed > 0:
                speed_bps = net_copied / elapsed
                remaining_bytes = max(0, global_total_size - (completed_bytes + net_copied))
                eta_sec = remaining_bytes / speed_bps if speed_bps > 0 else 0
                speed_mb = speed_bps / (1024 * 1024)
                call_js('update_progress', f"{percent:.1f}", f"{speed_mb:.1f} MB/s", int(eta_sec))
        elif total_size > 0:
            with lock:
                current_copied = progress_state['bytes_copied']
            net_copied = max(0, current_copied)
            percent = min(100.0, (net_copied / total_size) * 100)
            elapsed = time.time() - start_time
            if elapsed > 0:
                speed_bps = net_copied / elapsed
                remaining_bytes = max(0, total_size - net_copied)
                eta_sec = remaining_bytes / speed_bps if speed_bps > 0 else 0
                speed_mb = speed_bps / (1024 * 1024)
                call_js('update_progress', f"{percent:.1f}", f"{speed_mb:.1f} MB/s", int(eta_sec))
        time.sleep(0.5)
    
    reader_thread.join(timeout=5)
    process.wait()
    current_process = None
    duration = time.time() - start_time
    
    if not global_total_size and process.returncode is not None and 0 <= process.returncode <= 7:
        call_js('update_progress', "100.0", "Completado", 0)
        
    return process.returncode, duration


def run_pipeline(profile_name, src, dst):
    try:
        pipeline_file = None
        for p_dir in get_pipelines_search_paths():
            potential_file = os.path.join(p_dir, f"{profile_name.lower()}.json")
            if os.path.exists(potential_file):
                pipeline_file = potential_file
                break

        steps = []
        if profile_name not in ["manual", "backup"] and pipeline_file and os.path.exists(pipeline_file):
            with open(pipeline_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                steps = config.get("steps", [])
        else:
            steps = [{"type": "copy", "description": "Copia manual de archivos", "fail_on_error": True}]

        total_duration = 0
        
        # Detectar tipos de disco y calcular parámetros óptimos
        effective_src = src[0] if isinstance(src, list) and len(src) > 0 else src
        robocopy_params = get_optimal_robocopy_params(effective_src, dst)
        
        # Log informativo de tipo de disco
        call_js('add_log', "\u2550" * 40, "header")
        call_js('add_log', f"\U0001F4C0 Origen: {robocopy_params['src_label']} [{robocopy_params['src_drive']}]", "normal")
        call_js('add_log', f"\U0001F4BE Destino: {robocopy_params['dst_label']} [{robocopy_params['dst_drive']}]", "normal")
        call_js('add_log', f"\u26A1 Optimización: /MT:{robocopy_params['mt']}{' /J' if '/J' in robocopy_params.get('extra_flags', []) else ''} — {robocopy_params['optimization_note']}", "success")
        call_js('add_log', "\u2550" * 40, "header")
        
        for step in steps:
            call_js('add_log', f"--- Ejecutando paso: {step.get('description', step.get('type'))} ---", "header")
            if step["type"] == "copy":
                file_filter = step.get("file_filter", None)
                
                if profile_name in ["manual", "backup"] and isinstance(src, list):
                    global_total_size = get_dir_size(src)
                    completed_bytes = 0
                    for item in src:
                        item_size = get_dir_size(item)
                        is_file = os.path.isfile(item)
                        if is_file:
                            rc, dur = execute_robocopy(item, dst, None, 0, global_total_size, robocopy_params, completed_bytes)
                        else:
                            item_name = os.path.basename(os.path.normpath(item))
                            item_dst = os.path.join(dst, item_name)
                            rc, dur = execute_robocopy(item, item_dst, None, 0, global_total_size, robocopy_params, completed_bytes)
                        completed_bytes += item_size
                        total_duration += dur
                        if is_cancelled:
                            raise Exception("Transferencia cancelada por el usuario")
                    call_js('update_progress', "100.0", "Completado", 0)
                else:
                    rc, dur = execute_robocopy(src, dst, file_filter, robocopy_params=robocopy_params)
                    total_duration += dur
                    if is_cancelled:
                        raise Exception("Transferencia cancelada por el usuario")
                    
            elif step["type"] == "admin_install" or step["type"] == "installer":
                exe_path = os.path.join(dst, step.get("executable", ""))
                exe_dir = os.path.dirname(exe_path)
                args = step.get("arguments", "")
                
                if not os.path.exists(exe_path):
                    call_js('add_log', f"No se encontró el instalador: {exe_path}", "error")
                    if step.get("fail_on_error", True): raise Exception("Instalador no encontrado")
                    continue
                
                requires_admin = (step["type"] == "admin_install")
                
                if not requires_admin:
                    call_js('add_log', f"Ejecutando: {exe_path} {args}", "normal")
                    import shlex
                    popen_args = [exe_path] + shlex.split(args)
                    if exe_path.lower().endswith(".msi"):
                        popen_args = ["msiexec.exe", "/i", exe_path] + shlex.split(args)

                    try:
                        proc = subprocess.Popen(popen_args, cwd=exe_dir)
                        proc.wait()
                        if proc.returncode != 0 and step.get("fail_on_error", True):
                            raise Exception(f"Instalador falló con código {proc.returncode}")
                        continue
                    except OSError as e:
                        if getattr(e, 'winerror', None) == 740:
                            requires_admin = True
                        else:
                            raise
                
                if requires_admin:
                    call_js('add_log', f"Ejecutando como ADMIN: {os.path.basename(exe_path)}", "warning")
                    
                    used_creds = False
                    exit_code = -1
                    creds_path = os.path.join(get_app_profile_dir(), "admin_creds.json")
                    if os.path.exists(creds_path):
                        try:
                            with open(creds_path, "r", encoding="utf-8") as f:
                                creds = json.load(f)
                                username = creds.get("username")
                                password = creds.get("password")
                                if username and password:
                                    call_js('add_log', f"Usando credenciales de administrador guardadas (Usuario: {username})...", "warning")
                                    u_esc = username.replace("'", "''")
                                    p_esc = password.replace("'", "''")
                                    exe_esc = exe_path.replace("'", "''")
                                    args_esc = args.replace("'", "''")
                                    exe_dir_esc = exe_dir.replace("'", "''")
                                    
                                    if exe_path.lower().endswith(".msi"):
                                        cmd_file = "msiexec.exe"
                                        cmd_args = f'/i "{exe_esc}" {args_esc}'
                                    else:
                                        cmd_file = exe_esc
                                        cmd_args = args_esc
                                        
                                    ps_script = f"$sec = ConvertTo-SecureString '{p_esc}' -AsPlainText -Force; $cred = New-Object System.Management.Automation.PSCredential ('{u_esc}', $sec); Start-Process -FilePath '{cmd_file}' -ArgumentList '{cmd_args}' -Credential $cred -WorkingDirectory '{exe_dir_esc}' -NoNewWindow -Wait"
                                    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                                    proc = subprocess.run(['powershell', '-NoProfile', '-Command', ps_script], creationflags=flags)
                                    exit_code = proc.returncode
                                    call_js('add_log', f"Instalador finalizado con código: {exit_code}", "success" if exit_code == 0 else "warning")
                                    used_creds = True
                        except Exception as e:
                            call_js('add_log', f"Error ejecutando con credenciales guardadas: {str(e)}", "error")
                    
                    if not used_creds:
                        call_js('add_log', "Autoriza en la ventana de Windows (UAC)...", "warning")
                        try:
                            exit_code = _run_as_admin_and_wait(exe_path, args, exe_dir)
                            call_js('add_log', f"Instalador finalizado con código: {exit_code}", "success" if exit_code == 0 else "warning")
                        except Exception as e:
                            if step.get("fail_on_error", True):
                                raise
                                
                    if exit_code != 0 and step.get("fail_on_error", True):
                        raise Exception(f"Instalador falló con código {exit_code}")



        mins, secs = divmod(int(total_duration), 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        
        # Calcular estadísticas detalladas de la copia para el dashboard
        try:
            global_total_size = get_dir_size(src)
            if global_total_size >= (1024**3):
                size_str = f"{global_total_size / (1024**3):.2f} GB"
            elif global_total_size >= (1024**2):
                size_str = f"{global_total_size / (1024**2):.2f} MB"
            elif global_total_size >= 1024:
                size_str = f"{global_total_size / 1024:.2f} KB"
            else:
                size_str = f"{global_total_size} B"
                
            avg_speed_str = "N/A"
            if total_duration > 0 and global_total_size > 0:
                avg_speed_mb = (global_total_size / total_duration) / (1024 * 1024)
                avg_speed_str = f"{avg_speed_mb:.2f} MB/s"
        except Exception:
            size_str = "Desconocido"
            avg_speed_str = "N/A"

        op_type = "Transferencia de archivos"
        if profile_name == "backup":
            op_type = "Backup Rápido"
        elif profile_name != "manual":
            op_type = f"Instalación ({profile_name})"

        disk_flow = f"{robocopy_params.get('src_label', 'Desconocido')} -> {robocopy_params.get('dst_label', 'Desconocido')}"

        details_data = {
            "op_type": op_type,
            "disk_flow": disk_flow,
            "avg_speed": avg_speed_str,
            "total_size": size_str,
            "error_msg": ""
        }
        
        has_exe = check_has_executables(dst)
        write_audit_log(profile_name, src, dst, time_str, "Success", json.dumps(details_data, ensure_ascii=False))
        call_js('transfer_complete', True, f"Pipeline completado en {time_str}.", has_exe)
        
    except Exception as e:
        # Registrar fallo con detalles JSON
        try:
            details_data = {
                "op_type": op_type if 'op_type' in locals() else "Operación",
                "disk_flow": disk_flow if 'disk_flow' in locals() else "Desconocido",
                "avg_speed": "N/A",
                "total_size": size_str if 'size_str' in locals() else "N/A",
                "error_msg": str(e)
            }
            error_details = json.dumps(details_data, ensure_ascii=False)
        except Exception:
            error_details = str(e)
            
        write_audit_log(profile_name, src, dst, "N/A", "Error", error_details)
        call_js('transfer_complete', False, f"Error en pipeline: {str(e)}", False)



def monitor_disks():
    """Monitorea cambios en los discos conectados y avisa a la interfaz web."""
    last_disks = set()
    for p in psutil.disk_partitions(all=False):
        if p.fstype: last_disks.add(p.device)
            
    while True:
        time.sleep(2)
        current_disks = set()
        for p in psutil.disk_partitions(all=False):
            if p.fstype: current_disks.add(p.device)
                
        if current_disks != last_disks:
            last_disks = current_disks
            try:
                call_js('trigger_reload_disks')
            except Exception:
                pass


# ═══════════════════════════════════════════════════
#  Clase API — Expone funciones al frontend JS
# ═══════════════════════════════════════════════════

class Api:
    """Todos los métodos de esta clase quedan expuestos como
       window.pywebview.api.<método> en JavaScript."""

    def get_disk_types_map_async(self):
        return get_disk_types_map()

    def get_disks(self):
        """Devuelve la lista de discos disponibles."""
        disks = []
        for p in psutil.disk_partitions(all=False):
            if p.fstype:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    is_removable = 'removable' in p.opts.lower()
                    drive_type = "USB / Extraíble" if is_removable else "Disco Fijo"
                    free_gb = f"{usage.free / (1024**3):.2f} GB"
                    total_gb = f"{usage.total / (1024**3):.2f} GB"
                    disks.append({
                        "device": p.device,
                        "type": drive_type,
                        "free": usage.free,
                        "total": usage.total,
                        "free_gb": free_gb,
                        "total_gb": total_gb
                    })
                except Exception:
                    pass
        return disks

    def select_folder(self):
        """Abre el diálogo nativo de selección de carpetas."""
        global _window
        try:
            result = _window.create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                return os.path.normpath(result[0])
        except Exception as e:
            print(f"Error select_folder: {e}")
        return None

    def select_files(self):
        """Abre el diálogo nativo para seleccionar múltiples archivos."""
        global _window
        try:
            result = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
            if result:
                return [os.path.normpath(f) for f in result]
        except Exception as e:
            print(f"Error select_files: {e}")
        return []

    def get_dashboard_stats(self):
        return database.get_stats()

    def select_file(self):
        """Abre el diálogo nativo para seleccionar un único archivo."""
        global _window
        try:
            result = _window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
            if result:
                if isinstance(result, (list, tuple)):
                    return os.path.normpath(result[0])
                return os.path.normpath(result)
        except Exception as e:
            print(f"Error select_file: {e}")
        return None

    def find_profile_folder(self, profile_name):
        """Busca en todas las unidades conectadas una carpeta que coincida con el perfil."""
        try:
            pipeline_file = None
            for p_dir in get_pipelines_search_paths():
                potential_file = os.path.join(p_dir, f"{profile_name.lower()}.json")
                if os.path.exists(potential_file):
                    pipeline_file = potential_file
                    break
                    
            if not pipeline_file or not os.path.exists(pipeline_file):
                return None
                
            with open(pipeline_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                folder_to_find = config.get("source_folder_name") or config.get("expected_src_suffix")
        except Exception:
            return None

        if not folder_to_find:
            return None
            
        drives = [p.mountpoint for p in psutil.disk_partitions(all=False) if p.fstype]
        
        # Filtrar solo memorias USB (GetDriveTypeW == 2 es REMOVABLE)
        usb_drives = [d for d in drives if ctypes.windll.kernel32.GetDriveTypeW(d) == 2]
        other_drives = [d for d in drives if d not in usb_drives]
        
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        if os.path.exists(desktop_path):
            other_drives.append(desktop_path)
            
        ordered_drives = usb_drives + other_drives

        for drive in ordered_drives:
            try:
                # Quitar letra de unidad si existe para buscar relativamente en cada unidad
                if len(folder_to_find) >= 2 and folder_to_find[1] == ':' and folder_to_find[0].isalpha():
                    clean_folder = folder_to_find[2:]
                else:
                    clean_folder = folder_to_find
                clean_folder = clean_folder.lstrip("\\/")
                full_path = os.path.join(drive, clean_folder)
                if os.path.isdir(full_path):
                    return full_path
            except Exception:
                continue
        return None

    def get_available_profiles(self):
        """Devuelve la lista de perfiles JSON encontrados en todas las carpetas de perfiles configuradas."""
        profiles_dict = {}
        
        # Cargar perfiles eliminados (soft-deleted)
        deleted_list_path = os.path.join(get_app_profile_dir(), "deleted_profiles.json")
        deleted_ids = set()
        if os.path.exists(deleted_list_path):
            try:
                with open(deleted_list_path, "r", encoding="utf-8") as f:
                    deleted_ids = set(json.load(f))
            except Exception:
                pass

        for p_dir in get_pipelines_search_paths():
            try:
                if not os.path.exists(p_dir):
                    continue
                for filename in os.listdir(p_dir):
                    if filename.endswith(".json"):
                        p_id = filename.replace(".json", "")
                        
                        # Omitir si ha sido eliminado por el usuario
                        if p_id in deleted_ids:
                            continue
                            
                        filepath = os.path.join(p_dir, filename)
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                config = json.load(f)
                                profiles_dict[p_id] = {
                                    "id": p_id,
                                    "name": config.get("profile_name", filename),
                                    "is_custom": True  # Todos los perfiles se pueden eliminar ahora
                                }
                        except Exception as e:
                            print(f"Error leyendo {filename} en {p_dir}: {e}")
            except Exception as e:
                print(f"Error accediendo a {p_dir}: {e}")
        return sorted(list(profiles_dict.values()), key=lambda x: x["name"])

    def delete_custom_profile(self, profile_id):
        """Elimina un perfil personalizado o registra un perfil predefinido como eliminado."""
        try:
            # 1. Intentar eliminar físicamente de pipelines escribibles si existe
            pipelines_dir = get_writable_pipelines_dir()
            filepath = os.path.join(pipelines_dir, f"{profile_id.lower()}.json")
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                    
            # 2. Registrar en la lista de exclusión local
            deleted_list_path = os.path.join(get_app_profile_dir(), "deleted_profiles.json")
            
            deleted_profiles = []
            if os.path.exists(deleted_list_path):
                try:
                    with open(deleted_list_path, "r", encoding="utf-8") as f:
                        deleted_profiles = json.load(f)
                except Exception:
                    pass
                    
            if profile_id not in deleted_profiles:
                deleted_profiles.append(profile_id)
                with open(deleted_list_path, "w", encoding="utf-8") as f:
                    json.dump(deleted_profiles, f)
                    
            return {"success": True, "message": "Perfil eliminado exitosamente."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def set_admin_password(self, pwd):
        global ADMIN_PASSWORD
        ADMIN_PASSWORD = pwd
        admin_password_event.set()
        return True

    def resume_installation(self):
        admin_password_event.set()

    def scan_usb_installers(self):
        """Busca la carpeta INSTALADORES en las unidades extraíbles"""
        try:
            drives = [p.mountpoint for p in psutil.disk_partitions(all=False) if p.fstype]
            usb_drives = [d for d in drives if ctypes.windll.kernel32.GetDriveTypeW(d) == 2]
            other_drives = [d for d in drives if d not in usb_drives and not d.startswith("C:")]
            
            for drive in usb_drives + other_drives:
                installers_path = os.path.join(drive, "INSTALADORES")
                if os.path.isdir(installers_path):
                    return {"success": True, "source_path": installers_path}
                    
            return {"success": False, "message": "No se encontró ninguna carpeta INSTALADORES en las memorias USB conectadas."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def launch_admin_installer(self, dest_folder):
        """Busca ejecutables en la carpeta destino y los lista."""
        try:
            executables = []
            for root, dirs, files in os.walk(dest_folder):
                for file in files:
                    if file.lower().endswith(('.exe', '.msi')):
                        name_lower = file.lower()
                        if any(kw in name_lower for kw in ['setup', 'install', 'installer', 'spkb']):
                            executables.append(os.path.join(root, file))
            
            if not executables:
                for root, dirs, files in os.walk(dest_folder):
                    for file in files:
                        if file.lower().endswith(('.exe', '.msi')):
                            executables.append(os.path.join(root, file))
            
            if not executables:
                call_js('add_log', "No se encontraron ejecutables en la carpeta destino.", "error")
                return False
            
            call_js('show_installer_list', executables)
            return True
        except Exception as e:
            print(f"Error buscando instaladores: {e}")
        return False

    def run_single_installer_as_admin(self, exe_path):
        """Lanza un instalador específico como administrador usando UAC nativo o credenciales guardadas."""
        try:
            exe_dir = os.path.dirname(exe_path)
            call_js('add_log', f"Lanzando como administrador: {exe_path}", "warning")
            
            used_creds = False
            creds_path = os.path.join(get_app_profile_dir(), "admin_creds.json")
            if os.path.exists(creds_path):
                try:
                    with open(creds_path, "r", encoding="utf-8") as f:
                        creds = json.load(f)
                        username = creds.get("username")
                        password = creds.get("password")
                        if username and password:
                            call_js('add_log', f"Usando credenciales de administrador guardadas (Usuario: {username})...", "warning")
                            u_esc = username.replace("'", "''")
                            p_esc = password.replace("'", "''")
                            exe_esc = exe_path.replace("'", "''")
                            exe_dir_esc = exe_dir.replace("'", "''")
                            
                            if exe_path.lower().endswith(".msi"):
                                cmd_file = "msiexec.exe"
                                cmd_args = f'/i "{exe_esc}"'
                            else:
                                cmd_file = exe_esc
                                cmd_args = ""
                                
                            ps_script = f"$sec = ConvertTo-SecureString '{p_esc}' -AsPlainText -Force; $cred = New-Object System.Management.Automation.PSCredential ('{u_esc}', $sec); Start-Process -FilePath '{cmd_file}' -ArgumentList '{cmd_args}' -Credential $cred -WorkingDirectory '{exe_dir_esc}' -NoNewWindow -Wait"
                            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            proc = subprocess.run(['powershell', '-NoProfile', '-Command', ps_script], creationflags=flags)
                            call_js('add_log', f"Instalador finalizado con código: {proc.returncode}", "success" if proc.returncode == 0 else "warning")
                            used_creds = True
                except Exception as e:
                    call_js('add_log', f"Error con credenciales: {str(e)}", "error")
                    
            if not used_creds:
                call_js('add_log', "Autoriza en la ventana de Windows (UAC)...", "warning")
                _run_as_admin_and_wait(exe_path, "", exe_dir)
                call_js('add_log', "Instalador finalizado.", "success")
            return True
        except Exception as e:
            call_js('add_log', f"Error: {str(e)}", "error")
            return False

    def cancel_transfer(self):
        global current_process, is_cancelled
        is_cancelled = True
        if current_process:
            try:
                current_process.kill()
                call_js('add_log', "--- TRANSFERENCIA CANCELADA POR EL USUARIO ---", 'error')
                return True
            except Exception as e:
                print(f"Error cancelando: {e}")
        return False

    def calculate_transfer_eta(self, src, dst):
        """Calcula el peso total y un ETA estimado antes de transferir."""
        try:
            if isinstance(src, list):
                total_size = get_dir_size(src)
            else:
                total_size = get_dir_size(src)
                
            free_space = shutil.disk_usage(dst).free
            if total_size > (free_space * 0.98):
                return {"success": False, "message": "Error: No hay suficiente espacio en el disco destino."}
                
            # Clasificar velocidad destino de forma rápida
            drive = os.path.splitdrive(dst)[0] + "\\"
            disk_types = get_disk_types_map()
            dst_label = disk_types.get(drive, "").lower()
            
            # Obtener velocidad estimada realista
            estimated_speed_bps = 35 * 1024 * 1024 # default 35 MB/s
            if 'usb' in dst_label or 'extraíble' in dst_label or 'extraible' in dst_label:
                estimated_speed_bps = 4.2 * 1024 * 1024 # 4.2 MB/s para memorias USB estándar
            elif 'ssd' in dst_label:
                estimated_speed_bps = 90 * 1024 * 1024 # 90 MB/s para SSD
            elif 'hdd' in dst_label:
                estimated_speed_bps = 25 * 1024 * 1024 # 25 MB/s para HDD
                
            eta_seconds = total_size / estimated_speed_bps if estimated_speed_bps > 0 else 0
            
            if total_size >= (1024**3):
                size_str = f"{total_size / (1024**3):.2f} GB"
            else:
                size_str = f"{total_size / (1024**2):.2f} MB"
                
            if eta_seconds > 0:
                mins, secs = divmod(int(eta_seconds), 60)
                time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            else:
                time_str = "0s"
                
            return {
                "success": True,
                "size_bytes": total_size,
                "size_str": size_str,
                "eta_sec": int(eta_seconds),
                "eta_str": time_str
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_system_info(self):
        """Devuelve información del sistema como el nombre del dispositivo y usuario actual."""
        import socket
        import getpass
        try:
            hostname = socket.gethostname()
            username = os.environ.get("USERNAME") or getpass.getuser() or os.getlogin()
            user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
            return {
                "hostname": hostname,
                "username": username,
                "user_profile": os.path.normpath(user_profile)
            }
        except Exception as e:
            return {
                "hostname": "Desconocido",
                "username": "Usuario",
                "user_profile": ""
            }

    def get_backup_folders_status(self):
        """Resuelve el estado de las carpetas de respaldo estándar del usuario."""
        user_profile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        
        candidates = {
            "Desktop": ["Desktop", "Escritorio"],
            "Documents": ["Documents", "Documentos"],
            "Downloads": ["Downloads", "Descargas"],
            "Pictures": ["Pictures", "Imágenes", "Imagenes"],
            "Videos": ["Videos", "Vídeos"]
        }
        
        resolved = []
        for key, folders in candidates.items():
            found_path = None
            for folder in folders:
                p = os.path.join(user_profile, folder)
                if os.path.isdir(p):
                    found_path = p
                    break
            if not found_path:
                found_path = os.path.join(user_profile, folders[0])
            
            exists = os.path.isdir(found_path)
            resolved.append({
                "id": key,
                "name": folders[1] if len(folders) > 1 else folders[0],
                "path": os.path.normpath(found_path),
                "exists": exists,
                "size_str": "Calculando..." if exists else "0 B"
            })
            
        # Lanzar cálculo de tamaños en segundo plano
        thread = threading.Thread(target=self._calculate_backup_sizes_async, args=(resolved,))
        thread.daemon = True
        thread.start()
        
        return resolved

    def _calculate_backup_sizes_async(self, resolved_folders):
        """Calcula el tamaño de cada carpeta de respaldo en segundo plano y actualiza el frontend."""
        for folder in resolved_folders:
            if folder["exists"]:
                try:
                    size_bytes = get_dir_size(folder["path"])
                    if size_bytes >= (1024**3):
                        size_str = f"{size_bytes / (1024**3):.2f} GB"
                    elif size_bytes >= (1024**2):
                        size_str = f"{size_bytes / (1024**2):.2f} MB"
                    elif size_bytes >= 1024:
                        size_str = f"{size_bytes / 1024:.2f} KB"
                    else:
                        size_str = f"{size_bytes} B"
                except Exception:
                    size_str = "Error"
                
                # Actualizar el frontend
                call_js('update_backup_folder_size', folder["id"], size_str)


    def create_custom_profile(self, data):
        """Crea un archivo JSON de perfil personalizado en la carpeta pipelines/"""
        try:
            name = data.get("name")
            source_folder = data.get("folder")
            installers = data.get("installers", [])

            # Normalizar rutas
            source_folder = os.path.normpath(source_folder)
            
            # Generar un ID de perfil limpio y único
            import string
            profile_id = ''.join(c for c in name if c in (string.ascii_letters + string.digits + "_-")).lower()
            if not profile_id:
                profile_id = f"perfil_{int(time.time())}"
                
            steps = [
                {
                    "type": "copy",
                    "description": f"Copiando {name} a local",
                    "fail_on_error": True
                }
            ]

            # Agregar un paso de instalación secuencial para cada instalador
            for idx, inst in enumerate(installers):
                exe = inst.get("exe")
                args = inst.get("args", "")
                req_admin = inst.get("requireAdmin", True)
                
                steps.append({
                    "type": "admin_install" if req_admin else "installer",
                    "description": f"Instalando {name} - Paso {idx + 1} ({os.path.basename(exe)})",
                    "executable": exe,
                    "arguments": args,
                    "fail_on_error": True
                })

            profile_data = {
                "profile_name": name,
                "source_folder_name": source_folder,
                "steps": steps
            }
            
            pipelines_dir = get_writable_pipelines_dir()
            filepath = os.path.join(pipelines_dir, f"{profile_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=4, ensure_ascii=False)
                
            return {"success": True, "message": f"Perfil '{name}' creado exitosamente.", "profile_id": profile_id}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def save_admin_credentials(self, data):
        """Guarda las credenciales de administrador de forma segura (archivo JSON local)."""
        try:
            username = data.get("username")
            password = data.get("password")
            save_data = {"username": username, "password": password}
            filepath = os.path.join(get_app_profile_dir(), "admin_creds.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(save_data, f)
            return {"success": True, "message": "Credenciales de administrador guardadas exitosamente."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def delete_admin_credentials(self):
        """Borra las credenciales guardadas."""
        try:
            filepath = os.path.join(get_app_profile_dir(), "admin_creds.json")
            if os.path.exists(filepath):
                os.remove(filepath)
            return {"success": True, "message": "Credenciales eliminadas exitosamente."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_admin_credentials(self):
        """Obtiene si existen credenciales guardadas y el usuario."""
        filepath = os.path.join(get_app_profile_dir(), "admin_creds.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {"saved": True, "username": data.get("username", "")}
            except Exception:
                pass
        return {"saved": False, "username": ""}

    def start_transfer(self, profile_name, src, dst, custom_backup_name=""):
        """Inicia el proceso de transferencia en un hilo separado."""
        global _progress_window
        try:
            src_size = get_dir_size(src)
            free_space = shutil.disk_usage(dst).free
            if src_size > (free_space * 0.98):
                call_js('transfer_complete', False, "Error: No hay suficiente espacio en el disco destino.", False)
                return
        except Exception as e:
            print(f"Error comprobando espacio: {e}")

        folder_name = ""
        if profile_name == "backup":
            if custom_backup_name and custom_backup_name.strip():
                clean_name = re.sub(r'[\\/*?:"<>|]', "", custom_backup_name.strip())
                real_dst = os.path.join(dst, clean_name)
            else:
                import socket
                hostname = socket.gethostname()
                clean_hostname = re.sub(r'[\\/*?:"<>|]', "", hostname)
                real_dst = os.path.join(dst, f"Respaldo_{clean_hostname}")
        elif isinstance(src, str):
            folder_name = os.path.basename(os.path.normpath(src))
            real_dst = os.path.join(dst, folder_name)
        else:
            real_dst = dst
            
        
        
        call_js('add_log', "=" * 40, "header")
        call_js('add_log', f"Iniciando Pipeline para: {profile_name}", "header")
        if isinstance(src, list):
            call_js('add_log', f"Origen: {len(src)} elementos manuales", "normal")
        else:
            call_js('add_log', f"Origen: {src}", "normal")
        call_js('add_log', f"Destino: {real_dst}", "normal")
        
        thread = threading.Thread(target=run_pipeline, args=(profile_name, src, real_dst))
        thread.daemon = True
        thread.start()


# ═══════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════

if __name__ == '__main__':
    api = Api()

    # Iniciar hilo de monitoreo de discos
    monitor_thread = threading.Thread(target=monitor_disks)
    monitor_thread.daemon = True
    monitor_thread.start()

    web_dir = resource_path('web')

    _window = webview.create_window(
        'Nexus v1.2.0',
        url=os.path.join(web_dir, 'index.html'),
        width=950,
        height=650,
        js_api=api,
        frameless=False,
        easy_drag=False,
        text_select=False,
    )

    webview.start()