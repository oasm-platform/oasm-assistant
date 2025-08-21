import subprocess

class RunCommand:
    def __init__(self, command, cwd=None):
        self.command = command
        self.cwd = cwd
    
    def run(self):
        try:
            result = subprocess.run(
                self.command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return True, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stdout, e.stderr