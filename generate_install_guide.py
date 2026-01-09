"""
Generate Windows Installation Guide PDF
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
import os

def create_installation_guide():
    """Generate the Windows Installation Guide PDF."""
    
    output_path = os.path.join(os.path.dirname(__file__), "Windows_Installation_Guide.pdf")
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    # Colors
    primary_color = HexColor("#1a5276")
    accent_color = HexColor("#2980b9")
    light_bg = HexColor("#eaf2f8")
    success_color = HexColor("#27ae60")
    warning_color = HexColor("#e67e22")
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=primary_color,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    heading1_style = ParagraphStyle(
        'Heading1Custom',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=primary_color,
        spaceBefore=20,
        spaceAfter=10,
        borderWidth=1,
        borderColor=accent_color,
        borderPadding=5,
        backColor=light_bg
    )
    
    heading2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=accent_color,
        spaceBefore=15,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        leading=14
    )
    
    code_style = ParagraphStyle(
        'CodeCustom',
        parent=styles['Code'],
        fontSize=9,
        backColor=HexColor("#f4f4f4"),
        borderWidth=1,
        borderColor=HexColor("#cccccc"),
        borderPadding=8,
        spaceAfter=10,
        fontName='Courier'
    )
    
    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=4
    )
    
    # Build content
    content = []
    
    # Title
    content.append(Paragraph("Windows Installation Guide", title_style))
    content.append(Paragraph("Smart Options Screener & Paper Trade App", 
                            ParagraphStyle('Subtitle', parent=styles['Normal'], 
                                          fontSize=14, textColor=accent_color, 
                                          alignment=TA_CENTER, spaceAfter=30)))
    
    # Prerequisites
    content.append(Paragraph("Prerequisites (One-time Setup)", heading1_style))
    content.append(Paragraph("Install these on your build machine:", body_style))
    
    prereq_data = [
        ['Software', 'Download URL', 'Notes'],
        ['Python 3.10+', 'python.org/downloads', '✓ Check "Add Python to PATH"'],
        ['Git', 'git-scm.com/download/win', 'For cloning repository'],
        ['Inno Setup', 'jrsoftware.org/isdl.php', 'For creating installers'],
        ['PostgreSQL (Optional)', 'postgresql.org/download/windows', 'Only for Paper Trade App persistence'],
    ]
    
    prereq_table = Table(prereq_data, colWidths=[3*cm, 6*cm, 6*cm])
    prereq_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), light_bg),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    content.append(prereq_table)
    content.append(Spacer(1, 20))
    
    # Building the Installers
    content.append(Paragraph("Building the Installers", heading1_style))
    
    content.append(Paragraph("Step 1: Clone the Repository", heading2_style))
    content.append(Paragraph(
        '<font face="Courier" size="9">git clone https://github.com/manish-ongithub/option_testing_qwen.git<br/>'
        'cd option_testing_qwen</font>', code_style))
    
    content.append(Paragraph("Step 2: Build Both Applications", heading2_style))
    content.append(Paragraph("<b>Option A: One-Click Build (Recommended)</b>", body_style))
    content.append(Paragraph('<font face="Courier" size="9">.\\build_all.bat</font>', code_style))
    
    content.append(Paragraph("<b>Option B: Build Individually</b>", body_style))
    content.append(Paragraph(
        '<font face="Courier" size="9"># For Options Screener only<br/>'
        '.\\build_installer.bat<br/><br/>'
        '# For Paper Trade App only<br/>'
        '.\\build_paper_trade.bat</font>', code_style))
    
    content.append(Paragraph("Step 3: Create Installers with Inno Setup", heading2_style))
    content.append(Paragraph("• Open <b>Inno Setup Compiler</b>", bullet_style))
    content.append(Paragraph("• File → Open → Select the .iss file", bullet_style))
    content.append(Paragraph("• Build → Compile (or press Ctrl+F9)", bullet_style))
    content.append(Spacer(1, 10))
    
    installer_data = [
        ['Application', 'Inno Setup File', 'Output Installer'],
        ['Options Screener', 'installer\\OptionsScreener_Setup.iss', 'OptionsScreener_Setup_v3.3.exe'],
        ['Paper Trade App', 'installer\\PaperTradeApp_Setup.iss', 'PaperTradeApp_Setup_v1.0.exe'],
    ]
    
    installer_table = Table(installer_data, colWidths=[4*cm, 6*cm, 5.5*cm])
    installer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    content.append(installer_table)
    
    # Page break
    content.append(PageBreak())
    
    # Installing Options Screener
    content.append(Paragraph("Installing Smart Options Screener", heading1_style))
    
    screener_steps = [
        ['Step', 'Action'],
        ['1', 'Double-click OptionsScreener_Setup_v3.3.exe'],
        ['2', 'Click Next on Welcome screen'],
        ['3', 'Choose installation folder (default is fine)'],
        ['4', 'Optionally check "Create a desktop shortcut"'],
        ['5', 'Click Install'],
        ['6', 'Click Finish (optionally launch the app)'],
    ]
    
    screener_table = Table(screener_steps, colWidths=[1.5*cm, 14*cm])
    screener_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), success_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor("#e8f8f0")),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
    ]))
    content.append(screener_table)
    content.append(Spacer(1, 10))
    content.append(Paragraph("<b>Post-Installation:</b> None required - works out of the box! ✓", 
                            ParagraphStyle('Success', parent=body_style, textColor=success_color)))
    content.append(Spacer(1, 20))
    
    # Installing Paper Trade App
    content.append(Paragraph("Installing Paper Trade App", heading1_style))
    
    paper_steps = [
        ['Step', 'Action'],
        ['1', 'Double-click PaperTradeApp_Setup_v1.0.exe'],
        ['2', 'Click Next on Welcome screen'],
        ['3', 'Choose installation folder (default is fine)'],
        ['4', 'Optionally check "Create a desktop shortcut"'],
        ['5', 'Click Install'],
        ['6', 'Click Finish (optionally launch the app)'],
    ]
    
    paper_table = Table(paper_steps, colWidths=[1.5*cm, 14*cm])
    paper_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), light_bg),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
    ]))
    content.append(paper_table)
    content.append(Spacer(1, 15))
    
    content.append(Paragraph("<b>Post-Installation Setup:</b>", 
                            ParagraphStyle('Warning', parent=body_style, textColor=warning_color)))
    content.append(Spacer(1, 5))
    
    content.append(Paragraph("1. Navigate to installation folder:", bullet_style))
    content.append(Paragraph(
        '<font face="Courier" size="8">C:\\Users\\&lt;YourUsername&gt;\\AppData\\Local\\Programs\\Paper Trade App\\</font>', 
        code_style))
    
    content.append(Paragraph("2. Copy config_example.py to config.py:", bullet_style))
    content.append(Paragraph('<font face="Courier" size="8">copy config_example.py config.py</font>', code_style))
    
    content.append(Paragraph("3. Edit config.py with your API credentials (if using live data)", bullet_style))
    content.append(Paragraph("4. Place alert JSON files in the alerts_inbox folder", bullet_style))
    
    content.append(Spacer(1, 15))
    content.append(Paragraph("<b>PostgreSQL Database (OPTIONAL):</b>", 
                            ParagraphStyle('Info', parent=body_style, textColor=accent_color)))
    content.append(Paragraph(
        "The app works without PostgreSQL (uses in-memory storage). "
        "To enable persistent storage across sessions:", bullet_style))
    content.append(Paragraph("• Install PostgreSQL: https://www.postgresql.org/download/windows/", bullet_style))
    content.append(Paragraph("• Create database: <font face='Courier' size='8'>CREATE DATABASE paper_trade;</font>", bullet_style))
    content.append(Paragraph("• In config.py, set: <font face='Courier' size='8'>ENABLE_PERSISTENCE = True</font>", bullet_style))
    content.append(Paragraph("• Update DB_CONFIG with your PostgreSQL credentials", bullet_style))
    
    content.append(Spacer(1, 20))
    
    # Launching Applications
    content.append(Paragraph("Launching Applications", heading1_style))
    
    launch_data = [
        ['Method', 'Options Screener', 'Paper Trade App'],
        ['Start Menu', 'Start → Smart Options Screener', 'Start → Paper Trade App'],
        ['Desktop', 'Double-click desktop icon', 'Double-click desktop icon'],
    ]
    
    launch_table = Table(launch_data, colWidths=[3*cm, 6*cm, 6*cm])
    launch_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
    ]))
    content.append(launch_table)
    
    content.append(Spacer(1, 20))
    
    # Uninstalling
    content.append(Paragraph("Uninstalling", heading1_style))
    content.append(Paragraph("<b>Method 1: Windows Settings</b>", body_style))
    content.append(Paragraph("• Settings → Apps → Installed Apps", bullet_style))
    content.append(Paragraph("• Find the application → Click ⋮ → Uninstall", bullet_style))
    content.append(Spacer(1, 8))
    content.append(Paragraph("<b>Method 2: Start Menu</b>", body_style))
    content.append(Paragraph("• Start → [App Name] → Uninstall", bullet_style))
    
    content.append(Spacer(1, 20))
    
    # Troubleshooting
    content.append(Paragraph("Troubleshooting", heading1_style))
    
    trouble_data = [
        ['Issue', 'Solution'],
        ['VCRUNTIME140.dll not found', 'Install Visual C++ Redistributable from:\nhttps://aka.ms/vs/17/release/vc_redist.x64.exe'],
        ['Qt platform plugin error', 'Reinstall the application'],
        ['App crashes on startup', 'Right-click → Run as administrator (first time)'],
        ['Windows protected your PC', 'Click "More info" → "Run anyway"'],
    ]
    
    trouble_table = Table(trouble_data, colWidths=[5*cm, 10.5*cm])
    trouble_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), warning_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor("#fef5e7")),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    content.append(trouble_table)
    
    content.append(Spacer(1, 20))
    
    # Quick Reference
    content.append(Paragraph("Quick Reference", heading1_style))
    
    ref_data = [
        ['Application', 'Installer File', 'Default Install Location'],
        ['Options Screener', 'OptionsScreener_Setup_v3.3.exe', '%LocalAppData%\\Programs\\Smart Options Screener'],
        ['Paper Trade App', 'PaperTradeApp_Setup_v1.0.exe', '%LocalAppData%\\Programs\\Paper Trade App'],
    ]
    
    ref_table = Table(ref_data, colWidths=[4*cm, 5.5*cm, 6*cm])
    ref_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, -1), light_bg),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
    ]))
    content.append(ref_table)
    
    # Build PDF
    doc.build(content)
    print(f"✓ PDF created successfully: {output_path}")
    return output_path

if __name__ == "__main__":
    create_installation_guide()

