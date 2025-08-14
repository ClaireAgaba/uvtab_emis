#!/usr/bin/env python3
"""
Convert PROJECT_DOCUMENTATION.md to PDF
"""

import markdown
import pdfkit
from pathlib import Path
import sys
import os

def convert_md_to_pdf():
    """Convert markdown file to PDF with professional styling"""
    
    # Read the markdown file
    md_file = Path("PROJECT_DOCUMENTATION.md")
    if not md_file.exists():
        print("Error: PROJECT_DOCUMENTATION.md not found")
        return False
    
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML
    html = markdown.markdown(md_content, extensions=['tables', 'toc'])
    
    # Add professional CSS styling
    css_style = """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            color: #333;
        }
        h1 {
            color: #1e40af;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 0.5rem;
            font-size: 2.5rem;
        }
        h2 {
            color: #2563eb;
            border-bottom: 2px solid #60a5fa;
            padding-bottom: 0.3rem;
            margin-top: 2rem;
            font-size: 1.8rem;
        }
        h3 {
            color: #1d4ed8;
            font-size: 1.3rem;
            margin-top: 1.5rem;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1rem 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th, td {
            border: 1px solid #e5e7eb;
            padding: 12px;
            text-align: left;
        }
        th {
            background-color: #f3f4f6;
            font-weight: 600;
            color: #374151;
        }
        tr:nth-child(even) {
            background-color: #f9fafb;
        }
        code {
            background-color: #f1f5f9;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Monaco', 'Consolas', monospace;
        }
        pre {
            background-color: #1e293b;
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
        }
        blockquote {
            border-left: 4px solid #3b82f6;
            margin: 1rem 0;
            padding-left: 1rem;
            color: #6b7280;
        }
        .emoji {
            font-size: 1.2em;
        }
        hr {
            border: none;
            height: 2px;
            background: linear-gradient(to right, #3b82f6, #60a5fa, #93c5fd);
            margin: 2rem 0;
        }
        ul, ol {
            margin: 1rem 0;
            padding-left: 2rem;
        }
        li {
            margin: 0.5rem 0;
        }
        .page-break {
            page-break-before: always;
        }
    </style>
    """
    
    # Create complete HTML document
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>UVTAB EMIS - Project Documentation</title>
        {css_style}
    </head>
    <body>
        {html}
    </body>
    </html>
    """
    
    # Save HTML file
    html_file = Path("PROJECT_DOCUMENTATION.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML file created: {html_file}")
    
    # Try to convert to PDF using wkhtmltopdf
    try:
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None
        }
        
        pdfkit.from_file(str(html_file), 'PROJECT_DOCUMENTATION.pdf', options=options)
        print("✅ PDF file created: PROJECT_DOCUMENTATION.pdf")
        return True
        
    except Exception as e:
        print(f"❌ PDF conversion failed: {e}")
        print("📄 HTML file is available as an alternative")
        return False

if __name__ == "__main__":
    success = convert_md_to_pdf()
    if success:
        print("\n🎉 Successfully converted PROJECT_DOCUMENTATION.md to PDF!")
    else:
        print("\n📝 Markdown file preserved, HTML file created as alternative")
