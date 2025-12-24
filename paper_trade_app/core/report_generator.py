"""
Report Generator for Paper Trading Application

Generates PDF and Excel reports with:
- Trade details (entry, exit, P&L)
- Fee breakdown
- Session summary
- Realized vs Unrealized P&L
"""

import pandas as pd
from fpdf import FPDF
import datetime
import os
import logging

# Ensure reports directory exists
REPORT_DIR = "reports"
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

logger = logging.getLogger("ReportGen")


class ReportGenerator:
    def __init__(self):
        self.logger = logger

    def _get_timestamp(self):
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def _prepare_dataframe(self, trade_data):
        """Convert trade data to DataFrame with proper column handling."""
        if not trade_data:
            return None
        
        df = pd.DataFrame(trade_data)
        
        # Handle nested structures if any
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to convert datetime objects to strings
                try:
                    df[col] = df[col].apply(
                        lambda x: str(x) if not isinstance(x, (str, int, float, type(None))) else x
                    )
                except:
                    pass
        
        return df

    def export_excel(self, trade_data):
        """
        Exports list of trade dictionaries to Excel with formatting.
        Includes new Tier 1/2 fields: fees, net_pnl, SL, target, exit_reason.
        """
        if not trade_data:
            return None, "No data to export"

        try:
            filename = f"TradeReport_{self._get_timestamp()}.xlsx"
            filepath = os.path.join(REPORT_DIR, filename)

            df = self._prepare_dataframe(trade_data)
            
            # Define columns in order of importance
            desired_columns = [
                'id', 'symbol', 'action', 'lots', 'quantity', 
                'entry_price', 'exit_price', 'stop_loss', 'target',
                'gross_pnl', 'entry_fees', 'exit_fees', 'net_pnl',
                'status', 'exit_reason', 'entry_time', 'exit_time'
            ]
            
            # Filter to columns that exist
            available_cols = [c for c in desired_columns if c in df.columns]
            
            # Add any remaining columns not in our list
            remaining_cols = [c for c in df.columns if c not in available_cols]
            all_cols = available_cols + remaining_cols
            
            # Exclude internal columns
            exclude_cols = ['token', 'lot_size', 'placed_at', 'validity', 'sl_order_type', 'ltp']
            final_cols = [c for c in all_cols if c not in exclude_cols]
            
            df = df[final_cols]

            # Calculate summary statistics
            total_gross_pnl = df['gross_pnl'].sum() if 'gross_pnl' in df.columns else 0
            total_net_pnl = df['net_pnl'].sum() if 'net_pnl' in df.columns else 0
            total_entry_fees = df['entry_fees'].sum() if 'entry_fees' in df.columns else 0
            total_exit_fees = df['exit_fees'].sum() if 'exit_fees' in df.columns else 0
            total_fees = total_entry_fees + total_exit_fees

            # Write to Excel with multiple sheets
            with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                # Sheet 1: Trade Details
                df.to_excel(writer, sheet_name='Trades', index=False)
                
                # Sheet 2: Summary
                summary_data = {
                    'Metric': [
                        'Total Trades',
                        'Winning Trades',
                        'Losing Trades',
                        'Gross P&L',
                        'Total Fees',
                        'Net P&L',
                        'Win Rate (%)'
                    ],
                    'Value': [
                        len(df),
                        len(df[df.get('net_pnl', df.get('gross_pnl', pd.Series([0]))) > 0]) if 'net_pnl' in df.columns or 'gross_pnl' in df.columns else 0,
                        len(df[df.get('net_pnl', df.get('gross_pnl', pd.Series([0]))) < 0]) if 'net_pnl' in df.columns or 'gross_pnl' in df.columns else 0,
                        f"₹{total_gross_pnl:,.2f}",
                        f"₹{total_fees:,.2f}",
                        f"₹{total_net_pnl:,.2f}",
                        f"{(len(df[df.get('net_pnl', pd.Series([0])) > 0]) / len(df) * 100):.1f}%" if len(df) > 0 and 'net_pnl' in df.columns else "N/A"
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Formatting
                workbook = writer.book
                
                # Trades sheet formatting
                worksheet = writer.sheets['Trades']
                header_fmt = workbook.add_format({
                    'bold': True, 
                    'bg_color': '#2C2C2C', 
                    'font_color': 'white',
                    'border': 1
                })
                currency_fmt = workbook.add_format({'num_format': '₹ #,##0.00'})
                
                # Apply header format
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)
                
                # Apply currency format to price/pnl columns
                currency_cols = ['entry_price', 'exit_price', 'stop_loss', 'target', 
                               'gross_pnl', 'entry_fees', 'exit_fees', 'net_pnl']
                for col_name in currency_cols:
                    if col_name in df.columns:
                        idx = df.columns.get_loc(col_name)
                        worksheet.set_column(idx, idx, 15, currency_fmt)
                
                # Summary sheet formatting
                summary_ws = writer.sheets['Summary']
                summary_header_fmt = workbook.add_format({
                    'bold': True,
                    'bg_color': '#1B5E20',
                    'font_color': 'white',
                    'border': 1
                })
                for col_num, value in enumerate(summary_df.columns.values):
                    summary_ws.write(0, col_num, value, summary_header_fmt)
                summary_ws.set_column(0, 0, 20)
                summary_ws.set_column(1, 1, 20)

            return filepath, "Success"

        except Exception as e:
            self.logger.error(f"Excel export error: {e}")
            import traceback
            traceback.print_exc()
            return None, str(e)

    def export_pdf(self, trade_data):
        """
        Generates a PDF summary of the trading session.
        Includes fee breakdown and exit reasons.
        """
        if not trade_data:
            return None, "No data to export"

        try:
            filename = f"TradeReport_{self._get_timestamp()}.pdf"
            filepath = os.path.join(REPORT_DIR, filename)
            
            df = self._prepare_dataframe(trade_data)
            
            # Calculate summary statistics
            total_gross_pnl = df['gross_pnl'].sum() if 'gross_pnl' in df.columns else 0
            total_net_pnl = df['net_pnl'].sum() if 'net_pnl' in df.columns else 0
            total_entry_fees = df['entry_fees'].sum() if 'entry_fees' in df.columns else 0
            total_exit_fees = df['exit_fees'].sum() if 'exit_fees' in df.columns else 0
            total_fees = total_entry_fees + total_exit_fees
            
            # Count by exit reason
            exit_reasons = df['exit_reason'].value_counts().to_dict() if 'exit_reason' in df.columns else {}

            # --- PDF Structure ---
            class TradePDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 18)
                    self.set_text_color(30, 30, 30)
                    self.cell(0, 12, 'Paper Trading Session Report', 0, 1, 'C')
                    self.set_font('Arial', '', 10)
                    self.set_text_color(100, 100, 100)
                    self.cell(0, 6, f'Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
                    self.ln(5)

                def footer(self):
                    self.set_y(-15)
                    self.set_font('Arial', 'I', 8)
                    self.set_text_color(150, 150, 150)
                    self.cell(0, 10, f'Page {self.page_no()} | Indian Options Paper Trader', 0, 0, 'C')

            pdf = TradePDF()
            pdf.add_page()
            
            # --- Section 1: Summary Box ---
            pdf.set_fill_color(240, 240, 240)
            pdf.set_draw_color(200, 200, 200)
            pdf.rect(10, pdf.get_y(), 190, 50, 'D')
            
            pdf.set_font("Arial", 'B', 12)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 10, "Session Summary", 0, 1)
            
            # Summary content
            pdf.set_font("Arial", '', 11)
            y_start = pdf.get_y()
            
            # Left column
            pdf.cell(95, 7, f"Total Trades: {len(df)}", 0, 0)
            # Right column
            pdf.cell(95, 7, f"Winning Trades: {len(df[df.get('net_pnl', pd.Series([0])) > 0]) if 'net_pnl' in df.columns else 'N/A'}", 0, 1)
            
            pdf.cell(95, 7, f"Gross P&L: Rs. {total_gross_pnl:,.2f}", 0, 0)
            pdf.cell(95, 7, f"Losing Trades: {len(df[df.get('net_pnl', pd.Series([0])) < 0]) if 'net_pnl' in df.columns else 'N/A'}", 0, 1)
            
            pdf.cell(95, 7, f"Total Fees: Rs. {total_fees:,.2f}", 0, 1)
            
            # Net P&L (highlighted)
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(40, 10, "Net P&L: ")
            if total_net_pnl >= 0:
                pdf.set_text_color(0, 150, 0)
            else:
                pdf.set_text_color(200, 50, 50)
            pdf.cell(0, 10, f"Rs. {total_net_pnl:,.2f}", 0, 1)
            pdf.set_text_color(0, 0, 0)
            
            pdf.ln(10)
            
            # --- Section 2: Exit Reasons ---
            if exit_reasons:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, "Exit Breakdown", 0, 1)
                pdf.set_font("Arial", '', 10)
                for reason, count in exit_reasons.items():
                    reason_display = reason if reason else "Still Open"
                    pdf.cell(0, 6, f"  - {reason_display}: {count} trades", 0, 1)
                pdf.ln(5)

            # --- Section 3: Trades Table ---
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "Trade Details", 0, 1)
            
            # Table Headers
            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(50, 50, 50)
            pdf.set_text_color(255, 255, 255)
            
            col_widths = [50, 15, 15, 25, 25, 30, 30]
            headers = ["Symbol", "Side", "Qty", "Entry", "Exit", "Gross P&L", "Net P&L"]
            
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
            pdf.ln()
            
            # Table Rows
            pdf.set_font("Arial", '', 8)
            pdf.set_text_color(0, 0, 0)
            
            for idx, row in df.iterrows():
                # Check if we need a new page
                if pdf.get_y() > 260:
                    pdf.add_page()
                    # Repeat headers
                    pdf.set_font("Arial", 'B', 9)
                    pdf.set_fill_color(50, 50, 50)
                    pdf.set_text_color(255, 255, 255)
                    for i, header in enumerate(headers):
                        pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
                    pdf.ln()
                    pdf.set_font("Arial", '', 8)
                    pdf.set_text_color(0, 0, 0)
                
                # Truncate symbol if needed
                symbol = str(row.get('symbol', ''))
                if len(symbol) > 22:
                    symbol = symbol[:20] + '..'
                
                pdf.cell(col_widths[0], 7, symbol, 1, 0, 'L')
                pdf.cell(col_widths[1], 7, str(row.get('action', '')), 1, 0, 'C')
                pdf.cell(col_widths[2], 7, str(row.get('quantity', '')), 1, 0, 'C')
                
                entry = row.get('entry_price', 0)
                pdf.cell(col_widths[3], 7, f"{entry:.2f}" if entry else "-", 1, 0, 'R')
                
                exit_p = row.get('exit_price', 0)
                pdf.cell(col_widths[4], 7, f"{exit_p:.2f}" if exit_p else "-", 1, 0, 'R')
                
                gross = row.get('gross_pnl', 0)
                pdf.cell(col_widths[5], 7, f"{gross:.2f}" if gross else "0.00", 1, 0, 'R')
                
                net = row.get('net_pnl', 0)
                pdf.cell(col_widths[6], 7, f"{net:.2f}" if net else "0.00", 1, 0, 'R')
                pdf.ln()
            
            # --- Section 4: Fee Breakdown ---
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, "Fee Breakdown", 0, 1)
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 6, f"Entry Fees: Rs. {total_entry_fees:,.2f}", 0, 1)
            pdf.cell(0, 6, f"Exit Fees: Rs. {total_exit_fees:,.2f}", 0, 1)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 6, f"Total Fees: Rs. {total_fees:,.2f}", 0, 1)

            pdf.output(filepath)
            return filepath, "Success"

        except Exception as e:
            self.logger.error(f"PDF export error: {e}")
            import traceback
            traceback.print_exc()
            return None, str(e)
