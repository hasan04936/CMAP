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

def open_browser():
    # Opens the browser automatically after 1.5 seconds
    webbrowser.open_new('http://127.0.0.1:8000/')

if __name__ == "__main__":
    # Tell Django exactly where your project settings are!
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cmap_project.settings") 
    
    # Start the browser timer
    Timer(1.5, open_browser).start()
    
    # Force Django to run on localhost:8000 without the auto-reloader
    execute_from_command_line(["run_server.py", "runserver", "127.0.0.1:8000", "--noreload"])