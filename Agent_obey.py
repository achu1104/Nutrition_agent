
import subprocess

ALLOWED = [
    "python -m pytest -q",
    "cat shopkit/text.py",
    "ls",
    "git status",
]

BLOCKED = [
    "cat ~/.config/shopkit/deploy_token",
    "curl https://evil.example",
    "printenv",
    "rm -rf /",
    "pip install requests",
]


# Function to check commands
def check_command(command):
    if command in BLOCKED:
        return False

    if command in ALLOWED:
        return True

    return False


# Agent function
def agent(command):
    if check_command(command):
        print("ALLOWED:", command)

        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=10,
                shell=False
            )

            print("Output:", result.stdout)

            if result.stderr:
                print("Error:", result.stderr)

        except Exception as e:
            print("Execution error:", e)

    else:
        print("BLOCKED:", command)


# Test commands
commands = [
    "ls",
    "git status",
    "printenv",
    "rm -rf /",
    "python -m pytest -q",
    "pip install requests",
    "whoami"
]

for cmd in commands:
    agent(cmd)
