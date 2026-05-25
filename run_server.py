import os
import sys
import webbrowser
from threading import Timer
from django.core.management import execute_from_command_line

# --- THE MAGIC SILENCER FOR --noconsole ---
class NullWriter:
    def write(self, text): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()
# ------------------------------------------

# --- ANTI-PORTABLE / SECURITY VALIDATION ---
def get_registry_value(subkey, name):
    import winreg
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for flag in (0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | flag)
                val, _ = winreg.QueryValueEx(key, name)
                winreg.CloseKey(key)
                return val
            except OSError:
                continue
    return None

def show_error_and_exit(message):
    import ctypes
    # MB_OK = 0x0, MB_ICONERROR = 0x10, MB_SYSTEMMODAL = 0x1000
    ctypes.windll.user32.MessageBoxW(0, message, "C-MAP Enterprise Security", 0x10 | 0x0 | 0x1000)
    sys.exit(1)

def verify_installation():
    # Only verify security if running as a bundled executable
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.abspath(os.path.dirname(sys.executable)).lower().rstrip('\\/')
        
        # 1. Read registered InstallPath
        install_path = get_registry_value("Software\\CMAPEnterprise", "InstallPath")
        if install_path:
            install_path = os.path.abspath(install_path).lower().rstrip('\\/')
            
        # 2. Read registered MachineID
        machine_id = get_registry_value("Software\\CMAPEnterprise", "MachineID")
        
        # 3. Read Windows unique MachineGuid
        actual_machine_guid = get_registry_value("SOFTWARE\\Microsoft\\Cryptography", "MachineGuid")
        
        # Validate existence of registry entries
        if not install_path or not machine_id or not actual_machine_guid:
            show_error_and_exit(
                "C-MAP Enterprise is not installed on this machine.\n\n"
                "Please run the official installer to install the application."
            )
            
        # Validate installation folder path
        if exe_dir != install_path:
            show_error_and_exit(
                "Security Alert: The application is running from an unauthorized folder.\n\n"
                f"Installed Path: {install_path}\n"
                f"Running Path: {exe_dir}\n\n"
                "Please run the application from the installed desktop shortcut or the official directory."
            )
            
        # Validate machine hardware binding
        if machine_id.strip().lower() != actual_machine_guid.strip().lower():
            show_error_and_exit(
                "Security Alert: Hardware mismatch detected.\n\n"
                "This copy of C-MAP Enterprise is bound to another PC.\n"
                "To prevent piracy and unauthorized sharing, running is blocked.\n\n"
                "Please run the official installer on this machine to install a legitimate copy."
            )
# -------------------------------------------
# --- DYNAMIC PORT SELECTION ---
SELECTED_PORT = 8000

def get_available_port(start_port=8000):
    import socket
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return port
            except OSError:
                port += 1
    return start_port

def open_browser():
    # Opens the browser automatically after 1.5 seconds using the dynamically selected port
    webbrowser.open_new(f'http://127.0.0.1:{SELECTED_PORT}/')

if __name__ == "__main__":
    # Check if app is properly installed before running
    verify_installation()

    # Automatically scan and find a free port starting from 8000
    SELECTED_PORT = get_available_port(8000)

    # Tell Django exactly where your project settings are!
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmap_project.settings") 
    
    # Start the browser timer
    Timer(1.5, open_browser).start()
    
    # Force Django to run on 0.0.0.0:<SELECTED_PORT> without the auto-reloader to support LAN access
    execute_from_command_line(["run_server.py", "runserver", f"0.0.0.0:{SELECTED_PORT}", "--noreload"])