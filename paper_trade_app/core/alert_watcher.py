import sys
import time
import json
import os
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("Watchdog")
import pdb
class JsonFileHandler(FileSystemEventHandler):
    """
    Standard Watchdog Handler: Triggers when a file is created.
    """
    def __init__(self, callback):
        self.callback = callback

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            logger.info(f"📂 New Alert Detected: {event.src_path}")
            # Tiny sleep to ensure file write is complete (prevents empty reads)
            time.sleep(0.1) 
            self.process_file(event.src_path)

    def process_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Handle new screener format (v3.3+) with top_alerts array
            if isinstance(data, dict) and 'top_alerts' in data:
                logger.info(f"📊 New format detected: {len(data.get('top_alerts', []))} alerts")
                alerts = data.get('top_alerts', [])
                for item in alerts:
                    self.callback(item)
            elif isinstance(data, list):
                # Old format: array of alerts
                for item in data:
                    self.callback(item)
            else:
                # Single alert object
                self.callback(data)
            
            # Optional: Move to 'processed' folder so we don't read it again
            # os.rename(filepath, filepath + ".bak") 
        except Exception as e:
            logger.error(f"❌ Failed to read JSON: {e}")

class AlertWatcherThread(QThread):
    # Signal: Sends the Dictionary content of the JSON to Main App
    new_alert_signal = pyqtSignal(dict)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = os.path.abspath(folder_path)
        self._stop_requested = False
        
        # Ensure directory exists
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)
            
        self.observer = Observer()

    def run(self):
        logger.info(f"👀 Watching for alerts in: {self.folder_path}")
        
        # We pass 'self.emit_signal' as the callback to the Handler
        event_handler = JsonFileHandler(self.emit_signal)
        
        self.observer.schedule(event_handler, self.folder_path, recursive=False)
        self.observer.start()
        
        # Keep the thread alive
        try:
            while not self._stop_requested:
                self.msleep(500)  # Check every 500ms
        except Exception as e:
            logger.error(f"Watchdog Error: {e}")
        finally:
            self.observer.stop()
            self.observer.join()

    def emit_signal(self, data):
        # This runs in the Watchdog thread, so we emit to Main Thread
        self.new_alert_signal.emit(data)

    def stop(self):
        """Gracefully stop the watcher thread."""
        logger.info("🛑 Stopping alert watcher...")
        self._stop_requested = True
        self.observer.stop()