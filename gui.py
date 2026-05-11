from taxon import taxon_id, taxon_suggestions
from tkinter import filedialog, messagebox
import tkinter as tk
import threading
import platform
import subprocess
import main
import json
import sys
import os


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()
os.chdir(base_path)
HISTORY_FILE = os.path.join(base_path, "last_taxon.json")


class TextRedirector:
    def __init__(self, text_widget, bar_widget):
        self.text = text_widget
        self.bar = bar_widget

    def write(self, text_content):
        if "\r" in text_content and "\n" not in text_content:
            def _update_bar(t=text_content):
                self.bar.config(text=t.replace("\r", ""))
            self.bar.after(0, _update_bar)
        else:
            def _insert(t=text_content):
                self.text.config(state="normal")
                self.text.insert("end", t)
                self.text.see("end")
                self.text.config(state="disabled")
            self.text.after(0, _insert)

    def flush(self):
        pass


def load_last_taxon():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f).get("taxon", "")
    return ""


def save_last_taxon(taxon):
    with open(HISTORY_FILE, "w") as f:
        json.dump({"taxon": taxon}, f)


def browse_file(file_var):
    if platform.system() == "Windows":
        path = filedialog.askopenfilename(
            title="Select source file",
            filetypes=[("Supported files", "*.txt *.xlsx *.xls"), ("All files", "*.*")]
        )
    else:
        try:
            result = subprocess.run(
                ["zenity", "--file-selection", "--title=Select source file",
                 "--file-filter=Supported files (txt xlsx xls) | *.txt *.xlsx *.xls",
                 "--file-filter=All files | *"],
                capture_output=True, text=True
            )
            path = result.stdout.strip() if result.returncode == 0 else ""
        except FileNotFoundError:
            path = filedialog.askopenfilename(
                title="Select source file",
                filetypes=[("Supported files", "*.txt *.xlsx *.xls"), ("All files", "*.*")]
            )
    if path:
        file_var.set(path)


last = load_last_taxon()
TAXONS = ["Anas platyrhynchos", "Columba livia", "Gallus gallus", "Taeniopygia guttata"]
if last and last not in TAXONS:
    TAXONS.append(last)


def launch_gui():
    root = tk.Tk()
    root.title("Gene Alignment Pipeline")
    root.geometry("440x420")

    tk.Label(root, text="Studied taxon:").pack(pady=5)
    taxon_var = tk.StringVar(value=TAXONS[0])
    custom_var = tk.StringVar()
    frame = tk.Frame(root)
    frame.pack()

    def on_select():
        state = "normal" if taxon_var.get() == "Autre" else "disabled"
        custom_entry.config(state=state)
        validate_btn.config(state=state)

    def validate_custom():
        taxon = custom_var.get().strip()
        if not taxon:
            return
        result = taxon_id(taxon)
        if result:
            messagebox.showinfo("✓", f"Found taxon: {taxon}")
        else:
            suggestions = taxon_suggestions(taxon)
            msg = "Non-existing taxon."
            if suggestions:
                msg += f"\nClosest match: {suggestions[0]}"
            messagebox.showwarning("Non-existing taxon", msg)

    for taxon in TAXONS:
        tk.Radiobutton(frame, text=taxon, variable=taxon_var, value=taxon, command=on_select).pack(anchor="w")
    tk.Radiobutton(frame, text="Other:", variable=taxon_var, value="Autre", command=on_select).pack(anchor="w")

    custom_frame = tk.Frame(frame)
    custom_frame.pack(anchor="w", padx=20)
    custom_entry = tk.Entry(custom_frame, textvariable=custom_var, width=25, state="disabled")
    custom_entry.pack(side="left")
    validate_btn = tk.Button(custom_frame, text="Check", command=validate_custom, state="disabled")
    validate_btn.pack(side="left", padx=5)

    tk.Label(root, text="Source file:").pack(pady=5)
    file_var = tk.StringVar()
    file_frame = tk.Frame(root)
    file_frame.pack()
    tk.Entry(file_frame, textvariable=file_var, width=35).pack(side="left")
    tk.Button(file_frame, text="Browse", command=lambda: browse_file(file_var)).pack(side="left", padx=5)

    format_var = tk.StringVar(value="txt")
    format_frame = tk.Frame(root)
    format_frame.pack(pady=5)
    tk.Label(format_frame, text="Output format:").pack(side="left")
    tk.Radiobutton(format_frame, text=".txt", variable=format_var, value="txt").pack(side="left")
    tk.Radiobutton(format_frame, text=".xlsx", variable=format_var, value="xlsx").pack(side="left")

    def run():
        taxon = custom_var.get().strip() if taxon_var.get() == "Autre" else taxon_var.get()
        filepath = file_var.get().strip()
        if not taxon or not filepath:
            messagebox.showerror("Error", "Fill all fields")
            return
        if taxon not in TAXONS[:4]:
            save_last_taxon(taxon)
        root.destroy()

        root2 = tk.Tk()
        root2.title("Running...")
        root2.geometry("900x500")
        root2.minsize(600, 300)

        text = tk.Text(root2, state="disabled", font=("Courier", 10))
        text.pack(fill="both", expand=True, padx=5, pady=5)

        bar_label = tk.Label(root2, text="", font=("Courier", 10), anchor="w", bg="lightgrey")
        bar_label.pack(side="bottom", fill="x", padx=5, pady=2)

        redirector = TextRedirector(text, bar_label)
        sys.stdout = redirector
        sys.stderr = redirector

        root2.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))
        root2.update()

        def pipeline():
            try:
                main.run(taxon, filepath, format_var.get())
            except Exception as e:
                err = str(e)
                root2.after(0, lambda: messagebox.showerror("Error", err))
            finally:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__

        threading.Thread(target=pipeline, daemon=True).start()
        root2.mainloop()

    tk.Button(root, text="Run", command=run).pack(pady=10)
    root.mainloop()


launch_gui()