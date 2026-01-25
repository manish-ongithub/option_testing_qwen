"""
Smart Options Screener v3.3 - PyQt6 GUI

A graphical interface for configuring and running the options screener.

Run with:
    python -m screener.ui.screener_gui
"""

import os
import sys
import json
import csv
import io

# Fix Qt plugin path for macOS - must be set before ANY PyQt6 imports
def _setup_qt_plugin_path():
    """Set Qt plugin path for macOS to find cocoa platform plugin."""
    if sys.platform == 'darwin':
        try:
            # Find PyQt6 installation path using multiple methods
            import importlib.util
            spec = importlib.util.find_spec('PyQt6')
            if spec and spec.origin:
                pyqt6_path = os.path.dirname(spec.origin)
                qt_plugin_path = os.path.join(pyqt6_path, 'Qt6', 'plugins')
                if os.path.exists(qt_plugin_path):
                    os.environ['QT_PLUGIN_PATH'] = qt_plugin_path
                    # Also set QT_QPA_PLATFORM_PLUGIN_PATH for the platforms subfolder
                    platforms_path = os.path.join(qt_plugin_path, 'platforms')
                    if os.path.exists(platforms_path):
                        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = platforms_path
                    # Set QT_DEBUG_PLUGINS to help diagnose issues if they occur
                    # os.environ['QT_DEBUG_PLUGINS'] = '1'
                    return
            
            # Fallback: Try to find via pip show
            import subprocess
            result = subprocess.run(
                [sys.executable, '-c', 
                 'import PyQt6; import os; print(os.path.dirname(PyQt6.__file__))'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                pyqt6_path = result.stdout.strip()
                qt_plugin_path = os.path.join(pyqt6_path, 'Qt6', 'plugins')
                if os.path.exists(qt_plugin_path):
                    os.environ['QT_PLUGIN_PATH'] = qt_plugin_path
        except Exception:
            pass

_setup_qt_plugin_path()

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCheckBox, QPushButton, QGroupBox, QScrollArea,
    QComboBox, QSpinBox, QFrame, QStatusBar, QProgressBar,
    QGridLayout, QSplitter, QMessageBox, QTabWidget, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QDialog,
    QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette

from screener.config import INDEX_SYMBOLS, STOCK_SYMBOLS, JSON_FILE


# Available strategies
STRATEGIES = [
    ("Long Call", True),
    ("Long Put", True),
    ("Bull Call Spread", False),
    ("Bear Put Spread", False),
    ("Long Straddle", False),
    ("Long Strangle", False),
]

# Time configuration options
HISTORICAL_PERIODS = ["1w", "1mo", "3mo", "6mo", "1y"]
HISTORICAL_INTERVALS = ["1d", "1h", "5m"]
HV_PERIODS = ["3mo", "6mo", "1y", "2y"]


class OpstraRefreshWorker(QThread):
    """Background worker thread for refreshing Opstra session."""
    
    finished = pyqtSignal(bool, str)  # (success, message)
    progress = pyqtSignal(str)  # status message
    
    def __init__(self, force_login=False):
        super().__init__()
        self.force_login = force_login
    
    def run(self):
        """Refresh Opstra session via browser."""
        try:
            self.progress.emit("Opening browser for Opstra login...")
            
            from screener.iv.opstra_login import refresh_opstra_session
            
            success = refresh_opstra_session(force_login=self.force_login)
            
            if success:
                self.finished.emit(True, "Opstra session refreshed successfully!")
            else:
                self.finished.emit(False, "Failed to refresh Opstra session. Using HV fallback.")
                
        except ImportError as e:
            self.finished.emit(False, f"Selenium not installed. Install with: pip install selenium webdriver-manager")
        except Exception as e:
            self.finished.emit(False, f"Error refreshing Opstra: {str(e)}")


class ScanWorker(QThread):
    """Background worker thread for running scans."""
    
    finished = pyqtSignal(int, str)  # (alert_count, message)
    progress = pyqtSignal(str)  # status message
    error = pyqtSignal(str)  # error message
    
    def __init__(self, config):
        super().__init__()
        self.config = config
    
    def run(self):
        """Execute the scan with the given configuration."""
        try:
            from screener.main import run_scan_with_config
            
            self.progress.emit("Initializing scan...")
            
            alert_count = run_scan_with_config(
                indices=self.config.get('indices', []),
                stocks=self.config.get('stocks', []),
                strategies=self.config.get('strategies', []),
                trend_period=self.config.get('trend_period', '1mo'),
                trend_interval=self.config.get('trend_interval', '1d'),
                hv_period=self.config.get('hv_period', '1y'),
                hv_window=self.config.get('hv_window', 30),
                skip_opstra=self.config.get('skip_opstra', False),
                progress_callback=self.progress.emit
            )
            
            self.finished.emit(alert_count, f"Scan complete! {alert_count} alerts generated.")
            
        except Exception as e:
            self.error.emit(str(e))


class AnalysisWorker(QThread):
    """Background worker for running alert analysis."""
    
    finished = pyqtSignal(str, str)  # (report_text, report_type)
    error = pyqtSignal(str)
    
    def __init__(self, alert_data, analysis_type='basic'):
        super().__init__()
        self.alert_data = alert_data
        self.analysis_type = analysis_type
    
    def _ensure_numeric(self, value, default=0):
        """Ensure a value is numeric, handling string formats like '60000/60400'."""
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            # Handle multi-strike format like "60000/60400"
            if '/' in value:
                try:
                    return float(value.split('/')[0].strip())
                except ValueError:
                    return default
            try:
                return float(value)
            except ValueError:
                return default
        return default
    
    def run(self):
        """Run the analysis."""
        try:
            # Ensure strike is numeric
            strike = self._ensure_numeric(self.alert_data.get('strike', 0))
            spot = self._ensure_numeric(self.alert_data.get('spot', 0))
            premium = self._ensure_numeric(self.alert_data.get('premium', 0))
            
            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            
            if self.analysis_type == 'basic':
                from alert_analyzer import analyze_alert
                
                analyze_alert(
                    symbol=self.alert_data.get('symbol', 'UNKNOWN'),
                    spot=spot,
                    strike=strike,
                    premium=premium,
                    option_type=self.alert_data.get('type', 'CE'),
                    dte=int(self._ensure_numeric(self.alert_data.get('days_to_expiry', 30))),
                    iv=self._ensure_numeric(self.alert_data.get('iv', 20)),
                    iv_percentile=self._ensure_numeric(self.alert_data.get('iv_percentile', 50)),
                    volume=int(self._ensure_numeric(self.alert_data.get('volume', 0))),
                    oi=int(self._ensure_numeric(self.alert_data.get('open_interest', 0))),
                    lot_size=int(self._ensure_numeric(self.alert_data.get('lot_size', 100))),
                    capital=50000,
                    risk_per_trade_pct=2
                )
            else:
                from enhanced_alert_analyzer import enhanced_alert_analysis
                
                enhanced_alert_analysis(
                    symbol=self.alert_data.get('symbol', 'UNKNOWN'),
                    strike=strike,
                    premium=premium,
                    option_type=self.alert_data.get('type', 'CE'),
                    dte=int(self._ensure_numeric(self.alert_data.get('days_to_expiry', 30))),
                    iv=self._ensure_numeric(self.alert_data.get('iv', 20)),
                    iv_percentile=self._ensure_numeric(self.alert_data.get('iv_percentile', 50)),
                    volume=int(self._ensure_numeric(self.alert_data.get('volume', 0))),
                    oi=int(self._ensure_numeric(self.alert_data.get('open_interest', 0))),
                    capital=50000,
                    risk_per_trade_pct=2
                )
            
            # Get captured output
            output = buffer.getvalue()
            sys.stdout = old_stdout
            
            self.finished.emit(output, self.analysis_type)
            
        except Exception as e:
            sys.stdout = old_stdout
            self.error.emit(str(e))


class ReportDialog(QDialog):
    """Dialog to display analysis reports."""
    
    def __init__(self, title, report_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(950, 750)
        self.resize(1050, 850)
        
        layout = QVBoxLayout(self)
        
        # Report text display
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        # Use a monospace font that exists on macOS
        monospace_font = QFont()
        monospace_font.setFamily("Menlo")
        monospace_font.setStyleHint(QFont.StyleHint.Monospace)
        monospace_font.setPointSize(11)
        self.report_text.setFont(monospace_font)
        self.report_text.setPlainText(report_text)
        self.report_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                padding: 10px;
            }
        """)
        layout.addWidget(self.report_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(copy_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _copy_to_clipboard(self):
        """Copy report to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report_text.toPlainText())
        QMessageBox.information(self, "Copied", "Report copied to clipboard!")


class AlertViewerTab(QWidget):
    """Tab for loading and viewing alerts with analysis reports."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.alerts = []
        self.current_alert = None
        self.analysis_worker = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the alert viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Load file section
        load_layout = QHBoxLayout()
        
        load_btn = QPushButton("📁  Load Alert File")
        load_btn.setFont(QFont("Helvetica Neue", 11))
        load_btn.setMinimumHeight(40)
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        load_btn.clicked.connect(self._load_file)
        load_layout.addWidget(load_btn)
        
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("color: #666; font-style: italic;")
        load_layout.addWidget(self.file_label, stretch=1)
        
        layout.addLayout(load_layout)
        
        # Splitter for table and details
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Alerts table
        table_group = QGroupBox("Alerts")
        table_layout = QVBoxLayout(table_group)
        
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(11)
        self.alerts_table.setHorizontalHeaderLabels([
            "Symbol", "Strategy", "Strike", "Premium", "Spot", 
            "Volume", "OI", "IV%", "DTE", "PoP%", "Tax Risk"
        ])
        self.alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.alerts_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.alerts_table.itemSelectionChanged.connect(self._on_alert_selected)
        self.alerts_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                gridline-color: #eee;
            }
            QTableWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #ddd;
                font-weight: bold;
            }
        """)
        table_layout.addWidget(self.alerts_table)
        
        splitter.addWidget(table_group)
        
        # Alert details and analysis buttons
        details_group = QGroupBox("Selected Alert Details")
        details_layout = QVBoxLayout(details_group)
        
        # Details display
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        # Use a monospace font that exists on macOS
        details_font = QFont()
        details_font.setFamily("Menlo")
        details_font.setStyleHint(QFont.StyleHint.Monospace)
        details_font.setPointSize(10)
        self.details_text.setFont(details_font)
        self.details_text.setPlainText("Select an alert from the table above to view details.")
        details_layout.addWidget(self.details_text)
        
        # Analysis buttons
        analysis_layout = QHBoxLayout()
        
        self.basic_analysis_btn = QPushButton("📋  Basic Analysis Report")
        self.basic_analysis_btn.setFont(QFont("Helvetica Neue", 11))
        self.basic_analysis_btn.setMinimumHeight(45)
        self.basic_analysis_btn.setEnabled(False)
        self.basic_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.basic_analysis_btn.clicked.connect(lambda: self._run_analysis('basic'))
        analysis_layout.addWidget(self.basic_analysis_btn)
        
        self.enhanced_analysis_btn = QPushButton("📊  Enhanced Analysis Report")
        self.enhanced_analysis_btn.setFont(QFont("Helvetica Neue", 11))
        self.enhanced_analysis_btn.setMinimumHeight(45)
        self.enhanced_analysis_btn.setEnabled(False)
        self.enhanced_analysis_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.enhanced_analysis_btn.clicked.connect(lambda: self._run_analysis('enhanced'))
        analysis_layout.addWidget(self.enhanced_analysis_btn)
        
        details_layout.addLayout(analysis_layout)
        
        splitter.addWidget(details_group)
        
        # Set splitter sizes
        splitter.setSizes([400, 250])
        
        layout.addWidget(splitter)
    
    def _load_file(self):
        """Open file dialog to load JSON or CSV alert file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Alert File",
            "",
            "Alert Files (*.json *.csv);;JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.json'):
                self._load_json(file_path)
            elif file_path.endswith('.csv'):
                self._load_csv(file_path)
            else:
                QMessageBox.warning(self, "Invalid File", "Please select a JSON or CSV file.")
                return
            
            self.file_label.setText(f"Loaded: {os.path.basename(file_path)} ({len(self.alerts)} alerts)")
            self.file_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load file:\n\n{str(e)}")
    
    def _load_json(self, file_path):
        """Load alerts from JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Handle both direct array and nested structure
        if isinstance(data, list):
            self.alerts = data
        elif isinstance(data, dict):
            # Try common keys
            if 'top_alerts' in data:
                self.alerts = data['top_alerts']
            elif 'alerts' in data:
                self.alerts = data['alerts']
            else:
                # Assume single alert
                self.alerts = [data]
        
        self._populate_table()
    
    def _load_csv(self, file_path):
        """Load alerts from CSV file."""
        self.alerts = []
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                alert = {}
                for key, value in row.items():
                    # Clean key
                    clean_key = key.strip().lower().replace(' ', '_')
                    
                    # Try to convert to number
                    try:
                        if '.' in value:
                            alert[clean_key] = float(value)
                        else:
                            alert[clean_key] = int(value)
                    except (ValueError, TypeError):
                        alert[clean_key] = value
                
                # Map common CSV field names to expected format
                if 'type' not in alert and 'strategy' in alert:
                    if 'call' in alert['strategy'].lower():
                        alert['type'] = 'CE'
                    elif 'put' in alert['strategy'].lower():
                        alert['type'] = 'PE'
                
                self.alerts.append(alert)
        
        self._populate_table()
    
    def _populate_table(self):
        """Populate the alerts table with loaded data."""
        self.alerts_table.setRowCount(0)
        
        for alert in self.alerts:
            row = self.alerts_table.rowCount()
            self.alerts_table.insertRow(row)
            
            # Get values with fallbacks
            symbol = str(alert.get('symbol', ''))
            strategy = str(alert.get('strategy', ''))
            strike = alert.get('strike', 0)
            premium = alert.get('premium', 0)
            spot = alert.get('spot', 0)
            volume = alert.get('volume', 0)
            oi = alert.get('open_interest', alert.get('oi', 0))
            iv_pct = alert.get('iv_percentile', alert.get('iv', 0))
            dte = alert.get('days_to_expiry', alert.get('dte', 0))
            
            # Get probability data if available
            prob = alert.get('probability', {})
            pop_stt = prob.get('pop_stt_adjusted', prob.get('pop_raw', '-'))
            tax_risk = prob.get('tax_risk', '-')
            
            items = [
                QTableWidgetItem(symbol),
                QTableWidgetItem(strategy),
                QTableWidgetItem(f"₹{strike:,.0f}" if isinstance(strike, (int, float)) else str(strike)),
                QTableWidgetItem(f"₹{premium:.2f}" if isinstance(premium, (int, float)) else str(premium)),
                QTableWidgetItem(f"₹{spot:,.2f}" if isinstance(spot, (int, float)) else str(spot)),
                QTableWidgetItem(f"{volume:,}" if isinstance(volume, (int, float)) else str(volume)),
                QTableWidgetItem(f"{oi:,}" if isinstance(oi, (int, float)) else str(oi)),
                QTableWidgetItem(f"{iv_pct:.0f}%" if isinstance(iv_pct, (int, float)) else str(iv_pct)),
                QTableWidgetItem(f"{dte}" if isinstance(dte, (int, float)) else str(dte)),
                QTableWidgetItem(f"{pop_stt:.1f}%" if isinstance(pop_stt, (int, float)) else str(pop_stt)),
                QTableWidgetItem(f"{tax_risk:.1f}%" if isinstance(tax_risk, (int, float)) else str(tax_risk)),
            ]
            
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Color code PoP column
                if col == 9 and isinstance(pop_stt, (int, float)):  # PoP column
                    if pop_stt >= 40:
                        item.setBackground(QColor("#c8e6c9"))  # Green
                    elif pop_stt >= 25:
                        item.setBackground(QColor("#fff9c4"))  # Yellow
                    else:
                        item.setBackground(QColor("#ffcdd2"))  # Red
                # Color code Tax Risk column
                if col == 10 and isinstance(tax_risk, (int, float)):
                    if tax_risk > 3:
                        item.setBackground(QColor("#ffcdd2"))  # Red - high risk
                self.alerts_table.setItem(row, col, item)
    
    def _on_alert_selected(self):
        """Handle alert selection in table."""
        selected_rows = self.alerts_table.selectedIndexes()
        if not selected_rows:
            self.current_alert = None
            self.basic_analysis_btn.setEnabled(False)
            self.enhanced_analysis_btn.setEnabled(False)
            self.details_text.setPlainText("Select an alert from the table above to view details.")
            return
        
        row = selected_rows[0].row()
        if row < len(self.alerts):
            self.current_alert = self.alerts[row]
            self.basic_analysis_btn.setEnabled(True)
            self.enhanced_analysis_btn.setEnabled(True)
            
            # Display alert details with formatted probability section
            details = []
            prob_details = []
            
            for key, value in self.current_alert.items():
                if key == 'probability' and isinstance(value, dict):
                    # Format probability data specially
                    prob_details.append("\n=== PROBABILITY OF PROFIT ===")
                    prob_details.append(f"  PoP (Raw):          {value.get('pop_raw', 'N/A')}%")
                    prob_details.append(f"  PoP (STT-Adjusted): {value.get('pop_stt_adjusted', 'N/A')}%")
                    prob_details.append(f"  Tax Risk:           {value.get('tax_risk', 'N/A')}%")
                    if 'probability_itm' in value:
                        prob_details.append(f"  Probability ITM:    {value.get('probability_itm', 'N/A')}%")
                    if 'probability_max_profit' in value:
                        prob_details.append(f"  Prob Max Profit:    {value.get('probability_max_profit', 'N/A')}%")
                    prob_details.append(f"  Breakeven (Raw):    ₹{value.get('breakeven_raw', 'N/A')}")
                    if 'breakeven_stt_adjusted' in value:
                        prob_details.append(f"  Breakeven (STT):    ₹{value.get('breakeven_stt_adjusted', 'N/A')}")
                    prob_details.append(f"  STT Cost:           ₹{value.get('stt_cost', 'N/A')}")
                elif key in ['leg1', 'leg2'] and isinstance(value, dict):
                    details.append(f"{key}: Strike={value.get('strike')}, Premium={value.get('premium')}, Action={value.get('action')}")
                elif isinstance(value, float):
                    details.append(f"{key}: {value:.2f}")
                elif isinstance(value, dict):
                    details.append(f"{key}: {value}")
                else:
                    details.append(f"{key}: {value}")
            
            # Combine regular details with probability section
            all_details = details + prob_details
            self.details_text.setPlainText("\n".join(all_details))
    
    def _run_analysis(self, analysis_type):
        """Run analysis on selected alert."""
        if not self.current_alert:
            return
        
        # Disable buttons during analysis
        self.basic_analysis_btn.setEnabled(False)
        self.enhanced_analysis_btn.setEnabled(False)
        
        # Handle multi-leg strategies (strike is a string like "60000/60400")
        strike_raw = self.current_alert.get('strike', 0)
        if isinstance(strike_raw, str) and '/' in strike_raw:
            # Multi-leg strategy - extract first strike as primary
            try:
                strikes = [float(s.strip()) for s in strike_raw.split('/')]
                strike = strikes[0]  # Use first leg's strike
            except ValueError:
                strike = 0
        else:
            strike = strike_raw if isinstance(strike_raw, (int, float)) else 0
        
        # Check if this is a multi-leg strategy
        strategy = self.current_alert.get('strategy', '').lower()
        is_multi_leg = any(s in strategy for s in ['spread', 'straddle', 'strangle'])
        
        # For multi-leg, use leg1 data if available
        leg1 = self.current_alert.get('leg1', {})
        leg2 = self.current_alert.get('leg2', {})
        
        if is_multi_leg and leg1:
            # Use leg1's strike and premium for analysis
            strike = leg1.get('strike', strike)
            # Determine type from leg1's action
            action = leg1.get('action', '').upper()
            if 'CE' in action:
                option_type = 'CE'
            elif 'PE' in action:
                option_type = 'PE'
            else:
                option_type = 'CE'
        else:
            option_type = self.current_alert.get('type', 'CE')
        
        # Prepare alert data with defaults
        alert_data = {
            'symbol': self.current_alert.get('symbol', 'UNKNOWN'),
            'spot': self.current_alert.get('spot', 0),
            'strike': strike,
            'premium': self.current_alert.get('premium', 0),
            'type': option_type,
            'days_to_expiry': self.current_alert.get('days_to_expiry', 
                              self.current_alert.get('dte', 30)),
            'iv': self.current_alert.get('iv', 20),
            'iv_percentile': self.current_alert.get('iv_percentile', 50),
            'volume': self.current_alert.get('volume', 0),
            'open_interest': self.current_alert.get('open_interest', 
                             self.current_alert.get('oi', 0)),
            'lot_size': self.current_alert.get('lot_size', 100),
            # Include multi-leg info for enhanced reports
            'is_multi_leg': is_multi_leg,
            'strategy': self.current_alert.get('strategy', ''),
            'leg1': leg1,
            'leg2': leg2,
            'total_cost': self.current_alert.get('total_cost', 0),
            'max_loss': self.current_alert.get('max_loss', 0),
            'breakeven': self.current_alert.get('breakeven', ''),
        }
        
        # Determine option type from strategy if not already set
        if option_type == 'CE' and 'type' not in self.current_alert:
            if 'put' in strategy and 'call' not in strategy:
                alert_data['type'] = 'PE'
        
        # Start analysis worker
        self.analysis_worker = AnalysisWorker(alert_data, analysis_type)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)
        self.analysis_worker.start()
    
    def _on_analysis_finished(self, report_text, report_type):
        """Handle analysis completion."""
        self.basic_analysis_btn.setEnabled(True)
        self.enhanced_analysis_btn.setEnabled(True)
        
        title = "Basic Analysis Report" if report_type == 'basic' else "Enhanced Analysis Report"
        dialog = ReportDialog(title, report_text, self)
        dialog.exec()
    
    def _on_analysis_error(self, error_message):
        """Handle analysis error."""
        self.basic_analysis_btn.setEnabled(True)
        self.enhanced_analysis_btn.setEnabled(True)
        
        QMessageBox.critical(
            self,
            "Analysis Error",
            f"An error occurred during analysis:\n\n{error_message}"
        )


