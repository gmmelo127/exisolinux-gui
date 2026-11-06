#!/usr/bin/env python3
"""
ExIso linux gui
Interface gráfica para extrair ISOs de Xbox 360 e aplicar patch para devkit.

Interface criada por: gmmelo127
Scripts originais por: ljmellor

Requisitos (Linux):
    sudo apt install python3-tk wine
    extract-xiso/extract-xiso   (binário, ao lado deste script)
    winbins/xextool.exe         (ao lado deste script)
"""

import os
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")

DEFAULT_ISO_DIR = os.path.join(HOME, "Downloads/Finished/Games/XBOX360/ISO/")
DEFAULT_DEST_DIR = os.path.join(HOME, "XBOX360-EXT/Games/")
DEFAULT_EXTRACT_XISO = os.path.join(BASE_DIR, "extract-xiso", "extract-xiso")
DEFAULT_XEXTOOL = os.path.join(BASE_DIR, "winbins", "xextool.exe")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ExIso linux gui")
        self.geometry("760x620")
        self.minsize(640, 520)

        self.iso_var = tk.StringVar()
        self.dest_var = tk.StringVar(value=DEFAULT_DEST_DIR)
        self.name_var = tk.StringVar()
        self.subfolder_var = tk.BooleanVar(value=True)
        self.patch_xex_var = tk.BooleanVar(value=True)
        self.patch_dll_var = tk.BooleanVar(value=True)
        self.xiso_var = tk.StringVar(value=DEFAULT_EXTRACT_XISO)
        self.xextool_var = tk.StringVar(value=DEFAULT_XEXTOOL)

        self.log_queue = queue.Queue()
        self.worker = None
        self.current_proc = None
        self.cancel_flag = threading.Event()

        self._build_ui()
        self.after(100, self._drain_log)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        # --- Arquivos
        files = ttk.LabelFrame(main, text="Arquivos", padding=8)
        files.grid(row=0, column=0, columnspan=3, sticky="ew")
        files.columnconfigure(1, weight=1)

        ttk.Label(files, text="ISO:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(files, textvariable=self.iso_var).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(files, text="Procurar…", command=self.pick_iso).grid(row=0, column=2, **pad)

        ttk.Label(files, text="Destino:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(files, textvariable=self.dest_var).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(files, text="Procurar…", command=self.pick_dest).grid(row=1, column=2, **pad)

        ttk.Label(files, text="Nome do jogo:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(files, textvariable=self.name_var).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Checkbutton(
            files,
            text="Criar subpasta com o nome do jogo dentro do destino",
            variable=self.subfolder_var,
        ).grid(row=3, column=1, columnspan=2, sticky="w", **pad)

        # --- Opções
        opts = ttk.LabelFrame(main, text="Patch devkit (xextool -ra -md)", padding=8)
        opts.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(opts, text="Aplicar em arquivos .xex", variable=self.patch_xex_var).pack(side="left", padx=8)
        ttk.Checkbutton(opts, text="Aplicar em arquivos .dll", variable=self.patch_dll_var).pack(side="left", padx=8)

        # --- Ferramentas
        tools = ttk.LabelFrame(main, text="Ferramentas", padding=8)
        tools.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        tools.columnconfigure(1, weight=1)

        ttk.Label(tools, text="extract-xiso:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(tools, textvariable=self.xiso_var).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(tools, text="…", width=3, command=lambda: self.pick_file(self.xiso_var)).grid(row=0, column=2, **pad)

        ttk.Label(tools, text="xextool.exe:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(tools, textvariable=self.xextool_var).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(tools, text="…", width=3, command=lambda: self.pick_file(self.xextool_var)).grid(row=1, column=2, **pad)

        # --- Botões
        btns = ttk.Frame(main)
        btns.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        self.start_btn = ttk.Button(btns, text="▶ Extrair e aplicar patch", command=self.start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="■ Cancelar", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        ttk.Button(btns, text="Limpar log", command=self.clear_log).pack(side="right")

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew")

        # --- Log
        log_frame = ttk.LabelFrame(main, text="Log", padding=4)
        log_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        main.rowconfigure(5, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(log_frame, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)

        # --- Créditos
        ttk.Label(
            main,
            text="ExIso linux gui  •  Interface por gmmelo127  •  Scripts originais por ljmellor",
            foreground="gray",
            anchor="center",
        ).grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    # --------------------------------------------------------- Seleções
    def pick_iso(self):
        initial = DEFAULT_ISO_DIR if os.path.isdir(DEFAULT_ISO_DIR) else HOME
        path = filedialog.askopenfilename(
            title="Selecione a ISO para extrair",
            initialdir=initial,
            filetypes=[("ISO", "*.iso"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.iso_var.set(path)
            if not self.name_var.get():
                self.name_var.set(os.path.splitext(os.path.basename(path))[0])

    def pick_dest(self):
        initial = self.dest_var.get() if os.path.isdir(self.dest_var.get()) else HOME
        path = filedialog.askdirectory(title="Selecione a pasta de destino", initialdir=initial)
        if path:
            self.dest_var.set(path)

    def pick_file(self, var):
        path = filedialog.askopenfilename(title="Selecione o arquivo", initialdir=BASE_DIR)
        if path:
            var.set(path)

    # -------------------------------------------------------------- Log
    def write_log(self, text):
        self.log_queue.put(text)

    def _drain_log(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", text)
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log)

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # ---------------------------------------------------------- Execução
    def start(self):
        iso = self.iso_var.get().strip()
        dest = self.dest_var.get().strip()
        name = self.name_var.get().strip()
        xiso = self.xiso_var.get().strip()
        xextool = self.xextool_var.get().strip()

        if not iso or not os.path.isfile(iso):
            messagebox.showerror("Erro", "Selecione uma ISO válida.")
            return
        if not dest:
            messagebox.showerror("Erro", "Selecione a pasta de destino.")
            return
        if not name:
            name = os.path.splitext(os.path.basename(iso))[0]
            self.name_var.set(name)
        if not os.path.isfile(xiso):
            messagebox.showerror("Erro", f"extract-xiso não encontrado:\n{xiso}")
            return
        patch = self.patch_xex_var.get() or self.patch_dll_var.get()
        if patch and not os.path.isfile(xextool):
            messagebox.showerror("Erro", f"xextool.exe não encontrado:\n{xextool}")
            return

        final_dest = os.path.join(dest, name) if self.subfolder_var.get() else dest

        ok = messagebox.askyesno(
            "Confirmar",
            f"Nome: {name}\n\nISO: {iso}\n\nDestino: {final_dest}\n\nContinuar?",
        )
        if not ok:
            return

        self.cancel_flag.clear()
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress.start(12)

        self.worker = threading.Thread(
            target=self._run, args=(iso, final_dest, name, xiso, xextool), daemon=True
        )
        self.worker.start()

    def cancel(self):
        self.cancel_flag.set()
        if self.current_proc and self.current_proc.poll() is None:
            self.current_proc.terminate()
        self.write_log("\n>>> Cancelando…\n")

    def _run_cmd(self, cmd):
        """Executa um comando e envia a saída para o log. Retorna o código de saída."""
        self.write_log("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")
        try:
            self.current_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )
        except FileNotFoundError as e:
            self.write_log(f"ERRO: {e}\n")
            return 127
        for line in self.current_proc.stdout:
            self.write_log(line)
        return self.current_proc.wait()

    def _run(self, iso, dest, name, xiso, xextool):
        success = False
        try:
            os.makedirs(dest, exist_ok=True)

            # 1) Extração
            self.write_log(f"=== Extraindo {os.path.basename(iso)} ===\n")
            code = self._run_cmd([xiso, "-x", iso, "-d", dest])
            if self.cancel_flag.is_set():
                self.write_log("Extração cancelada.\n")
                return
            if code != 0:
                self.write_log(f"\nextract-xiso falhou (código {code}).\n")
                return

            # 2) Patch
            exts = []
            if self.patch_xex_var.get():
                exts.append(".xex")
            if self.patch_dll_var.get():
                exts.append(".dll")

            if exts:
                targets = []
                for root, _dirs, files in os.walk(dest):
                    for f in files:
                        if f.lower().endswith(tuple(exts)):
                            targets.append(os.path.join(root, f))
                self.write_log(f"\n=== Aplicando patch em {len(targets)} arquivo(s) ===\n")
                for path in targets:
                    if self.cancel_flag.is_set():
                        self.write_log("Patch cancelado.\n")
                        return
                    self._run_cmd(["wine", xextool, "-ra", "-md", path])

            success = True
            self.write_log(f"\n✔ Concluído: {name}\nArquivos em: {dest}\n")
        except Exception as e:  # noqa: BLE001
            self.write_log(f"\nErro inesperado: {e}\n")
        finally:
            self.current_proc = None
            self.after(0, self._finish, success, name, dest)

    def _finish(self, success, name, dest):
        self.progress.stop()
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        if success:
            messagebox.showinfo(
                "Concluído",
                f"Extração de {name} finalizada.\n\nLocal:\n{dest}\n\n"
                "Os executáveis foram patcheados para devkit.",
            )


if __name__ == "__main__":
    App().mainloop()
