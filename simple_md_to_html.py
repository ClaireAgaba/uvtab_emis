#!/usr/bin/env python3
"""
Simple Markdown to HTML converter for PROJECT_DOCUMENTATION.md
"""

import re
from pathlib import Path

def convert_md_to_html():
    """Convert markdown to HTML with basic formatting"""
    
    # Read the markdown file
    md_file = Path("PROJECT_DOCUMENTATION.md")
    if not md_file.exists():
        print("Error: PROJECT_DOCUMENTATION.md not found")
        return False
    
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Basic markdown to HTML conversion
    html = content
    
    # Convert headers
    html = re.sub(r'^# (.*$)', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*$)', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.*$)', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.*$)', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    
    # Convert bold text
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    
    # Convert italic text
    html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
    
    # Convert code blocks
    html = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    
    # Convert inline code
    html = re.sub(r'`(.*?)`', r'<code>\1</code>', html)
    
    # Convert links
    html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html)
    
    # Convert horizontal rules
    html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
    
    # Convert line breaks
    html = html.replace('\n\n', '</p><p>')
    html = html.replace('\n', '<br>')
    
    # Handle lists (basic)
    html = re.sub(r'^- (.*$)', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)
    
    # Convert tables (basic)
    lines = html.split('<br>')
    in_table = False
    table_html = []
    
    for line in lines:
        if '|' in line and line.strip():
            if not in_table:
                table_html.append('<table border="1" style="border-collapse: collapse; width: 100%;">')
                in_table = True
            
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells and not all(cell.startswith('-') for cell in cells):
                row_html = '<tr>'
                for cell in cells:
                    if cell.startswith('**') and cell.endswith('**'):
                        row_html += f'<th style="background-color: #f2f2f2; padding: 8px;">{cell[2:-2]}</th>'
                    else:
                        row_html += f'<td style="padding: 8px;">{cell}</td>'
                row_html += '</tr>'
                table_html.append(row_html)
        else:
            if in_table:
                table_html.append('</table>')
                in_table = False
            if line.strip():
                table_html.append(line)
    
    if in_table:
        table_html.append('</table>')
    
    html = '<br>'.join(table_html)
    
    # Professional CSS styling
    css_style = """
    <style>
        @page {
            margin: 1in;
            size: A4;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: none;
            margin: 0;
            padding: 20px;
        }
        h1 {
            color: #1e40af;
            border-bottom: 3px solid #3b82f6;
            padding-bottom: 0.5rem;
            font-size: 2.2rem;
            page-break-after: avoid;
        }
        h2 {
            color: #2563eb;
            border-bottom: 2px solid #60a5fa;
            padding-bottom: 0.3rem;
            margin-top: 2rem;
            font-size: 1.6rem;
            page-break-after: avoid;
        }
        h3 {
            color: #1d4ed8;
            font-size: 1.2rem;
            margin-top: 1.5rem;
            page-break-after: avoid;
        }
        h4 {
            color: #1e3a8a;
            font-size: 1.1rem;
            margin-top: 1rem;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1rem 0;
            page-break-inside: avoid;
        }
        th, td {
            border: 1px solid #e5e7eb;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f3f4f6 !important;
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
            font-size: 0.9em;
        }
        pre {
            background-color: #1e293b;
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            page-break-inside: avoid;
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
            margin: 0.3rem 0;
        }
        p {
            margin: 1rem 0;
        }
        strong {
            font-weight: 600;
            color: #1f2937;
        }
        a {
            color: #2563eb;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .no-break {
            page-break-inside: avoid;
        }
        @media print {
            body {
                font-size: 12pt;
            }
            h1 { font-size: 18pt; }
            h2 { font-size: 16pt; }
            h3 { font-size: 14pt; }
        }
    </style>
    """
    
    # Create complete HTML document
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>UVTAB EMIS - Project Documentation</title>
    {css_style}
</head>
<body>
    <p>{html}</p>
</body>
</html>"""
    
    # Save HTML file
    html_file = Path("PROJECT_DOCUMENTATION.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML file created: {html_file}")
    print("📄 You can open this file in a browser and use 'Print to PDF' to create a PDF")
    print("🖨️  For best results: Use Chrome/Edge, set margins to 'Minimum', enable 'Background graphics'")
    
    return True

if __name__ == "__main__":
    convert_md_to_html()
    print("\n🎉 Conversion complete! Original markdown file preserved.")