class ScreenerTab(QWidget):
    """Tab for configuring and running the screener."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Track checkboxes
        self.index_checkboxes = {}
        self.stock_checkboxes = {}
        self.strategy_checkboxes = {}
        
        # Worker threads
        self.scan_worker = None
        self.opstra_worker = None
        
        # Skip Opstra flag
        self.skip_opstra = False
        
        self._setup_ui()
        
        # Check Opstra status on startup
        QTimer.singleShot(500, self._update_opstra_status)
    
    def _setup_ui(self):
        """Setup the screener tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Subtitle
        subtitle_label = QLabel("Configure symbols, strategies, and time parameters to generate alerts")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(subtitle_label)
        
        # Main content area with 4 columns
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # Column 1: Symbols
        symbols_group = self._create_symbols_panel()
        content_layout.addWidget(symbols_group, stretch=2)
        
        # Column 2: Strategies
        strategies_group = self._create_strategies_panel()
        content_layout.addWidget(strategies_group, stretch=1)
        
        # Column 3: Time Config
        time_group = self._create_time_panel()
        content_layout.addWidget(time_group, stretch=1)
        
        # Column 4: Opstra Config
        opstra_group = self._create_opstra_panel()
        content_layout.addWidget(opstra_group, stretch=1)
        
        layout.addLayout(content_layout, stretch=1)
        
        # Control panel
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)
    
    def _create_symbols_panel(self):
        """Create the symbols selection panel."""
        group = QGroupBox("SYMBOLS")
        group.setFont(QFont("Helvetica Neue", 10, QFont.Weight.Bold))
        layout = QVBoxLayout(group)
        
        # Indices section
        indices_label = QLabel("Indices:")
        indices_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        layout.addWidget(indices_label)
        
        indices_layout = QHBoxLayout()
        for symbol in INDEX_SYMBOLS:
            cb = QCheckBox(symbol)
            cb.setChecked(True)
            self.index_checkboxes[symbol] = cb
            indices_layout.addWidget(cb)
        indices_layout.addStretch()
        layout.addLayout(indices_layout)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)
        
        # Stocks section header with label
        stocks_header = QHBoxLayout()
        self.stocks_label = QLabel(f"Stocks ({len(STOCK_SYMBOLS)}):")
        self.stocks_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        stocks_header.addWidget(self.stocks_label)
        stocks_header.addStretch()
        layout.addLayout(stocks_header)
        
        # Stock action buttons row
        stock_buttons = QHBoxLayout()
        stock_buttons.setSpacing(5)
        
        add_stock_btn = QPushButton("➕ Add")
        add_stock_btn.setMinimumWidth(60)
        add_stock_btn.setToolTip("Add a new stock symbol")
        add_stock_btn.clicked.connect(self._add_stock)
        stock_buttons.addWidget(add_stock_btn)
        
        remove_stock_btn = QPushButton("➖ Remove")
        remove_stock_btn.setMinimumWidth(80)
        remove_stock_btn.setToolTip("Remove unchecked stocks from list")
        remove_stock_btn.clicked.connect(self._remove_selected_stocks)
        stock_buttons.addWidget(remove_stock_btn)
        
        stock_buttons.addStretch()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.setMinimumWidth(75)
        select_all_btn.clicked.connect(self._select_all_stocks)
        stock_buttons.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.setMinimumWidth(70)
        clear_all_btn.clicked.connect(self._clear_all_stocks)
        stock_buttons.addWidget(clear_all_btn)
        
        layout.addLayout(stock_buttons)
        
        # Scrollable stock list
        self.stocks_scroll_area = QScrollArea()
        self.stocks_scroll_area.setWidgetResizable(True)
        self.stocks_scroll_area.setMinimumHeight(260)
        self.stocks_scroll_area.setStyleSheet("QScrollArea { border: 1px solid #ccc; }")
        
        self.stocks_scroll_widget = QWidget()
        self.stocks_scroll_layout = QGridLayout(self.stocks_scroll_widget)
        self.stocks_scroll_layout.setSpacing(5)
        
        # Sort stocks alphabetically and create checkboxes
        self._populate_stock_checkboxes(sorted(STOCK_SYMBOLS))
        
        self.stocks_scroll_area.setWidget(self.stocks_scroll_widget)
        layout.addWidget(self.stocks_scroll_area)
        
        return group
    
    def _populate_stock_checkboxes(self, stock_list, checked=True):
        """Populate the stock checkboxes grid."""
        # Clear existing checkboxes
        for cb in list(self.stock_checkboxes.values()):
            cb.setParent(None)
        self.stock_checkboxes.clear()
        
        # Clear layout
        while self.stocks_scroll_layout.count():
            item = self.stocks_scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create checkboxes in a grid (4 columns)
        cols = 4
        for i, symbol in enumerate(sorted(stock_list)):
            cb = QCheckBox(symbol)
            cb.setChecked(checked)
            self.stock_checkboxes[symbol] = cb
            self.stocks_scroll_layout.addWidget(cb, i // cols, i % cols)
        
        # Update label
        self.stocks_label.setText(f"Stocks ({len(self.stock_checkboxes)}):")
    
    def _add_stock(self):
        """Add a new stock symbol."""
        text, ok = QInputDialog.getText(
            self,
            "Add Stock Symbol",
            "Enter stock symbol(s) separated by comma:\n(e.g., TCS, INFY, WIPRO)",
            QLineEdit.EchoMode.Normal,
            ""
        )
        
        if not ok or not text.strip():
            return
        
        # Parse input - handle comma-separated symbols
        new_symbols = [s.strip().upper() for s in text.split(',') if s.strip()]
        
        added = []
        already_exists = []
        
        for symbol in new_symbols:
            if symbol in self.stock_checkboxes:
                already_exists.append(symbol)
            else:
                added.append(symbol)
        
        if added:
            # Get current stock list and add new ones
            current_stocks = list(self.stock_checkboxes.keys())
            # Remember which ones were checked
            checked_stocks = {sym for sym, cb in self.stock_checkboxes.items() if cb.isChecked()}
            
            # Add new stocks
            all_stocks = current_stocks + added
            
            # Repopulate (new stocks will be checked by default)
            self._populate_stock_checkboxes(all_stocks, checked=False)
            
            # Restore check state for existing stocks
            for sym in checked_stocks:
                if sym in self.stock_checkboxes:
                    self.stock_checkboxes[sym].setChecked(True)
            
            # Check the newly added stocks
            for sym in added:
                if sym in self.stock_checkboxes:
                    self.stock_checkboxes[sym].setChecked(True)
            
            main_window = self.window()
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage(f"Added: {', '.join(added)}", 3000)
        
        if already_exists:
            QMessageBox.information(
                self,
                "Already Exists",
                f"These symbols already exist:\n{', '.join(already_exists)}"
            )
    
    def _remove_selected_stocks(self):
        """Remove unchecked stocks from the list."""
        unchecked = [sym for sym, cb in self.stock_checkboxes.items() if not cb.isChecked()]
        
        if not unchecked:
            QMessageBox.information(
                self,
                "No Selection",
                "Uncheck the stocks you want to remove, then click Remove."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Remove Stocks",
            f"Remove {len(unchecked)} unchecked stock(s) from the list?\n\n"
            f"{', '.join(sorted(unchecked)[:10])}{'...' if len(unchecked) > 10 else ''}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Keep only checked stocks
            remaining = [sym for sym, cb in self.stock_checkboxes.items() if cb.isChecked()]
            self._populate_stock_checkboxes(remaining, checked=True)
            
            main_window = self.window()
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage(f"Removed {len(unchecked)} stock(s)", 3000)
    
    def _create_strategies_panel(self):
        """Create the strategies toggle panel."""
        group = QGroupBox("STRATEGIES")
        group.setFont(QFont("Helvetica Neue", 10, QFont.Weight.Bold))
        layout = QVBoxLayout(group)
        
        # Strategy checkboxes
        for strategy_name, default_checked in STRATEGIES:
            cb = QCheckBox(strategy_name)
            cb.setChecked(default_checked)
            self.strategy_checkboxes[strategy_name] = cb
            layout.addWidget(cb)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_strategies)
        btn_layout.addWidget(select_all_btn)
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self._clear_all_strategies)
        btn_layout.addWidget(clear_all_btn)
        
        layout.addLayout(btn_layout)
        
        return group
    
    def _create_time_panel(self):
        """Create the time configuration panel."""
        group = QGroupBox("TIME CONFIG")
        group.setFont(QFont("Helvetica Neue", 10, QFont.Weight.Bold))
        layout = QVBoxLayout(group)
        
        # Historical Data section
        hist_label = QLabel("Historical Data (RSI/EMA):")
        hist_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        layout.addWidget(hist_label)
        
        # Period dropdown
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Period:"))
        self.trend_period_combo = QComboBox()
        self.trend_period_combo.addItems(HISTORICAL_PERIODS)
        self.trend_period_combo.setCurrentText("1mo")
        self.trend_period_combo.setToolTip("Lookback period for RSI and EMA calculations")
        period_layout.addWidget(self.trend_period_combo)
        layout.addLayout(period_layout)
        
        # Interval dropdown
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval:"))
        self.trend_interval_combo = QComboBox()
        self.trend_interval_combo.addItems(HISTORICAL_INTERVALS)
        self.trend_interval_combo.setCurrentText("1d")
        self.trend_interval_combo.setToolTip("Data granularity for trend analysis")
        interval_layout.addWidget(self.trend_interval_combo)
        layout.addLayout(interval_layout)
        
        # Separator
        layout.addSpacing(15)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)
        layout.addSpacing(10)
        
        # HV Calculation section
        hv_label = QLabel("HV Calculation:")
        hv_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        layout.addWidget(hv_label)
        
        # HV Period dropdown
        hv_period_layout = QHBoxLayout()
        hv_period_layout.addWidget(QLabel("Period:"))
        self.hv_period_combo = QComboBox()
        self.hv_period_combo.addItems(HV_PERIODS)
        self.hv_period_combo.setCurrentText("1y")
        self.hv_period_combo.setToolTip("Lookback period for Historical Volatility")
        hv_period_layout.addWidget(self.hv_period_combo)
        layout.addLayout(hv_period_layout)
        
        # HV Window spinner
        hv_window_layout = QHBoxLayout()
        hv_window_layout.addWidget(QLabel("Window:"))
        self.hv_window_spin = QSpinBox()
        self.hv_window_spin.setRange(10, 60)
        self.hv_window_spin.setValue(30)
        self.hv_window_spin.setSuffix(" days")
        self.hv_window_spin.setToolTip("Rolling window for HV calculation")
        hv_window_layout.addWidget(self.hv_window_spin)
        layout.addLayout(hv_window_layout)
        
        layout.addStretch()
        
        return group
    
    def _create_opstra_panel(self):
        """Create the Opstra IV configuration panel."""
        group = QGroupBox("OPSTRA IV")
        group.setFont(QFont("Helvetica Neue", 10, QFont.Weight.Bold))
        layout = QVBoxLayout(group)
        
        # Status section
        status_label = QLabel("Session Status:")
        status_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        layout.addWidget(status_label)
        
        self.opstra_status = QLabel("Checking...")
        self.opstra_status.setStyleSheet("""
            QLabel {
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.opstra_status)
        
        # Check status button
        check_btn = QPushButton("🔄 Check Status")
        check_btn.setToolTip("Check if current Opstra session is valid")
        check_btn.clicked.connect(self._update_opstra_status)
        layout.addWidget(check_btn)
        
        # Separator
        layout.addSpacing(10)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)
        layout.addSpacing(5)
        
        # Actions section
        actions_label = QLabel("Actions:")
        actions_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        layout.addWidget(actions_label)
        
        # Refresh session button (opens browser)
        self.refresh_btn = QPushButton("🌐 Refresh Session")
        self.refresh_btn.setToolTip("Open browser to refresh Opstra session cookies")
        self.refresh_btn.clicked.connect(lambda: self._refresh_opstra_session(force=False))
        layout.addWidget(self.refresh_btn)
        
        # Force login button
        force_login_btn = QPushButton("🔑 Force Re-Login")
        force_login_btn.setToolTip("Force a new login even if session exists")
        force_login_btn.clicked.connect(lambda: self._refresh_opstra_session(force=True))
        layout.addWidget(force_login_btn)
        
        # Manual cookies button
        manual_btn = QPushButton("✏️ Enter Cookies Manually")
        manual_btn.setToolTip("Manually enter JSESSIONID and DSESSIONID")
        manual_btn.clicked.connect(self._manual_cookie_entry)
        layout.addWidget(manual_btn)
        
        # Separator
        layout.addSpacing(10)
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line2)
        layout.addSpacing(5)
        
        # Settings section
        settings_label = QLabel("Settings:")
        settings_label.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
        layout.addWidget(settings_label)
        
        # Skip Opstra checkbox
        self.skip_opstra_cb = QCheckBox("Skip Opstra (use HV only)")
        self.skip_opstra_cb.setToolTip("Skip Opstra IV data and use Historical Volatility as fallback")
        self.skip_opstra_cb.stateChanged.connect(self._on_skip_opstra_changed)
        layout.addWidget(self.skip_opstra_cb)
        
        # Clear profile button
        clear_btn = QPushButton("🗑️ Clear Saved Profile")
        clear_btn.setToolTip("Delete saved Chrome profile (requires re-login)")
        clear_btn.clicked.connect(self._clear_opstra_profile)
        layout.addWidget(clear_btn)
        
        layout.addStretch()
        
        return group
    
    def _update_opstra_status(self):
        """Check and update Opstra session status."""
        try:
            from screener.iv.opstra import is_opstra_configured, validate_opstra_session
            
            if not is_opstra_configured():
                self.opstra_status.setText("❌ Not Configured")
                self.opstra_status.setStyleSheet("""
                    QLabel {
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-weight: bold;
                        background-color: #ffebee;
                        color: #c62828;
                    }
                """)
                return
            
            if validate_opstra_session():
                self.opstra_status.setText("✅ Active")
                self.opstra_status.setStyleSheet("""
                    QLabel {
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-weight: bold;
                        background-color: #e8f5e9;
                        color: #2e7d32;
                    }
                """)
            else:
                self.opstra_status.setText("⚠️ Expired")
                self.opstra_status.setStyleSheet("""
                    QLabel {
                        padding: 5px 10px;
                        border-radius: 3px;
                        font-weight: bold;
                        background-color: #fff3e0;
                        color: #e65100;
                    }
                """)
        except Exception as e:
            self.opstra_status.setText("❓ Error")
            self.opstra_status.setStyleSheet("""
                QLabel {
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                    background-color: #fce4ec;
                    color: #880e4f;
                }
            """)
    
    def _refresh_opstra_session(self, force=False):
        """Refresh Opstra session via browser."""
        if self.opstra_worker and self.opstra_worker.isRunning():
            QMessageBox.warning(self, "In Progress", "Opstra refresh is already in progress.")
            return
        
        # Disable buttons during refresh
        self.refresh_btn.setEnabled(False)
        self.opstra_status.setText("🔄 Refreshing...")
        self.opstra_status.setStyleSheet("""
            QLabel {
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
                background-color: #e3f2fd;
                color: #1565c0;
            }
        """)
        
        # Get the main window to update status bar
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("Opening browser for Opstra login...")
        
        # Start worker thread
        self.opstra_worker = OpstraRefreshWorker(force_login=force)
        self.opstra_worker.finished.connect(self._on_opstra_refresh_finished)
        self.opstra_worker.start()
    
    def _on_opstra_refresh_finished(self, success, message):
        """Handle Opstra refresh completion."""
        self.refresh_btn.setEnabled(True)
        
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(message, 5000)
        
        self._update_opstra_status()
        
        if success:
            QMessageBox.information(self, "Opstra Refresh", message)
        else:
            QMessageBox.warning(self, "Opstra Refresh", message)
    
    def _manual_cookie_entry(self):
        """Open dialog for manual cookie entry."""
        # Get JSESSIONID
        jsessionid, ok1 = QInputDialog.getText(
            self, 
            "Enter JSESSIONID",
            "JSESSIONID cookie value:\n(Get from browser DevTools > Application > Cookies)",
            QLineEdit.EchoMode.Normal,
            ""
        )
        
        if not ok1 or not jsessionid.strip():
            return
        
        # Get DSESSIONID
        dsessionid, ok2 = QInputDialog.getText(
            self,
            "Enter DSESSIONID",
            "DSESSIONID cookie value:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        
        if not ok2 or not dsessionid.strip():
            return
        
        try:
            from screener.iv.opstra import set_opstra_cookies
            set_opstra_cookies(jsessionid.strip(), dsessionid.strip())
            
            self._update_opstra_status()
            
            QMessageBox.information(
                self,
                "Cookies Set",
                "Opstra cookies have been set. Click 'Check Status' to validate."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to set cookies: {str(e)}"
            )
    
    def _on_skip_opstra_changed(self, state):
        """Handle skip Opstra checkbox change."""
        self.skip_opstra = (state == Qt.CheckState.Checked.value)
        
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            if self.skip_opstra:
                main_window.status_bar.showMessage("Opstra skipped - using Historical Volatility only", 3000)
            else:
                main_window.status_bar.showMessage("Opstra enabled", 3000)
    
    def _clear_opstra_profile(self):
        """Clear the saved Chrome profile."""
        reply = QMessageBox.question(
            self,
            "Clear Profile",
            "This will delete the saved Chrome profile.\nYou will need to login again.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from screener.iv.opstra_login import clear_opstra_profile
                clear_opstra_profile()
                
                self._update_opstra_status()
                
                QMessageBox.information(
                    self,
                    "Profile Cleared",
                    "Chrome profile has been deleted. You will need to login again."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear profile: {str(e)}"
                )
    
    def _create_control_panel(self):
        """Create the control panel with Run button and output path."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout = QHBoxLayout(frame)
        
        # Run button
        self.run_button = QPushButton("▶  Run Single Scan")
        self.run_button.setFont(QFont("Helvetica Neue", 11, QFont.Weight.Bold))
        self.run_button.setMinimumHeight(45)
        self.run_button.setMinimumWidth(180)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.run_button.clicked.connect(self._run_scan)
        layout.addWidget(self.run_button)
        
        layout.addSpacing(20)
        
        # Output path
        output_layout = QVBoxLayout()
        output_label = QLabel("Output:")
        output_label.setStyleSheet("color: #666; font-size: 10px;")
        output_layout.addWidget(output_label)
        
        output_path = QLabel(JSON_FILE)
        output_path.setStyleSheet("color: #333; font-family: monospace; font-size: 11px;")
        output_path.setWordWrap(True)
        output_layout.addWidget(output_path)
        
        layout.addLayout(output_layout, stretch=1)
        
        return frame
    
    def _select_all_stocks(self):
        """Select all stock checkboxes."""
        for cb in self.stock_checkboxes.values():
            cb.setChecked(True)
    
    def _clear_all_stocks(self):
        """Clear all stock checkboxes."""
        for cb in self.stock_checkboxes.values():
            cb.setChecked(False)
    
    def _select_all_strategies(self):
        """Select all strategy checkboxes."""
        for cb in self.strategy_checkboxes.values():
            cb.setChecked(True)
    
    def _clear_all_strategies(self):
        """Clear all strategy checkboxes."""
        for cb in self.strategy_checkboxes.values():
            cb.setChecked(False)
    
    def _get_selected_config(self):
        """Get the current configuration from UI controls."""
        return {
            'indices': [sym for sym, cb in self.index_checkboxes.items() if cb.isChecked()],
            'stocks': [sym for sym, cb in self.stock_checkboxes.items() if cb.isChecked()],
            'strategies': [name for name, cb in self.strategy_checkboxes.items() if cb.isChecked()],
            'trend_period': self.trend_period_combo.currentText(),
            'trend_interval': self.trend_interval_combo.currentText(),
            'hv_period': self.hv_period_combo.currentText(),
            'hv_window': self.hv_window_spin.value(),
            'skip_opstra': self.skip_opstra,
        }
    
    def _run_scan(self):
        """Start the scan with current configuration."""
        config = self._get_selected_config()
        
        # Validate at least one symbol selected
        if not config['indices'] and not config['stocks']:
            QMessageBox.warning(
                self,
                "No Symbols Selected",
                "Please select at least one index or stock to scan."
            )
            return
        
        # Validate at least one strategy selected
        if not config['strategies']:
            QMessageBox.warning(
                self,
                "No Strategies Selected",
                "Please select at least one strategy."
            )
            return
        
        # Disable controls during scan
        self.run_button.setEnabled(False)
        self.run_button.setText("Scanning...")
        
        # Create and start worker thread
        self.scan_worker = ScanWorker(config)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()
    
    def _on_scan_progress(self, message):
        """Handle scan progress updates."""
        main_window = self.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(message)
    
    def _on_scan_finished(self, alert_count, message):
        """Handle scan completion."""
        self.run_button.setEnabled(True)
        self.run_button.setText("▶  Run Single Scan")
        
        QMessageBox.information(
            self,
            "Scan Complete",
            f"Scan finished successfully!\n\n"
            f"Alerts generated: {alert_count}\n"
            f"Output saved to:\n{JSON_FILE}"
        )
    
    def _on_scan_error(self, error_message):
        """Handle scan errors."""
        self.run_button.setEnabled(True)
        self.run_button.setText("▶  Run Single Scan")
        
        QMessageBox.critical(
            self,
            "Scan Error",
            f"An error occurred during the scan:\n\n{error_message}"
        )


class ScreenerMainWindow(QMainWindow):
    """Main window for the Options Screener GUI."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Options Screener v3.3")
        self.setMinimumSize(1000, 750)
        self.resize(1100, 800)
        
        self._setup_ui()
        self._apply_styles()
    
    def _setup_ui(self):
        """Setup the main UI layout with tabs."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Title
        title_label = QLabel("Smart Options Screener v3.3")
        title_label.setFont(QFont("Helvetica Neue", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Helvetica Neue", 11))
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 5px;
                background: white;
            }
            QTabBar::tab {
                background: #f0f0f0;
                border: 1px solid #ddd;
                border-bottom: none;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover:!selected {
                background: #e0e0e0;
            }
        """)
        
        # Add tabs
        self.screener_tab = ScreenerTab()
        self.tabs.addTab(self.screener_tab, "🔍  Screener")
        
        self.viewer_tab = AlertViewerTab()
        self.tabs.addTab(self.viewer_tab, "📊  Alert Viewer")
        
        main_layout.addWidget(self.tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _apply_styles(self):
        """Apply global styles to the application."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fafafa;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #333;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QComboBox, QSpinBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton {
                padding: 5px 15px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #fff;
            }
            QPushButton:hover {
                background-color: #e3e3e3;
            }
            QStatusBar {
                background-color: #f0f0f0;
                border-top: 1px solid #ddd;
            }
        """)


def main():
    """Entry point for the GUI application."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = ScreenerMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
