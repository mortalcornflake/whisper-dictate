# Windows Setup (developer / early-tester guide)

> This is the **temporary developer bootstrap** for getting Whisper Dictate
> running on Windows while we build it. The finished product (Phase 4) will be a
> one-click installer that needs **none** of this. See `CROSS_PLATFORM.md` for the
> overall plan.

## Status: what works on Windows today

- ✅ The **faster-whisper transcription engine** + GPU auto-detection (test it
  with `check_setup.py`).
- ⏳ The **full app** (`dictate.py`) does **not** run on Windows yet —
  `platform_io/windows.py` is a stub (Phase 3). Don't run `dictate.py` on Windows
  until Phase 3 lands; it will crash on the first sound/paste.

So the first goal on Windows is simply: **confirm the NVIDIA GPU works and
transcription is good.**

## 1. Install Python 3.12

- Download from <https://www.python.org/downloads/> (get **3.12.x**, not 3.13 —
  some packages don't have 3.13 builds yet).
- On the first installer screen, **tick "Add python.exe to PATH"**, then install.
- Verify in a new PowerShell window:
  ```powershell
  python --version
  pip --version
  ```

## 2. Get the code

Download the repo as a ZIP from GitHub (green **Code** button → **Download ZIP**)
and unzip it somewhere simple like `C:\whisper-dictate`.

## 3. Create a virtual environment and install dependencies

Open **PowerShell**, then:

```powershell
cd C:\whisper-dictate
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks the activate script ("running scripts is disabled"), run
this once, then retry the activate line:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then install:

```powershell
pip install -r requirements.txt -r requirements-windows.txt
```

This pulls in faster-whisper and the NVIDIA CUDA runtime wheels. You do **not**
need the standalone CUDA Toolkit — just an up-to-date NVIDIA GPU driver (you
almost certainly already have one).

## 4. Run the setup check

```powershell
python check_setup.py
```

This reports your OS/Python, checks every dependency, prints the detected
**device / VRAM / model / compute type**, loads the model (first run downloads
it), then records 4 seconds from your mic and transcribes it. You can also pass a
WAV file instead of using the mic: `python check_setup.py some_audio.wav`.

**What you want to see:** `device detected : cuda` and `>>> NVIDIA GPU will be
used.`, followed by a correct transcript. If it says `cpu`, transcription still
works (just slower) — tell the developer and we'll look at the CUDA setup.

## 5. Install Claude Code (to continue development on this PC)

The Windows phases are done with Claude Code running on this machine. Native
Windows is preferred here (we need direct GPU + filesystem access — not WSL).

- **No Node.js needed** — Claude Code is a native binary.
- In PowerShell, install it:
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```
  This installs to `%USERPROFILE%\.local\bin\` and auto-updates.
- Sign in (opens a browser the first time):
  ```powershell
  claude
  ```
- Then start it in the project folder:
  ```powershell
  cd C:\whisper-dictate
  claude
  ```
- Optional: install [Git for Windows](https://git-scm.com/downloads/win) so the
  session can use Bash and push changes back to GitHub.
- If PowerShell complains about script execution, run once:
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`.

Verify with `claude --version`.

## 6. Next

Once the GPU + transcription check passes and Claude Code is running here, point
the session at **`WINDOWS_AGENT_BRIEF.md`** — it's a complete, self-contained
brief for a fresh Claude session (it assumes no memory of prior conversations).
From there it picks up **Phase 3** (Windows adapter + tray app) and **Phase 4**
(installer). See `CROSS_PLATFORM.md` for the full plan.
