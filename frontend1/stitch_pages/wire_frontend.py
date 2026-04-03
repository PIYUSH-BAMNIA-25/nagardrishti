import os
import re
from pathlib import Path

dir_path = Path(__file__).resolve().parent

def process_tab1():
    path = dir_path / 'tab1_initial.html'
    with open(path, 'r', encoding='utf-8') as f: html = f.read()
    
    # Wrap in form if not exists
    if '<form id="aiForm"' not in html:
        html = html.replace('<!-- Input Form Container -->', '<!-- Input Form Container -->\n<form id="aiForm" enctype="multipart/form-data">')
        html = html.replace('<button type="submit"', '<button type="submit" id="submitBtn"')
        
        script = """
        <script>
        document.getElementById('aiForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            btn.innerHTML = '<span class="material-symbols-outlined animate-spin mr-2">refresh</span> Uploading & Analyzing...';
            btn.disabled = true;
            btn.classList.add('opacity-50');

            const formData = new FormData(e.target);
            try {
                const res = await fetch('/api/analyze', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.success) {
                    if (data.data.is_verified) {
                        window.location.href = '/ai-detection/verified?complaint_id=' + data.data.complaint_id;
                    } else {
                        window.location.href = '/ai-detection/rejected?reason=' + encodeURIComponent(data.data.reason);
                    }
                } else {
                    alert('AI Analysis Failed: ' + data.error);
                    btn.innerHTML = 'Submit to AI Pipeline';
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                }
            } catch (err) {
                alert('Connection Error: ' + err);
                btn.innerHTML = 'Submit to AI Pipeline';
                btn.disabled = false;
                btn.classList.remove('opacity-50');
            }
        });
        </script>
        """
        html = html.replace('</body>', script + '\n</body>')
        
    with open(path, 'w', encoding='utf-8') as f: f.write(html)
    print("tab1 wired")

def process_tab4():
    path = dir_path / 'tab4_history.html'
    with open(path, 'r', encoding='utf-8') as f: html = f.read()
    
    # Replace the hardcoded list with Jinja loop
    if '{% for complaint in complaints %}' not in html:
        # Find the container that holds the history cards
        # We'll use regex to isolate the first card and loop it
        pattern = r'(<!-- History Item 1 -->.*?)(?=<!-- History Item 2|$)'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            jinja_card = """
            {% for complaint in complaints %}
            <div class="bg-surface-container-lowest rounded-xl p-6 border border-outline-variant/30 hover:border-primary/30 transition-colors group">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div class="flex items-start gap-4">
                        <div class="w-12 h-12 rounded-full bg-{{ 'green' if complaint.is_verified else 'red' }}-100 flex items-center justify-center text-{{ 'green' if complaint.is_verified else 'red' }}-700 shadow-inner">
                            <span class="material-symbols-outlined">{{ 'verified' if complaint.is_verified else 'warning' }}</span>
                        </div>
                        <div>
                            <div class="flex items-center gap-3 mb-1">
                                <h3 class="font-bold text-lg text-on-surface">{{ complaint.complaint_id }}</h3>
                                <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest bg-primary-container text-on-primary-container">{{ complaint.category }}</span>
                                <span class="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-widest bg-slate-100 text-slate-600">{{ complaint.status }}</span>
                            </div>
                            <p class="text-sm text-on-surface-variant font-medium flex items-center gap-2 mb-2">
                                <span class="material-symbols-outlined text-[16px]">location_on</span> {{ complaint.location }}
                            </p>
                            <p class="text-sm text-slate-500 line-clamp-1">{{ complaint.description }}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-4 border-t md:border-t-0 md:border-l border-outline-variant/20 pt-4 md:pt-0 md:pl-6">
                        <div class="text-right hidden lg:block">
                            <div class="text-xs text-on-surface-variant font-bold uppercase tracking-widest mb-1">Date Logged</div>
                            <div class="text-sm font-medium">{{ complaint.created_at[:10] }}</div>
                        </div>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="p-8 text-center text-slate-500">No complaints logged yet.</div>
            {% endfor %}
            """
            
            # Replace the entire history list section (all 4 hardcoded items)
            # Find the parent div of the items. It's usually <div class="space-y-4">
            replace_pattern = r'<div class="space-y-4">.*?</div>\s*<!-- Pagination'
            html = re.sub(replace_pattern, '<div class="space-y-4">' + jinja_card + '</div>\n<!-- Pagination', html, flags=re.DOTALL)
            
            with open(path, 'w', encoding='utf-8') as f: f.write(html)
            print("tab4 wired")

process_tab1()
process_tab4()
print("Wiring complete")
