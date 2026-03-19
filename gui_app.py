"""
GUI för Image Optimizer (Tkinter + tkinterdnd2).
Laddas lazy från main.py så py2app/byggverktyg kan importera main utan Tk.
"""

import json
import re
import sys
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
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
        self.create_widgets()

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
        """Skapa alla GUI-komponenter (v2-layout enligt illustration)."""
        # Bas-layout / storlek
        self.root.geometry("1050x640")

        outer = ttk.Frame(self.root, padding="18")
        outer.pack(fill=tk.BOTH, expand=True)

        # Översta illustration
        illustration_frame = ttk.Frame(outer)
        illustration_frame.pack(fill=tk.X, pady=(0, 14))

        illustration_loaded = False
        try:
            ill_path = self._bundle_dir() / "illustration.png"
            if ill_path.exists():
                img = Image.open(ill_path)
                # Skala proportionellt (max bredd enligt design).
                max_w = 760
                if img.width > max_w:
                    new_h = int(img.height * (max_w / img.width))
                    img = img.resize((max_w, new_h), Image.LANCZOS)
                self._illustration_imgtk = ImageTk.PhotoImage(img)

                ill_label = ttk.Label(illustration_frame, image=self._illustration_imgtk)
                ill_label.pack()
                illustration_loaded = True
        except Exception as e:
            print(f"Kunde inte ladda illustration.png: {e}")

        if not illustration_loaded:
            ttk.Label(illustration_frame, text="Image Optimizer", font=("Helvetica", 18, "bold")).pack()

        # Två kolumner + bottenknapp
        columns_frame = ttk.Frame(outer)
        columns_frame.pack(fill=tk.BOTH, expand=True)
        columns_frame.columnconfigure(0, weight=1)
        columns_frame.columnconfigure(1, weight=1)
        columns_frame.rowconfigure(0, weight=1)

        left_card = tk.Frame(
            columns_frame,
            bg="white",
            highlightthickness=1,
            highlightbackground="#E5E7EB",
        )
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        right_card = tk.Frame(
            columns_frame,
            bg="white",
            highlightthickness=1,
            highlightbackground="#E5E7EB",
        )
        right_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # --- Left card ---
        left_card_inner = ttk.Frame(left_card, padding="16")
        left_card_inner.pack(fill=tk.BOTH, expand=True)

        btn_row = ttk.Frame(left_card_inner)
        btn_row.pack(fill=tk.X, pady=(0, 12))

        select_btn = tk.Button(
            btn_row,
            text="+  Välj bilder",
            bg="#22c55e",
            fg="white",
            activebackground="#16a34a",
            relief="flat",
            padx=14,
            pady=8,
            font=("Helvetica", 11, "bold"),
            command=self.select_files,
        )
        select_btn.pack(side=tk.LEFT)

        clear_btn = tk.Button(
            btn_row,
            text="Rensa lista",
            bg="#F3F4F6",
            fg="#6B7280",
            activebackground="#E5E7EB",
            relief="flat",
            padx=14,
            pady=8,
            font=("Helvetica", 11, "bold"),
            command=self.clear_files,
        )
        clear_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Drag-n-drop dashed area
        self.drop_frame = tk.Frame(left_card_inner, bg="#F9FAFB", highlightthickness=1, highlightbackground="#D1D5DB")
        self.drop_frame.pack(fill=tk.X, pady=(0, 12))

        # Canvas gör det enkelt att få dashed outline
        self.drop_canvas = tk.Canvas(self.drop_frame, height=150, bg="#F9FAFB", highlightthickness=0)
        self.drop_canvas.pack(fill=tk.X, expand=True)

        self._drop_rect_id = None
        self._drop_text_id = None

        def _redraw_drop_border(_=None):
            self.drop_canvas.delete("drop_border")
            w = max(self.drop_canvas.winfo_width(), 1)
            h = max(self.drop_canvas.winfo_height(), 1)
            pad = 12
            self.drop_canvas.create_rectangle(
                pad,
                pad,
                w - pad,
                h - pad,
                dash=(6, 6),
                outline="#9CA3AF",
                width=2,
                tags=("drop_border",),
            )
            self.drop_canvas.create_text(
                w / 2,
                h / 2,
                text="Drag in images\nto convert to WebP",
                fill="#6B7280",
                font=("Helvetica", 11, "bold"),
                justify="center",
                tags=("drop_text",),
            )

        self.drop_canvas.bind("<Configure>", _redraw_drop_border)
        _redraw_drop_border()

        # List-container (ska döljas när tomt)
        self.list_container = tk.Frame(left_card_inner, bg="white")
        self.list_container.pack_forget()

        list_row = tk.Frame(self.list_container, bg="white")
        list_row.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_row)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(
            list_row,
            yscrollcommand=scrollbar.set,
            background="#F9FAFB",
            selectmode=tk.EXTENDED,
            activestyle="dotbox",
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # Tangentbordsradering av markerade rader.
        self.file_listbox.bind("<KeyPress-BackSpace>", self.delete_selected_files)
        self.file_listbox.bind("<KeyPress-Delete>", self.delete_selected_files)
        self.file_listbox.bind("<Enter>", lambda e: self.file_listbox.config(background="#E8F4FF"))
        self.file_listbox.bind("<Leave>", lambda e: self.file_listbox.config(background="#F9FAFB"))

        # Drag and drop (registeras efter att widgets finns)
        try:
            self.setup_drag_drop()
        except Exception as e:
            print(f"Drag-and-drop init misslyckades: {e}")
            messagebox.showwarning("Drag-and-drop", f"Kunne inte initiera drag-and-drop:\n{e}")

        # --- Right card: Inställningar ---
        right_card_inner = ttk.Frame(right_card, padding="16")
        right_card_inner.pack(fill=tk.BOTH, expand=True)

        settings_title = ttk.Label(right_card_inner, text="Inställningar", font=("Helvetica", 14, "bold"))
        settings_title.pack(anchor=tk.W)

        sep1 = ttk.Separator(right_card_inner)
        sep1.pack(fill=tk.X, pady=12)

        api_label = ttk.Label(right_card_inner, text="TinyPNG API-nyckel")
        api_label.pack(anchor=tk.W, pady=(0, 6))

        self.api_key_var = tk.StringVar(value=self.api_key or "")
        api_entry = ttk.Entry(right_card_inner, textvariable=self.api_key_var, show="*", width=30)
        api_entry.pack(fill=tk.X)

        save_key_btn = ttk.Button(right_card_inner, text="Spara nyckel", command=self.on_save_api_key)
        save_key_btn.pack(fill=tk.X, pady=(10, 18))

        width_label = ttk.Label(right_card_inner, text="Max bildstorlek (px):")
        width_label.pack(anchor=tk.W, pady=(0, 6))

        self.max_width_var = tk.IntVar(value=1920)
        width_entry = ttk.Entry(right_card_inner, textvariable=self.max_width_var, width=10)
        width_entry.pack(anchor=tk.W, pady=(0, 18))

        output_label = ttk.Label(right_card_inner, text="Spara optimerade bilder i")
        output_label.pack(anchor=tk.W, pady=(0, 6))

        self.output_label = ttk.Label(
            right_card_inner,
            text="Ingen mapp vald\n(sparas bredvid originalfiler)",
            foreground="gray",
            font=("Helvetica", 9),
        )
        self.output_label.pack(fill=tk.X, pady=(0, 10))

        select_output_btn = ttk.Button(right_card_inner, text="Välj mapp", command=self.select_output_dir)
        select_output_btn.pack(fill=tk.X, pady=(0, 18))

        # Primärknapp längst ner (spänner över hela appen)
        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X, pady=(16, 0))

        self.button_canvas = tk.Canvas(bottom, height=74, highlightthickness=0)
        self.button_canvas.pack(fill=tk.X)

        self.button_bg = self.button_canvas.create_rectangle(
            0, 0, 1000, 100, fill="#4CAF50", outline="#4CAF50", width=0
        )
        self.button_text_id = self.button_canvas.create_text(
            500, 37, text="Optimera bilder!",
            font=("Arial", 20, "bold"), fill="white"
        )
        self.button_canvas.bind("<Button-1>", lambda e: self.start_processing())
        self.button_canvas.bind("<Enter>", lambda e: self.button_canvas.config(cursor="pointinghand"))
        self.button_canvas.bind("<Leave>", lambda e: self.button_canvas.config(cursor=""))

        def resize_canvas(event):
            width = event.width
            height = event.height
            self.button_canvas.coords(self.button_bg, 0, 0, width, height)
            self.button_canvas.coords(self.button_text_id, width / 2, height / 2)

        self.button_canvas.bind("<Configure>", resize_canvas)

        self.progress_var = tk.DoubleVar()

    def setup_drag_drop(self):
        """Konfigurera drag-and-drop (försöker med tkinterdnd2 om tillgänglig)"""
        try:
            from tkinterdnd2 import DND_FILES

            for w in (self.drop_frame, self.drop_canvas, self.file_listbox):
                w.drop_target_register(DND_FILES)
                w.dnd_bind('<<Drop>>', self.on_drop)
            print("Drag-and-drop aktiverat med tkinterdnd2 (drop-zon + lista)")
        except ImportError:
            print("tkinterdnd2 inte installerat - drag-and-drop begränsad")
            self.root.bind('<Enter>', lambda e: self.root.focus_force())

    def on_save_api_key(self):
        """Spara API-nyckel"""
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Varning", "Ange en API-nyckel först")
            return

        if self.save_api_key(api_key):
            self.api_key = api_key
            tinify.key = api_key
            messagebox.showinfo("Sparad", "API-nyckel sparad!")

    def select_files(self):
        """Välj bildfiler"""
        files = filedialog.askopenfilenames(
            title="Välj bilder",
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
        """Rensa fillistan"""
        self.files_to_process = []
        self.update_file_list()
        self.button_canvas.itemconfig(self.button_text_id, text="Optimera bilder!")

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
        self.button_canvas.itemconfig(self.button_text_id, text="Optimera bilder!")

        return "break"

    def update_file_list(self):
        """Uppdatera listboxen med filer"""
        self.file_listbox.delete(0, tk.END)
        for file_path in self.files_to_process:
            self.file_listbox.insert(tk.END, Path(file_path).name)

        if self.files_to_process:
            # Visa listan när det finns filer.
            if not self.list_container.winfo_ismapped():
                self.list_container.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
            # Döljer placeholder-texten i dropytan när listan inte är tom.
            try:
                self.drop_canvas.itemconfigure("drop_text", state="hidden")
            except Exception:
                pass
        else:
            # Döljer listan i tomt läge (design: endast dashed drag-yta).
            if self.list_container.winfo_ismapped():
                self.list_container.pack_forget()
            try:
                self.drop_canvas.itemconfigure("drop_text", state="normal")
            except Exception:
                pass

    def select_output_dir(self):
        """Välj output-mapp"""
        directory = filedialog.askdirectory(title="Välj mapp för optimerade bilder")
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
                "API-nyckel saknas",
                "Ange din TinyPNG API-nyckel först"
            )
            return

        if not self.files_to_process:
            messagebox.showwarning("Inga filer", "Välj minst en bildfil först")
            return

        try:
            tinify.key = self.api_key
            tinify.validate()
        except tinify.Error as e:
            messagebox.showerror(
                "API-nyckel ogiltig",
                f"TinyPNG API-nyckeln fungerar inte:\n{str(e)}"
            )
            return

        self.is_processing = True

        self.button_canvas.itemconfig(self.button_bg, fill="#FF9800", outline="#FF9800")
        self.button_canvas.itemconfig(self.button_text_id, text="Jobbar...")
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
                text=f"KLAR! {total} {'bild' if total == 1 else 'bilder'} sparade",
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
                            text=f"Jobbar (Bild {i} av {t})",
                        )
                    )
                    self.process_single_image(file_path, max_width)
                    pct = (idx / total) * 100 if total else 100
                    self._ui(lambda p=pct: self.progress_var.set(p))
                except Exception as e:
                    print(f"Fel vid behandling av {file_path}: {e}")
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
            self.button_canvas.itemconfig(self.button_text_id, text="Optimera bilder!")

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
            messagebox.showwarning("Inga bildfiler", "Dra och släpp endast JPG/PNG-filer eller en mapp med sådana filer")

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
