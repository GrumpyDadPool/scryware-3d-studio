"""
Scryware 3D Studio - WSL bridge.

Runs on Windows. Executes commands inside WSL via wsl.exe and streams output.
Also handles Windows <-> WSL path translation.
"""
import os
import re
import shutil
import subprocess
import threading


def _session_log_path():
    """Same session log file main.py writes to (lives next to main.py)."""
    # backend/wsl_bridge.py -> parent dir is the app root
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "scryware-3d-studio.log")


def find_wsl_exe():
    """Locate wsl.exe."""
    for candidate in ("wsl.exe", r"C:\Windows\System32\wsl.exe"):
        if shutil.which(candidate):
            return shutil.which(candidate)
    return None


def detect_distro(wsl_exe):
    """Pick a distro: prefer Ubuntu-22.04, then Ubuntu, then first available."""
    try:
        proc = subprocess.run(
            [wsl_exe, "-l", "-q"],
            capture_output=True, timeout=15,
        )
        # wsl.exe outputs UTF-16LE; decode it properly, then kill any stray nulls
        try:
            out = proc.stdout.decode("utf-16")
        except Exception:
            out = proc.stdout.decode("utf-8", errors="replace")
        out = out.replace("\x00", "")
        names = [n.strip() for n in re.split(r"[\r\n]+", out)]
        # strip "(Default)" markers
        names = [re.sub(r"\s*\(Default\)\s*", "", n).strip() for n in names]
        names = [n for n in names if n]
        for prefer in ("Ubuntu-22.04", "Ubuntu"):
            if prefer in names:
                return prefer
        return names[0] if names else None
    except Exception:
        return None


def win_to_wsl(win_path):
    """C:\\Users\\kevin\\img.png -> /mnt/c/Users/kevin/img.png"""
    p = os.path.abspath(win_path)
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if not m:
        raise ValueError(f"Cannot translate to WSL path: {win_path}")
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def wsl_to_win(wsl_path):
    """ /mnt/c/Users/kevin/img.png -> C:\\Users\\kevin\\img.png """
    m = re.match(r"^/mnt/([a-z])/(.*)$", wsl_path)
    if not m:
        return wsl_path
    return f"{m.group(1).upper()}:\\" + m.group(2).replace("/", "\\")


class WslRunner:
    """Runs bash commands inside WSL, streaming combined stdout/stderr."""

    def __init__(self, distro=None):
        self.wsl_exe = find_wsl_exe()
        if not self.wsl_exe:
            raise RuntimeError("wsl.exe not found. Is WSL2 installed?")
        self.distro = distro or detect_distro(self.wsl_exe)
        if not self.distro:
            raise RuntimeError("No WSL distro found.")
        self.home = self._detect_home()

    def _detect_home(self):
        # Try simple non-interactive shells; login/interactive flags (-li)
        # let .bashrc/conda-init output pollute the result, so avoid them.
        cmds = [
            [self.wsl_exe, "-d", self.distro, "-e", "bash", "-c", "echo $HOME"],
            [self.wsl_exe, "-d", self.distro, "-e", "sh", "-c", "echo $HOME"],
        ]
        for cmd in cmds:
            try:
                out = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", timeout=15,
                    errors="replace",
                ).stdout.replace("\x00", "")
                # take the last non-empty line in case of stray output
                lines = [ln.strip() for ln in out.split("\n") if ln.strip()]
                home = lines[-1] if lines else ""
                if home.startswith("/") and " " not in home:
                    return home
            except Exception:
                continue
        return "/home/user"  # fallback; expand_wsl still works structurally

    def expand_wsl(self, path):
        """Expand a leading ~/ using the detected WSL home dir."""
        if path == "~":
            return self.home
        if path.startswith("~/"):
            return self.home + path[1:]
        return path

    def run(self, bash_cmd, on_line=None, on_done=None, workdir="~"):
        """
        Run bash_cmd in WSL (login shell, so conda is available).
        on_line(str) called per output line. on_done(returncode) at end.
        Returns the Popen object (caller may .terminate() it).
        Runs the wait loop in a background thread so the GUI stays responsive.
        """
        # Use bash -lic so ~/.bashrc (conda init) is loaded.
        # Escape for the outer shell: pass the command via stdin-safe single arg.
        cmd = [
            self.wsl_exe, "-d", self.distro,
            "--cd", self.expand_wsl(workdir),
            "-e", "bash", "-lc", bash_cmd,
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8",
            bufsize=1,
            errors="replace",
        )

        def pump():
            try:
                for line in proc.stdout:
                    stripped = line.rstrip("\n")
                    # Mirror WSL process output to the session log file so
                    # crashes can be diagnosed after the window is gone.
                    try:
                        with open(_session_log_path(), "a", encoding="utf-8",
                                  errors="replace") as f:
                            f.write(f"[wsl] {stripped}\n")
                    except Exception:
                        pass
                    if on_line:
                        on_line(stripped)
            finally:
                proc.wait()
                if on_done:
                    on_done(proc.returncode)

        threading.Thread(target=pump, daemon=True).start()
        return proc

    def run_simple(self, bash_cmd, workdir="~", timeout=60):
        """Blocking run, returns (returncode, output)."""
        cmd = [
            self.wsl_exe, "-d", self.distro,
            "--cd", self.expand_wsl(workdir),
            "-e", "bash", "-lc", bash_cmd,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                timeout=timeout, errors="replace",
            )
            return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            return -1, "timed out"

    def path_exists(self, wsl_path):
        dest = self.expand_wsl(wsl_path)
        rc, _ = self.run_simple(f'test -e {sh_escape(dest)} && echo yes')
        return rc == 0

    def deploy_file(self, local_text, wsl_dest):
        """Write text content to a file inside WSL (via stdin, no quoting pain)."""
        dest = self.expand_wsl(wsl_dest)
        cmd = [
            self.wsl_exe, "-d", self.distro,
            "-e", "bash", "-lc", f"cat > {sh_escape(dest)}",
        ]
        proc = subprocess.run(
            cmd, input=local_text, capture_output=True,
            text=True, encoding="utf-8", timeout=60, errors="replace",
        )
        return proc.returncode == 0


def sh_escape(s):
    """Single-quote escape for bash."""
    return "'" + s.replace("'", "'\"'\"'") + "'"
