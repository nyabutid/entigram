import os
import shlex
import subprocess
import platform
import tempfile
import stat
from pathlib import Path


def _escape_applescript(s: str) -> str:
    """Escapes a string for safe embedding inside an AppleScript double-quoted string."""
    return s.replace('\\', '\\\\').replace('"', '\\"')


def _sanitize_initial_prompt(prompt: str) -> str:
    """Remove bracketed-paste markers that can leak from terminal launch paths."""
    return (
        prompt
        .replace("\x1b[200~", "")
        .replace("\x1b[201~", "")
        .replace("^[[200~", "")
        .replace("^[[201~", "")
    )


def _build_codex_command(initial_prompt: str = "", flags=None, model: str = None) -> str:
    parts = ["codex"]
    if model:
        parts.extend(["--model", shlex.quote(model)])
    if flags:
        parts.extend(flags)
    if initial_prompt:
        parts.append(shlex.quote(_sanitize_initial_prompt(initial_prompt)))
    return " ".join(parts)


def execute_headless_agy(prompt: str, target_dir: str = "."):
    print("[ENTIGRAM] Igniting headless Antigravity engine...")
    target_path = Path(target_dir).absolute()
    try:
        # We pass the prompt via 'input', NOT as a command-line argument.
        # This breaks the TTY and forces a one-shot execution.
        result = subprocess.run(
            ["agy", "run", "--dangerously-skip-permissions"],
            input=prompt,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(target_path)
        )
        output = result.stdout.strip()
        
        # Defensive: If the engine echoes the prompt, strip it
        if output.startswith(prompt):
            output = output[len(prompt):].strip()
            
        return output
    except subprocess.CalledProcessError as e:
        print(f"[ENTIGRAM FATAL] Engine failure: {e.stderr}")
        import sys
        sys.exit(1)


def launch_agent(target_dir: str, engine: str, yolo: bool = False, initial_prompt: str = "", headless: bool = False, model: str = None):
    """
    Attempts to launch the selected CLI agent in the target directory.
    On macOS, it opens a new Terminal window and brings it to the front.
    """
    target_path = Path(target_dir).absolute()
    initial_prompt = _sanitize_initial_prompt(initial_prompt)

    # Construct base command
    if engine == "Antigravity":
        engine_cmd = "agy run"
        if model:
            # assuming agy supports --model
            engine_cmd += f" --model {model}"
    elif engine == "Claude Code":
        engine_cmd = "claude"
        if model:
            # claude code usually doesn't take --model directly in the command but maybe?
            pass 
    elif engine == "Ollama":
        # Entigram targets the Claude Code integration via Ollama
        app = "claude"
        if model:
            engine_cmd = f"ollama launch {app} --model {model}"
        else:
            # Default to qwen3 as requested by user to allow silent boot
            engine_cmd = f"ollama launch {app} --model qwen3"
    elif engine == "Codex":
        engine_cmd = _build_codex_command(model=model)
    else:
        engine_cmd = "agy run"

    flags = []
    if yolo:
        if engine == "Antigravity":
            flags.append("--dangerously-skip-permissions")
        elif engine == "Claude Code":
            flags.append("--dangerously-skip-permissions")
        elif engine == "Codex":
            flags.extend(["--ask-for-approval", "never"])

    if headless and (engine == "Antigravity" or engine == "agy"):
        output = execute_headless_agy(initial_prompt, target_dir=str(target_path))
        print(output)
        return True, "Headless execution completed successfully."

    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            if engine == "Codex":
                cmd = f"cd {shlex.quote(str(target_path))} && {_build_codex_command(initial_prompt=initial_prompt, flags=flags, model=model)}"
                escaped_cmd = _escape_applescript(cmd)
                applescript = f'''
                    tell application "Terminal"
                        activate
                        do script "{escaped_cmd}"
                    end tell
                '''
                subprocess.run(["osascript", "-e", applescript])
                return True, "Launched Codex with native initial prompt."

            if initial_prompt:
                # Use UNIX expect to bypass AppleScript Accessibility prompts
                # This spawns the agent in a true PTY, injects the prompt silently, and hands over control.
                engine_cmd_str = f"{engine_cmd} {' '.join(flags)}"
                
                # Escape for Tcl/Expect double-quotes
                escaped_prompt = initial_prompt.replace('\\', '\\\\').replace('$', '\\$').replace('[', '\\[').replace('"', '\\"')
                
                # Determine what to expect before sending the prompt
                # Antigravity uses '?', Claude/Ollama uses '❯' or '>'
                expect_pattern = "? for shortcuts" if "agy" in engine_cmd or "Antigravity" in engine else "> "
                
                expect_script_content = f"""#!/usr/bin/expect -f
set timeout -1
cd "{str(target_path)}"

# Log user 1 means we see the startup sequence.
log_user 1
spawn {engine_cmd_str}

# PHASE 1: Let the TUI settle
sleep 3.0

# PHASE 2: Wait for the interactive prompt character.
# Use regex to match common prompt characters: >, >>>, ❯, ›, ?
expect {{
    -re {{[>❯›?]}} {{ sleep 1.0 }}
    timeout {{ }}
}}

# PHASE 3: Send the initial priority task SILENTLY
log_user 0
send -- "{escaped_prompt}\\r\\n"
# Wait for the agent to process the return key
sleep 1.5
log_user 1

# Hand control over to the user
interact
"""
                fd, script_path = tempfile.mkstemp(prefix="entigram_agent_", suffix=".exp", text=True)
                with os.fdopen(fd, "w") as f:
                    f.write(expect_script_content)
                
                os.chmod(script_path, stat.S_IRWXU)
                subprocess.run(["open", "-a", "Terminal", script_path], check=True)
                return True, f"Launched {engine} via silent expect PTY."
            else:
                # Standard AppleScript launch for empty prompts
                cmd = f"cd {shlex.quote(str(target_path))} && {engine_cmd} {' '.join(flags)}"
                escaped_cmd = _escape_applescript(cmd)
                applescript = f'''
                    tell application "Terminal"
                        activate
                        do script "{escaped_cmd}"
                    end tell
                '''
                subprocess.run(["osascript", "-e", applescript])
                return True, "Launched and focused Terminal."
        else:
            prompt_arg = f" {shlex.quote(initial_prompt)}" if initial_prompt else ""
            cmd = f"cd {shlex.quote(str(target_path))} && {engine_cmd} {' '.join(flags)}{prompt_arg}"
            return False, f"Auto-launch not supported on {system}. Please run '{cmd}' manually."
    except Exception as e:
        return False, str(e)
