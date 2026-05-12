from tkinter import filedialog, messagebox
import tkinter as tk
import threading
import sys
import os

#ok

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

os.chdir(get_base_path())


def browse_folder():
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder to process")
    root.destroy()
    return folder


def run_batch(folder, taxon, output_format):
    import main

    supported = (".txt", ".xlsx", ".xls", ".ods")
    files = [f for f in os.listdir(folder) if f.endswith(supported)]

    if not files:
        print("No supported files found in folder.")
        return

    out_dir = os.path.join(folder, "aligned")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Found {len(files)} file(s) to process")
    print(f"Output folder: {out_dir}\n")

    for i, filename in enumerate(files, 1):
        filepath = os.path.join(folder, filename)
        print(f"[{i}/{len(files)}] Processing: {filename}")
        try:
            main.run(taxon, filepath, output_format, out_dir=out_dir)
        except Exception as e:
            print(f"  Error: {e}")
        print()

    print("Batch complete.")


def launch_batch_gui():
    from taxon import taxon_id

    root = tk.Tk()
    root.title("Batch Gene Alignment Pipeline")
    root.geometry("440x320")

    # Folder
    tk.Label(root, text="Source folder:").pack(pady=5)
    folder_var = tk.StringVar()
    folder_frame = tk.Frame(root)
    folder_frame.pack()
    tk.Entry(folder_frame, textvariable=folder_var, width=35).pack(side="left")
    tk.Button(folder_frame, text="Browse",
              command=lambda: folder_var.set(filedialog.askdirectory(title="Select folder"))).pack(side="left", padx=5)

    # Taxon
    tk.Label(root, text="Studied taxon:").pack(pady=5)
    TAXONS = ["Anas platyrhynchos", "Columba livia", "Gallus gallus", "Taeniopygia guttata"]
    taxon_var = tk.StringVar(value=TAXONS[0])
    for t in TAXONS:
        tk.Radiobutton(root, text=t, variable=taxon_var, value=t).pack(anchor="w", padx=20)

    # Output format
    format_var = tk.StringVar(value="txt")
    format_frame = tk.Frame(root)
    format_frame.pack(pady=5)
    tk.Label(format_frame, text="Output format:").pack(side="left")
    tk.Radiobutton(format_frame, text=".txt", variable=format_var, value="txt").pack(side="left")
    tk.Radiobutton(format_frame, text=".xlsx", variable=format_var, value="xlsx").pack(side="left")
    tk.Radiobutton(format_frame, text=".ods",  variable=format_var, value="ods").pack(side="left")

    def run():
        folder = folder_var.get().strip()
        taxon = taxon_var.get()
        if not folder:
            messagebox.showerror("Error", "Select a folder")
            return
        root.destroy()

        root2 = tk.Tk()
        root2.title("Running...")
        root2.geometry("900x500")

        from gui import TextRedirector
        text = tk.Text(root2, state="disabled", font=("Courier", 10))
        text.pack(fill="both", expand=True, padx=5, pady=5)
        bar_label = tk.Label(root2, text="", font=("Courier", 10), anchor="w", bg="lightgrey")
        bar_label.pack(side="bottom", fill="x", padx=5, pady=2)

        sys.stdout = TextRedirector(text, bar_label)
        sys.stderr = TextRedirector(text, bar_label)
        root2.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

        threading.Thread(target=lambda: run_batch(folder, taxon, format_var.get()), daemon=True).start()
        root2.mainloop()

    tk.Button(root, text="Run", command=run).pack(pady=10)
    root.mainloop()


launch_batch_gui()