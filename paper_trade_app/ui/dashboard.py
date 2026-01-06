"""
Dashboard UI for Indian Options Paper Trader

Enhanced for Tier 1/2 features:
- Order ID based position tracking (supports multiple orders per token)
- SL/Target display
- Net P&L with fees
- Realized/Unrealized breakdown
- Position removal on close
"""

import datetime
import sys
import io
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
    QListWidget, QListWidgetItem, QTextEdit, QPushButton, 
    QFrame, QMessageBox, QSplitter, QComboBox, QInputDialog,
    QGroupBox, QSizePolicy, QScrollArea, QDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont


class AnalysisReportDialog(QDialog):
    """
    Dialog to display alert analysis reports in a popup window.
    Supports both basic and enhanced analysis modes with HTML rendering.
    Includes PDF export functionality.
    """
    
    def __init__(self, title: str, report_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(950, 750)
        self.resize(1050, 850)
        self.report_title = title
        self.raw_text = report_text
        
        self._setup_ui(report_text)
    
    def _convert_to_html(self, report_text: str) -> str:
        """Convert plain text report to styled HTML."""
        import html
        import re
        
        # Escape HTML entities
        text = html.escape(report_text)
        
        # Replace box drawing characters and structure with HTML
        lines = text.split('\n')
        html_lines = []
        current_section = None
        in_table = False
        
        for line in lines:
            # Main title box
            if '█' in line:
                if 'COMPREHENSIVE' in line or 'ENHANCED' in line or 'ANALYSIS' in line:
                    # Extract title from the line
                    title_match = re.search(r'(COMPREHENSIVE.*?|ENHANCED.*?)(?:█|$)', line)
                    if title_match:
                        title_text = title_match.group(1).strip()
                        html_lines.append(f'<div class="main-title">{title_text}</div>')
                continue
            
            # Section headers
            if '📋' in line or '📊' in line or '🔢' in line or '📖' in line or '⚠️' in line or '🎯' in line or '💰' in line or '📈' in line or '🛡️' in line:
                section_text = re.sub(r'[│┌┐└┘├┤─┬┴┼]', '', line).strip()
                if section_text:
                    html_lines.append(f'<div class="section-header">{section_text}</div>')
                    html_lines.append('<div class="section-content">')
                    current_section = True
                continue
            
            # Table borders - skip or convert
            if line.strip().startswith(('┌', '├', '└', '─', '╔', '╠', '╚', '═')):
                if current_section and not in_table:
                    # Start of a visual section
                    pass
                continue
            if line.strip().startswith(('┐', '┤', '┘', '╗', '╣', '╝')):
                continue
            
            # Content lines
            if '│' in line or '║' in line:
                # Remove box characters and clean up
                content = re.sub(r'[│║]', '', line).strip()
                if content:
                    # Check for key-value pairs
                    if ':' in content and not content.startswith('•'):
                        parts = content.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip()
                            value = parts[1].strip()
                            # Color coding for values
                            value_class = 'value'
                            if '🟢' in value or 'GOOD' in value.upper() or 'BUY' in value.upper() or '+' in value:
                                value_class = 'value-positive'
                            elif '🔴' in value or 'BAD' in value.upper() or 'SELL' in value.upper() or 'WARNING' in value.upper():
                                value_class = 'value-negative'
                            elif '🟡' in value or '🟠' in value or 'CAUTION' in value.upper():
                                value_class = 'value-warning'
                            html_lines.append(f'<div class="data-row"><span class="label">{key}:</span> <span class="{value_class}">{value}</span></div>')
                        else:
                            html_lines.append(f'<div class="content-line">{content}</div>')
                    elif content.startswith('•'):
                        html_lines.append(f'<div class="bullet-point">{content}</div>')
                    else:
                        # Check for visual bars
                        if '█' in content or '░' in content:
                            html_lines.append(f'<div class="progress-bar">{content}</div>')
                        else:
                            html_lines.append(f'<div class="content-line">{content}</div>')
                continue
            
            # Regular lines
            if line.strip():
                html_lines.append(f'<div class="content-line">{line.strip()}</div>')
        
        # Close any open sections
        if current_section:
            html_lines.append('</div>')
        
        # Build complete HTML document
        html_content = f'''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #e0e0e0;
            padding: 30px;
            margin: 0;
            line-height: 1.6;
        }}
        .main-title {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            font-size: 22px;
            font-weight: bold;
            text-align: center;
            border-radius: 10px;
            margin-bottom: 25px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .section-header {{
            background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
            color: #0a0a0a;
            padding: 12px 20px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 8px;
            margin: 20px 0 15px 0;
            box-shadow: 0 3px 10px rgba(17, 153, 142, 0.3);
        }}
        .section-content {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 15px 20px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }}
        .data-row {{
            display: flex;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .data-row:last-child {{
            border-bottom: none;
        }}
        .label {{
            color: #a0a0a0;
            min-width: 180px;
            font-weight: 500;
        }}
        .value {{
            color: #e0e0e0;
            font-weight: 600;
        }}
        .value-positive {{
            color: #4ade80;
            font-weight: 600;
        }}
        .value-negative {{
            color: #f87171;
            font-weight: 600;
        }}
        .value-warning {{
            color: #fbbf24;
            font-weight: 600;
        }}
        .bullet-point {{
            padding: 6px 0 6px 15px;
            color: #b0b0b0;
            position: relative;
        }}
        .bullet-point:before {{
            content: '';
            position: absolute;
            left: 0;
            top: 12px;
            width: 6px;
            height: 6px;
            background: #667eea;
            border-radius: 50%;
        }}
        .content-line {{
            padding: 4px 0;
            color: #c0c0c0;
        }}
        .progress-bar {{
            font-family: 'Courier New', monospace;
            background: rgba(0, 0, 0, 0.3);
            padding: 8px 12px;
            border-radius: 4px;
            margin: 8px 0;
            font-size: 12px;
        }}
        hr {{
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 11px;
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }}
    </style>
</head>
<body>
    {''.join(html_lines)}
    <div class="footer">
        Generated by Paper Trade App • {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>
</body>
</html>
'''
        return html_content
    
    def _setup_ui(self, report_text: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Report display area with HTML rendering
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        try:
            self.report_display = QWebEngineView()
            html_content = self._convert_to_html(report_text)
            self.report_display.setHtml(html_content)
            self.use_web_view = True
        except ImportError:
            # Fallback to QTextEdit if WebEngine not available
            self.report_display = QTextEdit()
            self.report_display.setReadOnly(True)
            self.report_display.setFont(QFont("Consolas", 11))
            self.report_display.setStyleSheet("""
                QTextEdit {
                    background-color: #1a1a2e;
                    color: #E0E0E0;
                    border: 1px solid #333;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
            self.report_display.setPlainText(report_text)
            self.use_web_view = False
        
        layout.addWidget(self.report_display)
        
        # Button bar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        # Save as PDF button
        self.btn_pdf = QPushButton("📄 Save as PDF")
        self.btn_pdf.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c0392b, stop:1 #a93226);
            }
        """)
        self.btn_pdf.clicked.connect(self._save_as_pdf)
        btn_layout.addWidget(self.btn_pdf)
        
        # Copy button
        self.btn_copy = QPushButton("📋 Copy Text")
        self.btn_copy.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3498db, stop:1 #2980b9);
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2980b9, stop:1 #1f6aa5);
            }
        """)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_layout.addWidget(self.btn_copy)
        
        # Close button
        self.btn_close = QPushButton("✖ Close")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #555, stop:1 #444);
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #666, stop:1 #555);
            }
        """)
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
        
        # Dark theme for dialog
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1a2e, stop:1 #16213e);
            }
        """)
    
    def _save_as_pdf(self):
        """Save the report as a PDF file."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtCore import QMarginsF
        from PyQt6.QtGui import QPageLayout, QPageSize
        
        # Generate default filename
        safe_title = self.report_title.replace(' ', '_').replace(':', '')
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Analysis_{safe_title}_{timestamp}.pdf"
        
        # Get save path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report as PDF",
            default_name,
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return
        
        try:
            if hasattr(self, 'use_web_view') and self.use_web_view:
                # Use WebEngine's print to PDF
                page_layout = QPageLayout(
                    QPageSize(QPageSize.PageSizeId.A4),
                    QPageLayout.Orientation.Portrait,
                    QMarginsF(15, 15, 15, 15)
                )
                self.report_display.page().printToPdf(file_path, page_layout)
                QMessageBox.information(self, "Success", f"Report saved to:\n{file_path}")
            else:
                # Fallback: Use reportlab if available
                self._save_text_as_pdf(file_path)
        except Exception as e:
            # Final fallback: Save as HTML
            html_path = file_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self._convert_to_html(self.raw_text))
            QMessageBox.information(
                self, 
                "Saved as HTML", 
                f"PDF generation not available.\nSaved as HTML instead:\n{html_path}"
            )
    
    def _save_text_as_pdf(self, file_path: str):
        """Fallback PDF generation using reportlab."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
            from reportlab.lib.colors import HexColor
            
            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=HexColor('#333333'),
                spaceAfter=20
            )
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['Normal'],
                fontSize=10,
                textColor=HexColor('#444444'),
                fontName='Courier'
            )
            
            story = []
            story.append(Paragraph(self.report_title, title_style))
            story.append(Spacer(1, 12))
            
            # Convert text to paragraphs
            for line in self.raw_text.split('\n'):
                if line.strip():
                    story.append(Paragraph(line, body_style))
                else:
                    story.append(Spacer(1, 6))
            
            doc.build(story)
            QMessageBox.information(self, "Success", f"Report saved to:\n{file_path}")
            
        except ImportError:
            raise Exception("reportlab not installed")
    
    def _copy_to_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.raw_text)
        QMessageBox.information(self, "Copied", "Report text copied to clipboard!")


class AlertItemWidget(QWidget):
    """
    Custom widget for each alert in the Signal Inbox.
    Contains alert info, status indicator, and action buttons.
    Enhanced to display screener data fields and multi-leg strategies.
    Now includes live LTP (Last Traded Price) display.
    """
    enter_trade_clicked = pyqtSignal(dict)
    square_off_clicked = pyqtSignal(dict)
    basic_analyze_clicked = pyqtSignal(dict)
    enhanced_analyze_clicked = pyqtSignal(dict)
    
    def __init__(self, alert_data: dict, parent=None):
        super().__init__(parent)
        self.alert_data = alert_data
        self.is_traded = False
        self.is_squared_off = False
        self.token = None  # Will be set when subscribed to live data
        self.last_ltp = 0.0  # Track last LTP for color changes
        
        self._setup_ui()
    
    def _setup_ui(self):
        # Main vertical layout for stacked content
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)
        
        # === TOP SECTION: Status + Info ===
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)
        
        # Status indicator
        self.status_label = QLabel("⚪")
        self.status_label.setFixedWidth(24)
        self.status_label.setStyleSheet("font-size: 14px;")
        self.status_label.setToolTip("Pending")
        top_layout.addWidget(self.status_label)
        
        # Info section (vertical layout for main + details)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # Extract alert data
        action = self.alert_data.get('action', 'BUY')
        symbol = self.alert_data.get('symbol', 'Unknown')
        strike = self.alert_data.get('strike', 0)
        option_type = self.alert_data.get('option_type', 'CE')
        price = self.alert_data.get('price_limit', 0)
        quantity = self.alert_data.get('quantity', 0)
        strategy_type = self.alert_data.get('strategy_type', 'single')
        strategy = self.alert_data.get('strategy', '')
        
        # Build main line based on strategy type
        if strategy_type == 'spread':
            sell_strike = self.alert_data.get('sell_strike', 0)
            if self.alert_data.get('display_text'):
                main_text = f"{action} {symbol} {self.alert_data['display_text']}"
            else:
                main_text = f"{action} {symbol} {strike}/{sell_strike}{option_type} @ ₹{price:.2f}"
            main_color = '#FFA726' if action == 'BUY' else '#FF5252'
        elif strategy_type == 'volatility':
            if option_type == 'STRADDLE':
                main_text = f"{action} {symbol} {strike} STRADDLE @ ₹{price:.2f}"
            else:
                put_strike = self.alert_data.get('put_strike', strike)
                if self.alert_data.get('display_text'):
                    main_text = f"{action} {symbol} {self.alert_data['display_text']}"
                else:
                    main_text = f"{action} {symbol} {put_strike}/{strike} STRANGLE @ ₹{price:.2f}"
            main_color = '#AB47BC' if action == 'BUY' else '#FF5252'
        else:
            main_text = f"{action} {symbol} {strike}{option_type} @ ₹{price:.2f}"
            main_color = '#00E676' if action == 'BUY' else '#FF5252'
        
        # Main line with symbol info
        main_row = QHBoxLayout()
        main_row.setSpacing(8)
        
        self.main_label = QLabel(main_text)
        self.main_label.setStyleSheet(
            f"color: {main_color}; font-weight: bold; font-size: 13px;"
        )
        main_row.addWidget(self.main_label)
        
        # LTP display - shows live price with color indication
        self.ltp_label = QLabel("LTP: ---")
        self.ltp_label.setStyleSheet(
            "color: #888; font-size: 12px; font-weight: bold; "
            "background-color: #2a2a2a; padding: 2px 8px; border-radius: 3px;"
        )
        self.ltp_label.setToolTip("Live Last Traded Price - Updates in real-time")
        self.ltp_label.setFixedWidth(100)
        main_row.addWidget(self.ltp_label)
        main_row.addStretch()
        
        info_layout.addLayout(main_row)
        
        # Details line based on strategy type
        spot = self.alert_data.get('spot', 0)
        iv = self.alert_data.get('iv', 0)
        expiry = self.alert_data.get('expiry', '')
        days_to_expiry = self.alert_data.get('days_to_expiry', 0)
        
        if strategy_type == 'spread':
            max_profit = self.alert_data.get('max_profit', 0)
            max_loss = self.alert_data.get('max_loss', 0)
            reward_ratio = self.alert_data.get('reward_ratio', 0)
            details_parts = []
            if max_profit:
                details_parts.append(f"MaxP: ₹{max_profit:,.0f}")
            if max_loss:
                details_parts.append(f"MaxL: ₹{max_loss:,.0f}")
            if reward_ratio:
                details_parts.append(f"R:R: {reward_ratio:.2f}")
            if expiry:
                details_parts.append(f"Exp: {expiry} ({days_to_expiry}d)")
            if strategy:
                details_parts.append(f"[{strategy}]")
        elif strategy_type == 'volatility':
            max_loss = self.alert_data.get('max_loss', 0)
            breakeven = self.alert_data.get('breakeven', '')
            distance = self.alert_data.get('distance_from_spot', '')
            details_parts = []
            if max_loss:
                details_parts.append(f"MaxL: ₹{max_loss:,.0f}")
            if breakeven:
                details_parts.append(f"BE: {breakeven}")
            if distance:
                details_parts.append(f"{distance}")
            if expiry:
                details_parts.append(f"Exp: {expiry} ({days_to_expiry}d)")
            if strategy:
                details_parts.append(f"[{strategy}]")
        else:
            details_parts = [f"Qty: {quantity}"]
            if spot:
                details_parts.append(f"Spot: ₹{spot:,.0f}")
            if iv:
                details_parts.append(f"IV: {iv:.1f}%")
            if expiry:
                if days_to_expiry:
                    details_parts.append(f"Exp: {expiry} ({days_to_expiry}d)")
                else:
                    details_parts.append(f"Exp: {expiry}")
            if strategy:
                details_parts.append(f"[{strategy}]")
        
        details_text = " | ".join(details_parts)
        self.details_label = QLabel(details_text)
        self.details_label.setStyleSheet("color: #999; font-size: 11px;")
        info_layout.addWidget(self.details_label)
        
        # Optional: Market data line (OI, Volume, RSI)
        oi = self.alert_data.get('oi', 0)
        volume = self.alert_data.get('volume', 0)
        rsi = self.alert_data.get('rsi', 0)
        tier = self.alert_data.get('tier', '')
        
        if oi or volume or rsi or tier:
            market_parts = []
            if oi:
                market_parts.append(f"OI: {oi:,.0f}")
            if volume:
                market_parts.append(f"Vol: {volume:,.0f}")
            if rsi:
                market_parts.append(f"RSI: {rsi:.1f}")
            if tier:
                market_parts.append(f"Tier: {tier}")
            
            if market_parts:
                market_text = " | ".join(market_parts)
                self.market_label = QLabel(market_text)
                self.market_label.setStyleSheet("color: #777; font-size: 10px;")
                info_layout.addWidget(self.market_label)
        
        top_layout.addLayout(info_layout)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)
        
        # === SEPARATOR LINE ===
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #444; max-height: 1px; margin: 4px 0px;")
        main_layout.addWidget(separator)
        
        # === BOTTOM SECTION: Action Buttons (all 4 in a row) ===
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        # Enter Trade button
        self.btn_enter = QPushButton("📈 Trade")
        self.btn_enter.setFixedHeight(26)
        self.btn_enter.setMinimumWidth(70)
        self.btn_enter.setStyleSheet(
            "background-color: #1B5E20; color: white; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        self.btn_enter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enter.clicked.connect(self._on_enter_clicked)
        btn_layout.addWidget(self.btn_enter)
        
        # Square Off button
        self.btn_square_off = QPushButton("📉 Exit")
        self.btn_square_off.setFixedHeight(26)
        self.btn_square_off.setMinimumWidth(70)
        self.btn_square_off.setStyleSheet(
            "background-color: #B71C1C; color: white; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        self.btn_square_off.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_square_off.clicked.connect(self._on_square_off_clicked)
        btn_layout.addWidget(self.btn_square_off)
        
        # Basic Analyze button
        self.btn_basic_analyze = QPushButton("📊 Basic")
        self.btn_basic_analyze.setFixedHeight(26)
        self.btn_basic_analyze.setMinimumWidth(70)
        self.btn_basic_analyze.setStyleSheet(
            "background-color: #1565C0; color: white; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        self.btn_basic_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_basic_analyze.clicked.connect(self._on_basic_analyze_clicked)
        self.btn_basic_analyze.setToolTip("Basic Greeks Analysis")
        btn_layout.addWidget(self.btn_basic_analyze)
        
        # Enhanced Analyze button
        self.btn_enhanced_analyze = QPushButton("📈 Full")
        self.btn_enhanced_analyze.setFixedHeight(26)
        self.btn_enhanced_analyze.setMinimumWidth(70)
        self.btn_enhanced_analyze.setStyleSheet(
            "background-color: #7B1FA2; color: white; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        self.btn_enhanced_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enhanced_analyze.clicked.connect(self._on_enhanced_analyze_clicked)
        self.btn_enhanced_analyze.setToolTip("Full Technical + Greeks Analysis")
        btn_layout.addWidget(self.btn_enhanced_analyze)
        
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        
        # Widget styling with bottom border for separation
        self.setStyleSheet("""
            AlertItemWidget {
                background-color: #1E1E1E;
                border-bottom: 2px solid #333;
                padding-bottom: 4px;
            }
            AlertItemWidget:hover {
                background-color: #252525;
            }
        """)
    
    def _on_enter_clicked(self):
        if not self.is_traded:
            self.enter_trade_clicked.emit(self.alert_data)
    
    def _on_square_off_clicked(self):
        self.square_off_clicked.emit(self.alert_data)
    
    def _on_basic_analyze_clicked(self):
        self.basic_analyze_clicked.emit(self.alert_data)
    
    def _on_enhanced_analyze_clicked(self):
        self.enhanced_analyze_clicked.emit(self.alert_data)
    
    def mark_as_traded(self):
        """Mark this alert as traded (entered into trade)."""
        self.is_traded = True
        self.status_label.setText("✅")
        self.status_label.setToolTip("Trade Entered")
        self.btn_enter.setEnabled(False)
        self.btn_enter.setStyleSheet(
            "background-color: #333; color: #666; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        # Dim the main label to indicate traded status
        self.main_label.setStyleSheet(
            "color: #888; font-weight: normal; font-size: 13px;"
        )
        self.details_label.setStyleSheet("color: #666; font-size: 11px;")
        # Add a visual background indicator
        self.setStyleSheet("""
            AlertItemWidget {
                background-color: #1a3320;
                border-bottom: 2px solid #2e5a3a;
                padding-bottom: 4px;
            }
        """)
    
    def mark_as_squared_off(self):
        """Mark this alert as used for square off."""
        self.is_squared_off = True
        self.status_label.setText("🔴")
        self.status_label.setToolTip("Squared Off")
        self.btn_square_off.setEnabled(False)
        self.btn_square_off.setStyleSheet(
            "background-color: #333; color: #666; border-radius: 4px; font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        # Add a visual background indicator
        self.setStyleSheet("""
            AlertItemWidget {
                background-color: #3d1a1a;
                border-bottom: 2px solid #5a2e2e;
                padding-bottom: 4px;
            }
        """)
    
    def set_token(self, token: int):
        """Set the instrument token for this alert (for LTP updates)."""
        self.token = token
    
    def update_ltp(self, ltp: float):
        """
        Update the LTP display with live price.
        Colors: Green if price up, Red if down, White if unchanged.
        """
        # Format LTP text
        self.ltp_label.setText(f"LTP: ₹{ltp:.2f}")
        
        # Determine color based on price change
        if self.last_ltp > 0:
            if ltp > self.last_ltp:
                # Price went up - green
                self.ltp_label.setStyleSheet(
                    "color: #00E676; font-size: 12px; font-weight: bold; "
                    "background-color: #1a3320; padding: 2px 8px; border-radius: 3px;"
                )
            elif ltp < self.last_ltp:
                # Price went down - red
                self.ltp_label.setStyleSheet(
                    "color: #FF5252; font-size: 12px; font-weight: bold; "
                    "background-color: #3d1a1a; padding: 2px 8px; border-radius: 3px;"
                )
            else:
                # No change - neutral
                self.ltp_label.setStyleSheet(
                    "color: #FFF; font-size: 12px; font-weight: bold; "
                    "background-color: #2a2a2a; padding: 2px 8px; border-radius: 3px;"
                )
        else:
            # First update - neutral white
            self.ltp_label.setStyleSheet(
                "color: #FFF; font-size: 12px; font-weight: bold; "
                "background-color: #2a2a2a; padding: 2px 8px; border-radius: 3px;"
            )
        
        # Store for next comparison
        self.last_ltp = ltp
        
        # Also update the alert_data for reference
        self.alert_data['current_ltp'] = ltp


class MainWindow(QMainWindow):
    # Signal emitted when "Exit" button is clicked - now sends order_id (str)
    square_off_signal = pyqtSignal(str)
    
    # Config profile signals
    profile_save_signal = pyqtSignal(str)      # Emitted when save button clicked (profile name)
    profile_load_signal = pyqtSignal(str)      # Emitted when profile selected (profile name)
    profile_delete_signal = pyqtSignal(str)    # Emitted when delete button clicked (profile name)
    
    # Alert action signals (user-initiated trading)
    enter_trade_signal = pyqtSignal(dict)      # Emitted when user clicks "Enter Trade" (alert_data)
    square_off_with_alert_signal = pyqtSignal(dict)  # Emitted when user clicks "Square Off" (alert_data)
    
    # Analysis report signals
    basic_analyze_signal = pyqtSignal(dict)    # Emitted when user clicks "Basic" analyze (alert_data)
    enhanced_analyze_signal = pyqtSignal(dict) # Emitted when user clicks "Full" analyze (alert_data)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Indian Options Paper Trader (v2.0)")
        self.resize(1400, 900)
        
        # Dark Theme Styling
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; color: #E0E0E0; }
            QWidget { background-color: #121212; color: #E0E0E0; }
            QFrame { border: 1px solid #333; border-radius: 6px; }
            QLabel { color: #E0E0E0; border: none; }
            QTableWidget { 
                background-color: #1E1E1E; 
                gridline-color: #333; 
                border: none;
                selection-background-color: #333;
            }
            QHeaderView::section { 
                background-color: #2C2C2C; 
                padding: 6px; 
                border: none; 
                color: #AAA;
                font-weight: bold;
            }
            QTextEdit { 
                background-color: #000; 
                color: #00E676; 
                font-family: Consolas, monospace; 
                border: 1px solid #333; 
            }
            QListWidget {
                background-color: #1E1E1E;
                border: 1px solid #333;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)

        # Main Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(10)

        # 1. HEADER
        self._setup_header()

        # 2. CONTENT (Split View)
        self.content_layout = QHBoxLayout()
        self._setup_alert_feed()
        self._setup_positions_table()
        self.main_layout.addLayout(self.content_layout)

        # 3. LOGS
        self._setup_logs()

        # 4. FOOTER (Buttons)
        self._setup_footer()

        # Row Tracker: Maps Order ID -> Row Index (for fast updates)
        self.row_map = {}

    def _setup_header(self):
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #1E1E1E; padding: 10px;")
        header_layout = QHBoxLayout(header_frame)

        # Left: Connection Status
        status_layout = QVBoxLayout()
        status_layout.setSpacing(2)
        self.lbl_status = QLabel("🔴 API: Disconnected")
        self.lbl_status.setStyleSheet("color: #FF5252; font-weight: bold; font-size: 12px;")
        status_layout.addWidget(self.lbl_status)
        
        # Tick counter (to verify API is responding)
        self.lbl_tick_count = QLabel("Ticks: 0")
        self.lbl_tick_count.setStyleSheet("color: #666; font-size: 10px;")
        status_layout.addWidget(self.lbl_tick_count)
        self._tick_count = 0
        
        header_layout.addLayout(status_layout)
        
        # Live Ticker Section (between status and P&L)
        ticker_frame = QFrame()
        ticker_frame.setStyleSheet("border: 1px solid #333; background-color: #252525; border-radius: 4px;")
        ticker_layout = QVBoxLayout(ticker_frame)
        ticker_layout.setContentsMargins(8, 4, 8, 4)
        ticker_layout.setSpacing(2)
        
        ticker_header = QLabel("📊 LIVE TICKER")
        ticker_header.setStyleSheet("color: #888; font-size: 9px; font-weight: bold; border: none;")
        ticker_layout.addWidget(ticker_header)
        
        # Ticker items container (horizontal layout for multiple symbols)
        self.ticker_items_layout = QHBoxLayout()
        self.ticker_items_layout.setSpacing(12)
        ticker_layout.addLayout(self.ticker_items_layout)
        
        # Placeholder when no tickers are subscribed
        self.lbl_ticker_placeholder = QLabel("⏳ Waiting for connection...")
        self.lbl_ticker_placeholder.setStyleSheet("color: #FFA726; font-size: 11px; font-style: italic; border: none;")
        self.ticker_items_layout.addWidget(self.lbl_ticker_placeholder)
        
        # Store ticker labels: {token: (symbol_label, price_label, change_label)}
        self._ticker_labels = {}
        
        header_layout.addWidget(ticker_frame)
        
        # Center: P&L Summary
        pnl_frame = QFrame()
        pnl_frame.setStyleSheet("border: none;")
        pnl_layout = QVBoxLayout(pnl_frame)
        pnl_layout.setSpacing(2)
        
        self.lbl_total_pnl = QLabel("NET P&L: ₹ 0.00")
        self.lbl_total_pnl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.lbl_total_pnl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Breakdown row
        breakdown_layout = QHBoxLayout()
        self.lbl_realized = QLabel("Realized: ₹0.00")
        self.lbl_realized.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_unrealized = QLabel("Unrealized: ₹0.00")
        self.lbl_unrealized.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_fees = QLabel("Fees: ₹0.00")
        self.lbl_fees.setStyleSheet("color: #FF9800; font-size: 11px;")
        
        breakdown_layout.addWidget(self.lbl_realized)
        breakdown_layout.addWidget(QLabel("|"))
        breakdown_layout.addWidget(self.lbl_unrealized)
        breakdown_layout.addWidget(QLabel("|"))
        breakdown_layout.addWidget(self.lbl_fees)
        
        pnl_layout.addWidget(self.lbl_total_pnl)
        pnl_layout.addLayout(breakdown_layout)
        
        # Right: Clock
        self.lbl_time = QLabel("00:00:00 IST")
        self.lbl_time.setStyleSheet("color: #B0BEC5; font-size: 12px;")

        header_layout.addStretch()
        header_layout.addWidget(pnl_frame)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_time)
        
        self.main_layout.addWidget(header_frame)
        
        # Clock Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_clock)
        self.timer.start(1000)

    def _setup_alert_feed(self):
        layout = QVBoxLayout()
        
        header = QLabel("📡 Signal Inbox")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)
        
        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("⚪ Pending"))
        legend_layout.addWidget(QLabel("✅ Traded"))
        legend_layout.addWidget(QLabel("🔴 Exited"))
        legend_layout.addStretch()
        for i in range(legend_layout.count()):
            widget = legend_layout.itemAt(i).widget()
            if widget:
                widget.setStyleSheet("color: #888; font-size: 10px;")
        layout.addLayout(legend_layout)
        
        # Scrollable container for alert items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #333;
                background-color: #1E1E1E;
            }
            QScrollBar:vertical {
                background-color: #1E1E1E;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background-color: #444;
                border-radius: 4px;
            }
        """)
        
        # Container widget for alerts
        self.alert_container = QWidget()
        self.alert_layout = QVBoxLayout(self.alert_container)
        self.alert_layout.setContentsMargins(4, 4, 4, 4)
        self.alert_layout.setSpacing(4)
        self.alert_layout.addStretch()  # Push items to top
        
        scroll_area.setWidget(self.alert_container)
        layout.addWidget(scroll_area)
        
        # Store alert widgets for management
        self._alert_widgets = []  # List of AlertItemWidget
        
        # Add to Content Layout (30% width for more space)
        self.content_layout.addLayout(layout, 30)

    def _setup_positions_table(self):
        layout = QVBoxLayout()
        
        header = QLabel("📊 Active Positions")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Lots", "Qty", "Avg Price", 
            "LTP", "SL", "Target", "Net P&L", "Action"
        ])
        
        # Enable interactive column resizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)  # Last column (Action) stretches
        
        # Set minimum and default column widths
        header.setMinimumSectionSize(50)
        self.table.setColumnWidth(0, 180)   # Symbol - wider for long names
        self.table.setColumnWidth(1, 60)    # Side
        self.table.setColumnWidth(2, 50)    # Lots
        self.table.setColumnWidth(3, 60)    # Qty
        self.table.setColumnWidth(4, 90)    # Avg Price
        self.table.setColumnWidth(5, 80)    # LTP
        self.table.setColumnWidth(6, 80)    # SL
        self.table.setColumnWidth(7, 80)    # Target
        self.table.setColumnWidth(8, 90)    # Net P&L
        self.table.setColumnWidth(9, 70)    # Action
        
        # Enable horizontal scrollbar when needed
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Show tooltips for truncated text
        self.table.setMouseTracking(True)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget::item:alternate { background-color: #252525; }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                padding: 6px;
                border: 1px solid #333;
                font-weight: bold;
            }
            QHeaderView::section:hover {
                background-color: #3a3a3a;
            }
        """)
        
        layout.addWidget(self.table)
        
        # Add to Content Layout (70% width)
        self.content_layout.addLayout(layout, 70)

    def _setup_logs(self):
        log_header = QLabel("📋 Activity Log")
        log_header.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.main_layout.addWidget(log_header)
        
        self.log_box = QTextEdit()
        self.log_box.setMaximumHeight(140)
        self.log_box.setReadOnly(True)
        self.main_layout.addWidget(self.log_box)

    def _setup_footer(self):
        footer_layout = QHBoxLayout()
        
        # Square off all button
        self.btn_square_off_all = QPushButton("🚫 Square Off All")
        self.btn_square_off_all.setStyleSheet(
            "background-color: #B71C1C; color: white; padding: 10px 20px;"
        )
        
        footer_layout.addWidget(self.btn_square_off_all)
        
        # Config Profile Group
        profile_group = QGroupBox("Config Profile")
        profile_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #888;
            }
        """)
        profile_layout = QHBoxLayout(profile_group)
        profile_layout.setContentsMargins(8, 4, 8, 4)
        
        # Profile dropdown
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.setStyleSheet("""
            QComboBox {
                background-color: #2C2C2C;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
                color: #E0E0E0;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #888;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #2C2C2C;
                border: 1px solid #444;
                selection-background-color: #444;
            }
        """)
        self.profile_combo.addItem("-- Select Profile --")
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        
        # Save profile button
        self.btn_save_profile = QPushButton("💾 Save")
        self.btn_save_profile.setStyleSheet(
            "background-color: #1565C0; color: white; padding: 6px 12px;"
        )
        self.btn_save_profile.clicked.connect(self._on_save_profile_clicked)
        
        # Delete profile button
        self.btn_delete_profile = QPushButton("🗑️ Delete")
        self.btn_delete_profile.setStyleSheet(
            "background-color: #616161; color: white; padding: 6px 12px;"
        )
        self.btn_delete_profile.clicked.connect(self._on_delete_profile_clicked)
        
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addWidget(self.btn_save_profile)
        profile_layout.addWidget(self.btn_delete_profile)
        
        footer_layout.addWidget(profile_group)
        footer_layout.addStretch()
        
        # Report buttons
        self.btn_pdf = QPushButton("📄 Download PDF")
        self.btn_excel = QPushButton("📊 Download Excel")
        
        self.btn_pdf.setStyleSheet("background-color: #D32F2F; color: white;")
        self.btn_excel.setStyleSheet("background-color: #1B5E20; color: white;")
        
        footer_layout.addWidget(self.btn_pdf)
        footer_layout.addWidget(self.btn_excel)
        self.main_layout.addLayout(footer_layout)

    # --- UI Logic ---

    def _update_clock(self):
        now = datetime.datetime.now().strftime("%H:%M:%S IST")
        self.lbl_time.setText(now)

    def update_status(self, connected, msg):
        if connected:
            self.lbl_status.setText(f"🟢 API: Connected")
            self.lbl_status.setStyleSheet("color: #00E676; font-weight: bold; font-size: 12px;")
        else:
            self.lbl_status.setText(f"🔴 API: {msg}")
            self.lbl_status.setStyleSheet("color: #FF5252; font-weight: bold; font-size: 12px;")
    
    # --- Live Ticker Methods ---
    
    def add_ticker_symbol(self, token: int, symbol_name: str):
        """
        Add a symbol to the live ticker display.
        
        Args:
            token: Instrument token
            symbol_name: Display name (e.g., "NIFTY 26200 CE")
        """
        if token in self._ticker_labels:
            return  # Already added
        
        # Hide placeholder
        self.lbl_ticker_placeholder.hide()
        
        # Create ticker item widget
        item_widget = QWidget()
        item_widget.setStyleSheet("border: none;")
        item_layout = QVBoxLayout(item_widget)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(0)
        
        # Symbol name
        lbl_symbol = QLabel(symbol_name)
        lbl_symbol.setStyleSheet("color: #B0BEC5; font-size: 10px; font-weight: bold; border: none;")
        item_layout.addWidget(lbl_symbol)
        
        # Price and change row
        price_row = QHBoxLayout()
        price_row.setSpacing(4)
        
        lbl_price = QLabel("---")
        lbl_price.setStyleSheet("color: #FFF; font-size: 14px; font-weight: bold; border: none;")
        price_row.addWidget(lbl_price)
        
        lbl_change = QLabel("")
        lbl_change.setStyleSheet("color: #888; font-size: 10px; border: none;")
        price_row.addWidget(lbl_change)
        
        item_layout.addLayout(price_row)
        
        # Store labels for updates
        self._ticker_labels[token] = {
            'widget': item_widget,
            'symbol': lbl_symbol,
            'price': lbl_price,
            'change': lbl_change,
            'last_price': 0.0
        }
        
        # Add to ticker layout
        self.ticker_items_layout.addWidget(item_widget)
    
    def update_ticker_price(self, token: int, ltp: float, change_pct: float = 0.0):
        """
        Update the price for a ticker symbol.
        
        Args:
            token: Instrument token
            ltp: Last traded price
            change_pct: Percentage change (optional)
        """
        if token not in self._ticker_labels:
            return
        
        ticker_data = self._ticker_labels[token]
        last_price = ticker_data['last_price']
        
        # Update price label
        ticker_data['price'].setText(f"₹{ltp:.2f}")
        
        # Color based on price movement
        if last_price > 0:
            if ltp > last_price:
                ticker_data['price'].setStyleSheet("color: #00E676; font-size: 14px; font-weight: bold; border: none;")
            elif ltp < last_price:
                ticker_data['price'].setStyleSheet("color: #FF5252; font-size: 14px; font-weight: bold; border: none;")
            else:
                ticker_data['price'].setStyleSheet("color: #FFF; font-size: 14px; font-weight: bold; border: none;")
        
        # Update change label
        if change_pct != 0:
            change_color = "#00E676" if change_pct >= 0 else "#FF5252"
            sign = "+" if change_pct >= 0 else ""
            ticker_data['change'].setText(f"({sign}{change_pct:.2f}%)")
            ticker_data['change'].setStyleSheet(f"color: {change_color}; font-size: 10px; border: none;")
        
        # Store last price
        ticker_data['last_price'] = ltp
        
        # Update tick counter
        self._tick_count += 1
        self.lbl_tick_count.setText(f"Ticks: {self._tick_count}")
        self.lbl_tick_count.setStyleSheet("color: #00E676; font-size: 10px;")
    
    def clear_tickers(self):
        """Remove all ticker symbols."""
        for token, data in self._ticker_labels.items():
            data['widget'].deleteLater()
        self._ticker_labels.clear()
        self.lbl_ticker_placeholder.show()
        self._tick_count = 0
        self.lbl_tick_count.setText("Ticks: 0")
        self.lbl_tick_count.setStyleSheet("color: #666; font-size: 10px;")
    
    def set_ticker_status(self, status: str, color: str = "#FFA726"):
        """Update ticker placeholder status message."""
        self.lbl_ticker_placeholder.setText(status)
        self.lbl_ticker_placeholder.setStyleSheet(f"color: {color}; font-size: 11px; font-style: italic; border: none;")

    def add_alert(self, alert_data):
        """Add an alert to the inbox with inline action buttons."""
        # Create custom alert widget
        alert_widget = AlertItemWidget(alert_data)
        
        # Connect signals
        alert_widget.enter_trade_clicked.connect(self._on_alert_enter_trade)
        alert_widget.square_off_clicked.connect(self._on_alert_square_off)
        alert_widget.basic_analyze_clicked.connect(self._on_alert_basic_analyze)
        alert_widget.enhanced_analyze_clicked.connect(self._on_alert_enhanced_analyze)
        
        # Insert at the top (before the stretch)
        self._alert_widgets.insert(0, alert_widget)
        self.alert_layout.insertWidget(0, alert_widget)
    
    def _on_alert_enter_trade(self, alert_data):
        """Handle Enter Trade button click on an alert item."""
        # Emit signal - marking will be done by controller after successful trade
        self.enter_trade_signal.emit(alert_data)
    
    def _on_alert_square_off(self, alert_data):
        """Handle Square Off button click on an alert item."""
        # Emit signal - marking will be done by controller after successful square off
        self.square_off_with_alert_signal.emit(alert_data)
    
    def _on_alert_basic_analyze(self, alert_data):
        """Handle Basic Analyze button click on an alert item."""
        self.basic_analyze_signal.emit(alert_data)
    
    def _on_alert_enhanced_analyze(self, alert_data):
        """Handle Enhanced Analyze button click on an alert item."""
        self.enhanced_analyze_signal.emit(alert_data)
    
    def mark_alert_as_traded(self, alert_data):
        """Mark an alert as traded (called from controller after successful trade)."""
        for widget in self._alert_widgets:
            if widget.alert_data == alert_data:
                widget.mark_as_traded()
                break
    
    def mark_alert_as_squared_off(self, alert_data):
        """Mark an alert as squared off (called from controller after successful exit)."""
        for widget in self._alert_widgets:
            if widget.alert_data == alert_data:
                widget.mark_as_squared_off()
                break
    
    def set_alert_token(self, alert_data: dict, token: int):
        """
        Set the token for an alert widget to enable LTP updates.
        
        Args:
            alert_data: The alert data dict to find the widget
            token: The instrument token for this alert
        """
        for widget in self._alert_widgets:
            if widget.alert_data == alert_data:
                widget.set_token(token)
                break
    
    def update_alert_ltp(self, token: int, ltp: float):
        """
        Update LTP for all alert widgets with matching token.
        
        Args:
            token: Instrument token
            ltp: Last traded price
        """
        for widget in self._alert_widgets:
            if widget.token == token:
                widget.update_ltp(ltp)
    
    def get_alert_tokens(self) -> dict:
        """
        Get all alert widgets that need token mapping.
        
        Returns:
            Dict mapping alert index to alert_data for alerts without tokens
        """
        pending = {}
        for i, widget in enumerate(self._alert_widgets):
            if widget.token is None:
                pending[i] = widget.alert_data
        return pending
    
    def clear_alerts(self):
        """Clear all alerts from the inbox."""
        for widget in self._alert_widgets:
            self.alert_layout.removeWidget(widget)
            widget.deleteLater()
        self._alert_widgets.clear()
    
    def show_analysis_report(self, title: str, report_text: str):
        """Show an analysis report in a popup dialog."""
        dialog = AnalysisReportDialog(title, report_text, self)
        dialog.exec()

    def add_position_row(self, order):
        """
        Add a new position row to the table.
        Uses order_id as the unique key (supports multiple orders per token).
        """
        order_id = order['id']
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.row_map[order_id] = row

        def item(text, color="#E0E0E0"):
            i = QTableWidgetItem(str(text))
            i.setForeground(QColor(color))
            i.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            i.setFlags(i.flags() & ~Qt.ItemFlag.ItemIsEditable)
            i.setToolTip(str(text))  # Show full text on hover
            return i

        # Symbol
        self.table.setItem(row, 0, item(order['symbol']))
        
        # Side (colored)
        side_color = "#00E676" if order['action'] == "BUY" else "#FF5252"
        self.table.setItem(row, 1, item(order['action'], side_color))
        
        # Lots
        lots = order.get('lots', order['quantity'] // order.get('lot_size', 1))
        self.table.setItem(row, 2, item(lots))
        
        # Quantity
        self.table.setItem(row, 3, item(order['quantity']))
        
        # Avg Price
        self.table.setItem(row, 4, item(f"₹{order['entry_price']:.2f}"))
        
        # LTP (placeholder)
        self.table.setItem(row, 5, item("---"))
        
        # SL
        sl = order.get('stop_loss')
        sl_text = f"₹{sl:.2f}" if sl else "---"
        self.table.setItem(row, 6, item(sl_text, "#FF9800" if sl else "#666"))
        
        # Target
        target = order.get('target')
        target_text = f"₹{target:.2f}" if target else "---"
        self.table.setItem(row, 7, item(target_text, "#2196F3" if target else "#666"))
        
        # Net P&L (placeholder)
        self.table.setItem(row, 8, item("₹0.00"))

        # Exit Button
        btn = QPushButton("EXIT")
        btn.setStyleSheet(
            "background-color: #B71C1C; color: white; border: none; "
            "padding: 4px 8px; font-size: 11px;"
        )
        # Connect with explicit signal emission and debug print
        def emit_exit(checked, oid=order_id):
            print(f"[DEBUG] Exit button clicked for order: {oid}")
            self.square_off_signal.emit(oid)
        btn.clicked.connect(emit_exit)
        self.table.setCellWidget(row, 9, btn)

    def update_pnl_cell(self, data):
        """
        Update LTP and P&L for a position.
        data = {'order_id': 'ORD_1', 'token': 123, 'ltp': 150.0, 'net_pnl': 500.0, ...}
        """
        order_id = data.get('order_id')
        
        if order_id and order_id in self.row_map:
            row = self.row_map[order_id]
            
            # Update LTP
            ltp = data.get('ltp', 0)
            ltp_item = self.table.item(row, 5)
            if ltp_item:
                ltp_item.setText(f"₹{ltp:.2f}")
            
            # Update Net P&L
            net_pnl = data.get('net_pnl', 0)
            pnl_item = self.table.item(row, 8)
            if pnl_item:
                pnl_item.setText(f"₹{net_pnl:.2f}")
                if net_pnl >= 0:
                    pnl_item.setForeground(QColor("#00E676"))
                else:
                    pnl_item.setForeground(QColor("#FF5252"))

    def remove_position_row(self, order_id: str):
        """Remove a position row when it's closed."""
        if order_id in self.row_map:
            row = self.row_map[order_id]
            self.table.removeRow(row)
            del self.row_map[order_id]
            
            # Update row indices for remaining entries
            updated_map = {}
            for oid, r in self.row_map.items():
                if r > row:
                    updated_map[oid] = r - 1
                else:
                    updated_map[oid] = r
            self.row_map = updated_map

    def update_total_pnl(self, pnl_data):
        """
        Update the header P&L display.
        pnl_data = {'realized': 100.0, 'unrealized': 50.0, 'total': 150.0, 'fees_paid': 20.0}
        """
        realized = pnl_data.get('realized', 0)
        unrealized = pnl_data.get('unrealized', 0)
        total = pnl_data.get('total', realized + unrealized)
        fees = pnl_data.get('fees_paid', 0)
        
        # Update main P&L
        self.lbl_total_pnl.setText(f"NET P&L: ₹{total:,.2f}")
        if total >= 0:
            self.lbl_total_pnl.setStyleSheet("color: #00E676; font-size: 20px;")
        else:
            self.lbl_total_pnl.setStyleSheet("color: #FF5252; font-size: 20px;")
        
        # Update breakdown
        self.lbl_realized.setText(f"Realized: ₹{realized:,.2f}")
        if realized >= 0:
            self.lbl_realized.setStyleSheet("color: #00E676; font-size: 11px;")
        else:
            self.lbl_realized.setStyleSheet("color: #FF5252; font-size: 11px;")
            
        self.lbl_unrealized.setText(f"Unrealized: ₹{unrealized:,.2f}")
        if unrealized >= 0:
            self.lbl_unrealized.setStyleSheet("color: #00E676; font-size: 11px;")
        else:
            self.lbl_unrealized.setStyleSheet("color: #FF5252; font-size: 11px;")
            
        self.lbl_fees.setText(f"Fees: ₹{fees:,.2f}")

    def update_net_pnl(self, total_pnl):
        """Legacy method for backward compatibility."""
        self.update_total_pnl({'total': total_pnl})

    def show_notification(self, title: str, message: str, msg_type: str = "info"):
        """Show a notification popup."""
        if msg_type == "info":
            QMessageBox.information(self, title, message)
        elif msg_type == "warning":
            QMessageBox.warning(self, title, message)
        elif msg_type == "error":
            QMessageBox.critical(self, title, message)

    def append_log(self, msg):
        """Append a message to the log panel."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{ts}] {msg}")
        # Auto-scroll to bottom
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )
    
    # --- Config Profile Methods ---
    
    def set_profile_list(self, profiles: list):
        """
        Populate the profile dropdown with available profiles.
        
        Args:
            profiles: List of profile names
        """
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("-- Select Profile --")
        for profile in profiles:
            self.profile_combo.addItem(profile)
        self.profile_combo.blockSignals(False)
    
    def add_profile(self, name: str):
        """Add a new profile to the dropdown."""
        # Check if already exists
        for i in range(self.profile_combo.count()):
            if self.profile_combo.itemText(i) == name:
                return
        self.profile_combo.addItem(name)
    
    def remove_profile(self, name: str):
        """Remove a profile from the dropdown."""
        for i in range(self.profile_combo.count()):
            if self.profile_combo.itemText(i) == name:
                self.profile_combo.removeItem(i)
                break
    
    def get_selected_profile(self) -> str:
        """Get the currently selected profile name."""
        text = self.profile_combo.currentText()
        if text == "-- Select Profile --":
            return ""
        return text
    
    def _on_profile_selected(self, text: str):
        """Handle profile selection change."""
        if text and text != "-- Select Profile --":
            self.profile_load_signal.emit(text)
    
    def _on_save_profile_clicked(self):
        """Handle save profile button click."""
        name, ok = QInputDialog.getText(
            self,
            "Save Config Profile",
            "Enter profile name:",
            text="my_config"
        )
        
        if ok and name:
            # Validate name
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "Invalid Name", "Profile name cannot be empty.")
                return
            
            # Check for overwrite
            for i in range(self.profile_combo.count()):
                if self.profile_combo.itemText(i) == name:
                    reply = QMessageBox.question(
                        self,
                        "Overwrite Profile?",
                        f"Profile '{name}' already exists. Overwrite?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    break
            
            self.profile_save_signal.emit(name)
            self.add_profile(name)
            self.append_log(f"💾 Config profile saved: {name}")
    
    def _on_delete_profile_clicked(self):
        """Handle delete profile button click."""
        name = self.get_selected_profile()
        
        if not name:
            QMessageBox.warning(
                self,
                "No Profile Selected",
                "Please select a profile to delete."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Profile?",
            f"Are you sure you want to delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.profile_delete_signal.emit(name)
            self.remove_profile(name)
            self.profile_combo.setCurrentIndex(0)
            self.append_log(f"🗑️ Config profile deleted: {name}")
