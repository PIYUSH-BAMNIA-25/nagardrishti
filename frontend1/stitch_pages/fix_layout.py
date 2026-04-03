import os
import re
from pathlib import Path

dir_path = Path(__file__).resolve().parent

for filename in os.listdir(dir_path):
    if not filename.endswith('.html'):
        continue
        
    path = dir_path / filename
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
        
    original = html
    
    # 1. Width 100% (Replace max-w-* bounds with full width)
    # The user wants it to look like a laptop screen edge-to-edge
    html = re.sub(r'\bmax-w-[a-zA-Z0-9-]+\b', 'w-full px-4 md:px-8', html)
    html = html.replace('mx-auto', '') 
    
    # 2. Add JavaScript routing by replacing the hardcoded href="#" links
    html = html.replace('href="#">AI Detection</a>', 'href="/ai-detection">AI Detection</a>')
    html = html.replace('href="#">Manual Report</a>', 'href="/manual-report">Manual Report</a>')
    html = html.replace('href="#">Complaint Map</a>', 'href="/complaint-map">Complaint Map</a>')
    html = html.replace('href="#">History</a>', 'href="/history">History</a>')
    
    # Ensure brand logo is clickable
    html = re.sub(r'<div class="([^"]*?text-[^"]*?)">\s*NagarDrishti\s*</div>', 
                  r'<a href="/" class="\1" style="text-decoration:none">NagarDrishti</a>', html)

    if html != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ Updated: {filename}")

print("✨ All HTML files configured for 100% layout width and internal routing!")
