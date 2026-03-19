"""
GUI för Image Optimizer (Tkinter + tkinterdnd2).
Laddas lazy från main.py så py2app/byggverktyg kan importera main utan Tk.
"""

import json
import re
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image
import tinify


class ImageOptimizerApp:
    def __init__(self, root, initial_files=None):
        self.root = root
        self.root.title("Image Optimizer")
        self.root.geometry("700x750")

        # Ladda API-nyckel
        self.api_key = self.load_api_key()
        if self.api_key:
            tinify.key = self.api_key

        # Tillstånd för att blockera ändringar av listan under pågående bearbetning.
        self.is_processing = False

        # Lista över filer att behandla
        self.files_to_process = []
        self.output_dir = None

        # Skapa GUI
        try:
            self.create_widgets()
        except Exception:
            self._write_runtime_error(traceback.format_exc())
            raise

        # Filer från argv (släppta på app-ikonen) — bara i listan, ingen auto-optimering
        if initial_files:
            self._add_files_to_list(initial_files)

    def _bundle_dir(self):
        """Skrivskyddad app-resurs (t.ex. inbyggd config.json i .app)."""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).resolve().parent.parent / 'Resources'
        return Path(__file__).resolve().parent

    def _writable_config_dir(self):
        """Plats där vi får skriva (viktigt för signerad .app där Resources är read-only)."""
        if sys.platform == 'darwin':
            d = Path.home() / 'Library' / 'Application Support' / 'Image Optimizer'
        else:
            d = Path.home() / '.image-optimizer'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _user_config_path(self):
        return self._writable_config_dir() / 'config.json'

    def _write_runtime_error(self, text: str):
        """Skriv runtime-fel till logg som är lätt att hitta för användaren."""
        try:
            log_path = self._writable_config_dir() / "app_run.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n=== Runtime Error ===\n")
                f.write(text)
                if not text.endswith("\n"):
                    f.write("\n")
        except Exception:
            pass

    def _bundled_config_path(self):
        return self._bundle_dir() / 'config.json'

    def load_api_key(self):
        """Ladda API-nyckel: först användarens config, annars inbyggd bundle-config."""
        for path in (self._user_config_path(), self._bundled_config_path()):
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        config = json.load(f)
                        key = config.get('tinypng_api_key')
                        if key:
                            return key
                except Exception as e:
                    print(f"Kunde inte ladda config ({path}): {e}")
        return None

    def save_api_key(self, api_key):
        """Spara API-nyckel till skrivbar användar-mapp (inte i .app-bundle)."""
        config_file = self._user_config_path()
        try:
            with open(config_file, 'w') as f:
                json.dump({'tinypng_api_key': api_key}, f, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Fel", f"Kunde inte spara API-nyckel: {e}")
            return False

    def create_widgets(self):
        """Simplified, stable UI (no decorative canvas artifacts)."""
        self.root.geometry("860x590")
        self.root.resizable(False, False)
        self.root.minsize(860, 590)
        self.root.maxsize(860, 590)
        self.root.configure(bg="#F3F3F4")

        ui_bg = "#F3F3F4"
        body = tk.Frame(self.root, bg=ui_bg)
        body.pack(fill=tk.BOTH, expand=True, padx=24, pady=18)

        grid = tk.Frame(body, bg=ui_bg)
        grid.pack(fill=tk.BOTH, expand=True)
        grid.grid_columnconfigure(0, weight=40, uniform="g")
        grid.grid_columnconfigure(1, weight=60, uniform="g")
        grid.grid_rowconfigure(0, weight=1)

        left = tk.Frame(grid, bg=ui_bg)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = tk.Frame(grid, bg="#F8F8F9", highlightthickness=1, highlightbackground="#E0E1E5")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.right_card = right

        # Left column buttons
        btn_row = tk.Frame(left, bg=ui_bg)
        btn_row.pack(fill=tk.X, pady=(0, 14))

        self.select_button = tk.Canvas(btn_row, width=200, height=42, bg=ui_bg, highlightthickness=0, bd=0)
        self.select_button.pack(side=tk.LEFT, padx=(0, 12))

        def _draw_select_button(_event=None):
            self.select_button.delete("all")
            w = max(self.select_button.winfo_width(), 1)
            h = max(self.select_button.winfo_height(), 1)
            top = (0x4D, 0x8D, 0xFF)      # #4D8DFF
            bottom = (0x3C, 0x78, 0xE8)   # #3C78E8
            for y in range(h):
                t = y / max(h - 1, 1)
                r = int(top[0] + (bottom[0] - top[0]) * t)
                g = int(top[1] + (bottom[1] - top[1]) * t)
                b = int(top[2] + (bottom[2] - top[2]) * t)
                self.select_button.create_line(0, y, w, y, fill=f"#{r:02x}{g:02x}{b:02x}")
            self.select_button.create_text(
                w / 2,
                h / 2,
                text="+  Select images",
                fill="#FFFFFF",
                font=("SF Pro Display", 16, "bold"),
            )

        self.select_button.bind("<Configure>", _draw_select_button)
        self.select_button.bind("<Button-1>", lambda _e: self.select_files())
        self.select_button.bind("<Enter>", lambda _e: self.select_button.config(cursor="pointinghand"))
        self.select_button.bind("<Leave>", lambda _e: self.select_button.config(cursor=""))

        self.clear_button = tk.Button(
            btn_row,
            text="Clear list",
            command=self.clear_files,
            bg="#F9F9FA",
            fg="#33363A",
            activebackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#D8D8DC",
            bd=0,
            padx=18,
            pady=8,
            font=("SF Pro Display", 16, "bold"),
        )
        self.clear_button.pack(side=tk.LEFT)

        # Dropzone
        self.drop_frame = tk.Frame(left, bg="#F8F8F9", highlightthickness=1, highlightbackground="#DDDEE2", height=430)
        self.drop_frame.pack(fill=tk.X)
        self.drop_frame.pack_propagate(False)

        self.drop_canvas = tk.Canvas(self.drop_frame, bg="#F8F8F9", highlightthickness=0)
        self.drop_canvas.pack(fill=tk.BOTH, expand=True)

        def _draw_dropzone(_=None):
            self.drop_canvas.delete("all")
            w = max(self.drop_canvas.winfo_width(), 1)
            h = max(self.drop_canvas.winfo_height(), 1)
            self.drop_canvas.create_rectangle(14, 14, w - 14, h - 14, fill="#FBFBFC", outline="#D3D5DA", dash=(6, 6), width=2)
            self.drop_canvas.create_text(w / 2, h / 2 - 10, text="Drag in images", fill="#9AA0A8", font=("SF Pro Display", 15, "normal"))
            self.drop_canvas.create_text(w / 2, h / 2 + 18, text="to convert to WebP", fill="#9AA0A8", font=("SF Pro Display", 15, "normal"))

        self.drop_canvas.bind("<Configure>", _draw_dropzone)

        self.list_container = tk.Frame(self.drop_frame, bg="#FBFBFC")
        self.list_container.place(x=14, y=14, relwidth=1, relheight=1, width=-28, height=-28)
        self.list_container.place_forget()

        list_row = tk.Frame(self.list_container, bg="#FBFBFC")
        list_row.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        sb = tk.Scrollbar(list_row)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox = tk.Listbox(
            list_row,
            yscrollcommand=sb.set,
            selectmode=tk.EXTENDED,
            bg="#FBFBFC",
            fg="#39414A",
            font=("SF Pro Display", 14),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.file_listbox.yview)
        self.file_listbox.bind("<KeyPress-BackSpace>", self.delete_selected_files)
        self.file_listbox.bind("<KeyPress-Delete>", self.delete_selected_files)

        # Right settings card
        right_inner = tk.Frame(right, bg="#F8F8F9")
        right_inner.pack(fill=tk.BOTH, expand=True, padx=22, pady=22)
        tk.Label(right_inner, text="Settings", bg="#F8F8F9", fg="#2F3135", font=("SF Pro Display", 18, "normal")).pack(anchor="w", pady=(0, 14))
        tk.Frame(right_inner, bg="#E3E4E8", height=1).pack(fill=tk.X, pady=(0, 22))

        def label(parent, text):
            tk.Label(parent, text=text, bg="#F8F8F9", fg="#2F3135", font=("SF Pro Display", 16, "normal")).pack(anchor="w", pady=(0, 10))

        def input_field(parent, var, masked=False):
            e = tk.Entry(
                parent,
                textvariable=var,
                show="*" if masked else "",
                bg="#FFFFFF",
                fg="#2E3135",
                relief="flat",
                borderwidth=1,
                highlightthickness=1,
                highlightbackground="#D8DADF",
                highlightcolor="#72B8FF",
                insertbackground="#2E3135",
                font=("SF Pro Display", 15),
            )
            e.pack(fill=tk.X, ipady=9)
            return e

        label(right_inner, "TinyPNG API key")
        self.api_key_var = tk.StringVar(value=self.api_key or "")
        input_field(right_inner, self.api_key_var, masked=True)

        self.save_key_button = tk.Button(
            right_inner,
            text="Save key",
            command=self.on_save_api_key,
            bg="#F9F9FA",
            fg="#33363A",
            activebackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#D8D8DC",
            bd=0,
            font=("SF Pro Display", 16, "normal"),
            pady=8,
        )
        self.save_key_button.pack(fill=tk.X, pady=(12, 24))

        label(right_inner, "Max image size (px):")
        self.max_width_var = tk.IntVar(value=1920)
        input_field(right_inner, self.max_width_var)

        label(right_inner, "Save optimized images to")
        self.folder_button = tk.Button(
            right_inner,
            text="Select folder   >",
            command=self.select_output_dir,
            anchor="w",
            bg="#F9F9FA",
            fg="#2F3135",
            activebackground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#D8DADF",
            bd=0,
            font=("SF Pro Display", 15, "normal"),
            padx=14,
            pady=9,
        )
        self.folder_button.pack(fill=tk.X)

        self.output_label = tk.Label(
            right_inner,
            text="No folder selected (saves next to original files).",
            bg="#F8F8F9",
            fg="#8A9098",
            font=("SF Pro Display", 13),
            anchor="w",
            justify="left",
        )
        self.output_label.pack(fill=tk.X, pady=(12, 0))

        self.button_canvas = tk.Canvas(right_inner, height=72, bg="#F8F8F9", highlightthickness=0)
        self.button_canvas.pack(fill=tk.X, pady=(26, 0))
        self.button_bg = self.button_canvas.create_rectangle(0, 0, 1000, 100, fill="#37A94A", outline="#37A94A", width=0)
        self.button_text_id = self.button_canvas.create_text(500, 36, text="Optimize images!", fill="white", font=("SF Pro Display", 24, "bold"))
        self.button_canvas.bind("<Button-1>", lambda e: self.start_processing())
        self.button_canvas.bind("<Enter>", lambda e: self.button_canvas.config(cursor="pointinghand"))
        self.button_canvas.bind("<Leave>", lambda e: self.button_canvas.config(cursor=""))
        self.button_canvas.bind("<Configure>", lambda e: (self.button_canvas.coords(self.button_bg, 0, 0, e.width, e.height), self.button_canvas.coords(self.button_text_id, e.width / 2, e.height / 2)))

        # Keep left drop area bottom aligned with CTA button bottom.
        self._last_drop_h = None
        self.root.after(0, self._sync_dropzone_height_to_cta)
        self.root.bind("<Configure>", self._sync_dropzone_height_to_cta)

        try:
            self.setup_drag_drop()
        except Exception as e:
            print(f"Drag-and-drop initialization failed: {e}")
            messagebox.showwarning("Drag-and-drop", f"Could not initialize drag-and-drop:\\n{e}")

        self.progress_var = tk.DoubleVar()

    def _sync_dropzone_height_to_cta(self, _event=None):
        """Match dropzone bottom with right card bottom."""
        try:
            self.root.update_idletasks()
            drop_top = self.drop_frame.winfo_rooty()
            card_bottom = self.right_card.winfo_rooty() + self.right_card.winfo_height()
            desired_h = max(220, card_bottom - drop_top)
            if self._last_drop_h != desired_h:
                self.drop_frame.configure(height=desired_h)
                self._last_drop_h = desired_h
        except Exception:
            pass

    def setup_drag_drop(self):
        """Konfigurera drag-and-drop (försöker med tkinterdnd2 om tillgänglig)"""
        try:
            from tkinterdnd2 import DND_FILES

            for w in (self.drop_frame, self.drop_canvas, self.file_listbox):
                w.drop_target_register(DND_FILES)
                w.dnd_bind('<<Drop>>', self.on_drop)
            print("Drag-and-drop enabled with tkinterdnd2 (drop zone + list)")
        except ImportError:
            print("tkinterdnd2 is not installed - drag-and-drop is limited")
            self.root.bind('<Enter>', lambda e: self.root.focus_force())

    def on_save_api_key(self):
        """Save API key"""
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Warning", "Enter an API key first")
            return

        if self.save_api_key(api_key):
            self.api_key = api_key
            tinify.key = api_key
            messagebox.showinfo("Saved", "API key saved!")

    def select_files(self):
        """Select image files"""
        files = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[
                ("Bildfiler", "*.jpg *.jpeg *.png *.JPG *.JPEG *.PNG"),
                ("JPEG-filer", "*.jpg *.jpeg *.JPG *.JPEG"),
                ("PNG-filer", "*.png *.PNG"),
                ("Alla filer", "*.*")
            ]
        )

        if files:
            self._add_files_to_list(files)

    def clear_files(self):
        """Clear the file list"""
        self.files_to_process = []
        self.update_file_list()
        self.button_canvas.itemconfig(self.button_text_id, text="Optimize images!")

    def delete_selected_files(self, event=None):
        """Radera markerade filer från listan (Backspace/Delete)."""
        if self.is_processing:
            # Om konvertering pågår ska vi inte tillåta att listan ändras.
            return "break"

        selection = list(self.file_listbox.curselection())
        if not selection:
            return "break"

        # Ta bort från slutet för att inte förskjuta index.
        for idx in sorted(selection, reverse=True):
            if 0 <= idx < len(self.files_to_process):
                del self.files_to_process[idx]

        self.update_file_list()
        self.button_canvas.itemconfig(
            self.button_bg,
            fill="#4CAF50",
            outline="#4CAF50",
        )
        self.button_canvas.itemconfig(self.button_text_id, text="Optimize images!")

        return "break"

    def update_file_list(self):
        """Uppdatera listboxen med filer"""
        self.file_listbox.delete(0, tk.END)
        for file_path in self.files_to_process:
            self.file_listbox.insert(tk.END, Path(file_path).name)

        if self.files_to_process:
            # Visa listan när det finns filer.
            if not self.list_container.winfo_ismapped():
                self.list_container.place(x=14, y=14, relwidth=1, relheight=1, width=-28, height=-28)
        else:
            # Döljer listan i tomt läge (design: endast dashed drag-yta).
            if self.list_container.winfo_ismapped():
                self.list_container.place_forget()

    def select_output_dir(self):
        """Choose output folder"""
        directory = filedialog.askdirectory(title="Choose folder for optimized images")
        if directory:
            self.output_dir = directory
            short_path = Path(directory).name
            self.output_label.config(text=f".../{short_path}")

    def start_processing(self):
        """Starta bildbehandling i bakgrunden"""
        if self.is_processing:
            return
        if not self.api_key:
            messagebox.showwarning(
                "API key missing",
                "Enter your TinyPNG API key first"
            )
            return

        if not self.files_to_process:
            messagebox.showwarning("No files", "Select at least one image first")
            return

        try:
            tinify.key = self.api_key
            tinify.validate()
        except tinify.Error as e:
            messagebox.showerror(
                "Invalid API key",
                f"The TinyPNG API key is not valid:\n{str(e)}"
            )
            return

        self.is_processing = True

        self.button_canvas.itemconfig(self.button_bg, fill="#FF9800", outline="#FF9800")
        self.button_canvas.itemconfig(self.button_text_id, text="Working...")
        self.button_canvas.unbind("<Button-1>")
        self.button_canvas.config(cursor="")
        self.root.update()

        threading.Thread(target=self._process_images_thread, daemon=True).start()

    def _ui(self, fn):
        """Kör Tk-anrop på huvudtråden (Tk är inte trådsäkert på macOS)."""
        self.root.after(0, fn)

    def _process_images_thread(self):
        """Behandla alla bilder i bakgrunden; UI uppdateras via _ui()."""
        # Ta en snapshot så att listan kan ändras (t.ex. via radering) utan att tråden
        # får inkonsekventa index. (Radering är dock blockerad via is_processing.)
        files_snapshot = list(self.files_to_process)
        total = len(files_snapshot)
        max_width = self.max_width_var.get()

        def _finish():
            self.progress_var.set(100)
            self.button_canvas.itemconfig(self.button_bg, fill="#4CAF50", outline="#4CAF50")
            self.button_canvas.itemconfig(
                self.button_text_id,
                text=f"DONE! {total} {'image' if total == 1 else 'images'} saved",
            )
            self.is_processing = False
            self.button_canvas.bind("<Button-1>", lambda e: self.start_processing())
            self.button_canvas.bind("<Enter>", lambda e: self.button_canvas.config(cursor="pointinghand"))

        self._ui(lambda: self.progress_var.set(0))

        try:
            for idx, file_path in enumerate(files_snapshot, 1):
                try:
                    self._ui(
                        lambda i=idx, t=total: self.button_canvas.itemconfig(
                            self.button_text_id,
                            text=f"Working (Image {i} of {t})",
                        )
                    )
                    self.process_single_image(file_path, max_width)
                    pct = (idx / total) * 100 if total else 100
                    self._ui(lambda p=pct: self.progress_var.set(p))
                except Exception as e:
                    print(f"Error while processing {file_path}: {e}")
        finally:
            # Säkerställ att vi återställer is_processing även om något oväntat händer.
            self._ui(_finish)

    def process_single_image(self, input_path, max_width):
        """Behandla en enskild bild med intelligent orientering-baserad skalning"""
        input_path = Path(input_path)

        with Image.open(input_path) as img:
            width, height = img.size
            aspect_ratio = width / height
            is_portrait = height > width

            print(
                f"Bild: {input_path.name} - {width}x{height} - Ratio: {aspect_ratio:.2f} - "
                f"{'Portrait' if is_portrait else 'Landscape'}"
            )

        source = tinify.from_file(str(input_path))

        if is_portrait:
            if height > max_width:
                resized = source.resize(method="scale", height=max_width)
                print(f"  → Portrait skalad till höjd {max_width}px")
            else:
                resized = source
                print("  → Ingen skalning behövs")
        else:
            if width > max_width:
                resized = source.resize(method="scale", width=max_width)
                print(f"  → Landscape skalad till bredd {max_width}px")
            else:
                resized = source
                print("  → Ingen skalning behövs")

        converted = resized.convert(type="image/webp")

        if self.output_dir:
            output_path = Path(self.output_dir) / f"{input_path.stem}.webp"
        else:
            output_path = input_path.parent / f"{input_path.stem}.webp"

        converted.to_file(str(output_path))

        print(f"Sparad: {output_path}")
        return output_path

    def _add_files_to_list(self, paths):
        """Lägg till unika bildvägar; konvertering sker först vid grön knapp."""
        image_ext = ('.jpg', '.jpeg', '.png')
        added = 0
        for p in paths:
            if not p.lower().endswith(image_ext):
                continue
            if p not in self.files_to_process:
                self.files_to_process.append(p)
                added += 1
        if added:
            self.update_file_list()
            self.button_canvas.itemconfig(self.button_text_id, text="Optimize images!")

    def _expand_dropped_paths(self, paths):
        """Utöka sökvägar till enskilda bildfiler (inkl. mappar med JPG/PNG)."""
        expanded = []
        for p in paths:
            path = Path(p)
            if not path.exists():
                continue
            if path.is_file():
                expanded.append(str(path.resolve()))
            elif path.is_dir():
                for pat in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
                    expanded.extend(str(x.resolve()) for x in sorted(path.glob(pat)))
        return expanded

    def on_drop(self, event):
        """Hantera drag-and-drop av filer"""
        files = self.parse_drop_files(event.data)
        expanded = self._expand_dropped_paths(files)

        image_files = [f for f in expanded if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

        if image_files:
            self._add_files_to_list(image_files)
        elif files:
            messagebox.showwarning("No image files", "Drag and drop only JPG/PNG files or a folder containing such files")

    def parse_drop_files(self, data):
        """Parsar filvägar från drag-and-drop data"""
        files = []

        if isinstance(data, str):
            data = data.strip()
            matches = re.findall(r'\{([^}]+)\}', data)
            if matches:
                files = matches
            else:
                files = [f.strip() for f in data.split() if f.strip()]
        elif isinstance(data, (list, tuple)):
            files = list(data)

        valid_files = []
        for file_path in files:
            path = Path(file_path)
            if path.exists() and (path.is_file() or path.is_dir()):
                valid_files.append(str(path))

        return valid_files
