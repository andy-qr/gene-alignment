from taxon import taxon_id, taxon_suggestions
from tkinter import filedialog, messagebox
import tkinter as tk
import main
import json
import sys
import os

HISTORY_FILE = "last_taxon.json"

class TextRedirector:
    def __init__(self, text_widget, bar_widget):
        self.text = text_widget
        self.bar = bar_widget

    def write(self, text_content):
        if "\r" in text_content and "\n" not in text_content:
            self.bar.config(text=text_content.replace("\r", ""))
            self.bar.update()
        else:
            self.text.config(state="normal")
            self.text.insert("end", text_content)
            self.text.see("end")
            self.text.config(state="disabled")
            self.text.update()

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

last = load_last_taxon()
TAXONS = ["Anas platyrhynchos", "Columba livia", "Gallus gallus", "Taeniopygia guttata"]
if last and last not in TAXONS:
    TAXONS.append(last)

def launch_gui():
    root = tk.Tk()
    root.title("Gene Alignment Pipeline")
    root.geometry("420x320")

    tk.Label(root, text="Studied taxon:").pack(pady=5)
    taxon_var = tk.StringVar(value=TAXONS[0])
    custom_var = tk.StringVar()
    frame = tk.Frame(root)
    frame.pack()

    def on_select():
        custom_entry.config(state="normal" if taxon_var.get() == "Autre" else "disabled")

    def validate_custom():
        taxon = custom_var.get().strip()
        if not taxon:
            return
        result = taxon_id(taxon)
        if result:
            messagebox.showinfo("✓", f"Found taxon : {taxon}")
        else:
            suggestions = taxon_suggestions(taxon)  # à implémenter dans taxon.py
            msg = "Non-existing taxon."
            if suggestions:
                msg += f"\nLe plus proche : {suggestions[0]}"
            messagebox.showwarning("Non-existing taxon.", msg)

    for taxon in TAXONS:
        tk.Radiobutton(frame, text=taxon, variable=taxon_var, value=taxon, command=on_select).pack(anchor="w")
    tk.Radiobutton(frame, text="Autre :", variable=taxon_var, value="Autre", command=on_select).pack(anchor="w")
    custom_entry = tk.Entry(frame, textvariable=custom_var, width=30, state="disabled")
    custom_entry.pack(anchor="w", padx=20)
    tk.Button(frame, text="Search", command=validate_custom).pack(anchor="w", padx=20)

    file_var = tk.StringVar()
    def browse():
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        file_var.set(path)

    tk.Label(root, text="Source file:").pack(pady=5)
    file_frame = tk.Frame(root)
    file_frame.pack()
    tk.Entry(file_frame, textvariable=file_var, width=35).pack(side="left")
    tk.Button(file_frame, text="Browse", command=browse).pack(side="left", padx=5)

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
        root2.geometry("800x400")
        text = tk.Text(root2, state="disabled", width=120, height=23)
        text.pack()
        bar_label = tk.Label(root2, text="", font=("Courier", 10), width=120, anchor="w")
        bar_label.pack()
        sys.stdout = TextRedirector(text, bar_label)
        sys.stderr = TextRedirector(text, bar_label)
        root2.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))
        root2.update()

        try:
            main.run(taxon, filepath)
        except Exception as e:
            messagebox.showerror("Error", str(e))
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    tk.Button(root, text="Run", command=run).pack(pady=10)
    root.mainloop()

launch_gui()