# gui_wrapper.py
import os
import sys
import time
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

# --- Optional drag & drop support ---
HAS_DND = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # pip install tkinterdnd2
    HAS_DND = True
except Exception:
    pass

# Import your pipeline
from app import main  # main(folder_path: Path, progress_cb=None, out_dir: Path|None=None) -> str

#################### NEWLY ADDED ####################
# Helper to find resources when bundled with PyInstaller
def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", Path(__file__).parent)
    return Path(base) / rel

# Choose a safe default output folder (e.g., Desktop/IDS-Results)
def default_output_dir() -> Path:
    return Path.home() / "Desktop" / "IDS-Results"

# Ensure we don’t rely on cwd
os.makedirs(default_output_dir(), exist_ok=True)
#####################################################

selected_folder: Path | None = None
selected_out_dir: Path | None = None
worker_thread: threading.Thread | None = None
stop_requested = False

def fmt_eta(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}h {m:02d}m {s:02d}s"
    if m:
        return f"{m:d}m {s:02d}s"
    return f"{s:d}s"

def choose_input_folder():
    global selected_folder
    folder = filedialog.askdirectory(title="Select Input Folder")
    if folder:
        selected_folder = Path(folder)
        input_label.config(text=f"Input: {selected_folder}")
        run_btn.config(state=tk.NORMAL)
    else:
        input_label.config(text="Input: (none)")
        run_btn.config(state=tk.DISABLED)

def choose_output_folder():
    global selected_out_dir
    folder = filedialog.askdirectory(title="Select Output Folder")
    if folder:
        selected_out_dir = Path(folder)
        out_label.config(text=f"Output: {selected_out_dir}")
    else:
        # keep previous or None
        if selected_out_dir:
            out_label.config(text=f"Output: {selected_out_dir}")
        else:
            out_label.config(text="Output: (default ./out)")

def set_busy(is_busy: bool):
    state = tk.DISABLED if is_busy else tk.NORMAL
    run_btn.config(state=state)
    pick_in_btn.config(state=state)
    pick_out_btn.config(state=state)
    if HAS_DND:
        drop_label.config(state=state)

def on_drop(event):
    """Handle drag-and-drop of a folder. Multiple items may come in; use the first folder."""
    global selected_folder
    # event.data can be a space-separated list of paths, possibly quoted
    raw = event.data
    # On macOS, TkinterDnD sends paths like { /Users/you/My Folder }
    parts = root.splitlist(raw)
    for p in parts:
        p = Path(p)
        if p.is_dir():
            selected_folder = p
            input_label.config(text=f"Input: {selected_folder}")
            run_btn.config(state=tk.NORMAL)
            break

def progress_cb(done: int, total: int, msg: str, elapsed: float):
    # Called from worker thread → use thread-safe UI updates via .after
    def _update():
        pct = 0.0 if total == 0 else done / max(1, total)
        progress["value"] = pct * 100
        status_var.set(f"{msg}  ({done}/{total})  |  elapsed {fmt_eta(elapsed)}")
    root.after(0, _update)

def open_in_finder(path: Path):
    try:
        if sys.platform == "darwin":
            os.system(f'open "{path}"')
        elif os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass

def run_pipeline():
    global worker_thread, stop_requested
    if not selected_folder or not selected_folder.exists():
        messagebox.showerror("No input", "Please select a valid input folder.")
        return

    # Resolve output directory default
    out_dir = selected_out_dir or (Path.cwd() / "out")

    # Ensure out_dir is creatable before starting
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        test = out_dir / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
    except Exception as e:
        messagebox.showerror("Output not writable",
                             f"Could not create or write to output folder:\n{out_dir}\n\n{e}")
        return

    def task():
        set_busy(True)
        progress["value"] = 0
        status_var.set("Starting…")

        try:
            t0 = time.time()
            out_file = main(folder_path=selected_folder, progress_cb=progress_cb, out_dir=out_dir)
            elapsed = time.time() - t0
            status_var.set(f"Done in {fmt_eta(elapsed)} → {out_file}")
            # Offer to open output
            if out_file:
                try:
                    of = Path(out_file)
                    if of.exists():
                        open_in_finder(of.parent)
                except Exception:
                    pass
            messagebox.showinfo("Completed", f"Results saved to:\n{out_file}")
        except Exception as e:
            status_var.set("Error")
            traceback.print_exc()
            messagebox.showerror("Error", f"{e}\n\n{traceback.format_exc()}")
        finally:
            set_busy(False)

    worker_thread = threading.Thread(target=task, daemon=True)
    worker_thread.start()

# --- UI Setup ---
RootClass = TkinterDnD.Tk if HAS_DND else tk.Tk
root = RootClass()
root.title("IDS Extractor")
root.geometry("640x360")

container = ttk.Frame(root, padding=16)
container.pack(fill="both", expand=True)

title_lbl = ttk.Label(container, text="IDS / Patent PDF Extractor", font=("Arial", 16, "bold"))
title_lbl.pack(anchor="w", pady=(0, 8))

# Input row
row1 = ttk.Frame(container)
row1.pack(fill="x", pady=4)
pick_in_btn = ttk.Button(row1, text="Choose Input Folder…", command=choose_input_folder)
pick_in_btn.pack(side="left")
input_label = ttk.Label(row1, text="Input: (none)")
input_label.pack(side="left", padx=8)

# Optional output row
row2 = ttk.Frame(container)
row2.pack(fill="x", pady=4)
pick_out_btn = ttk.Button(row2, text="Choose Output Folder…", command=choose_output_folder)
pick_out_btn.pack(side="left")
out_label = ttk.Label(row2, text="Output: (default ./out)")
out_label.pack(side="left", padx=8)

# Drag & Drop area (if available)
if HAS_DND:
    drop_label = tk.Label(container, text="…or drag a folder here …",
                          relief="groove", height=4, padx=8, pady=8)
    drop_label.pack(fill="x", pady=10)
    drop_label.drop_target_register(DND_FILES)
    drop_label.dnd_bind("<<Drop>>", on_drop)
else:
    drop_label = ttk.Label(container, text="(Install 'tkinterdnd2' to enable drag-and-drop)")
    drop_label.pack(anchor="w", pady=(6, 10))

# Progress
progress = ttk.Progressbar(container, orient="horizontal", mode="determinate", length=400)
progress.pack(fill="x", pady=(8, 6))
status_var = tk.StringVar(value="Idle")
status_lbl = ttk.Label(container, textvariable=status_var)
status_lbl.pack(fill="x")

# Run button
run_btn = ttk.Button(container, text="Run Extraction", command=run_pipeline, state=tk.DISABLED)
run_btn.pack(pady=10)

root.mainloop()


