import glob
import re

for f in glob.glob('src/agents/nodes/*.py'):
    with open(f, 'r', encoding='utf8') as file:
        content = file.read()
    
    # Remove current_agent and current_tool keys
    content = re.sub(r'[\t ]*"current_agent":\s*"[^"]*",?\n', '', content)
    content = re.sub(r'[\t ]*"current_tool":\s*"[^"]*",?\n', '', content)
    
    with open(f, 'w', encoding='utf8') as file:
        file.write(content)
print("Done cleaning nodes.")
