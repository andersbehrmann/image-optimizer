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
        """Skapa alla GUI-komponenter"""
        # Header
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill=tk.X)

        title_label = ttk.Label(
            header_frame,
            text="Image Optimizer",
            font=("Helvetica", 18, "bold")
        )
        title_label.pack()

        subtitle_label = ttk.Label(
            header_frame,
            text="Skala ner, konvertera till WebP och komprimera dina bilder",
            font=("Helvetica", 10)
        )
        subtitle_label.pack()

        # Huvudlayout: Två kolumner
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)

        # VÄNSTER KOLUMN: Fillista
        left_column = ttk.Frame(main_container)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Knappar ovanför fillistan
        btn_frame = ttk.Frame(left_column)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        select_btn = ttk.Button(btn_frame, text="Välj bilder", command=self.select_files)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))

        clear_btn = ttk.Button(btn_frame, text="Rensa lista", command=self.clear_files)
        clear_btn.pack(side=tk.LEFT)

        # Stor yta för lista + drag-n-drop (tk.Frame behövs för tkinterdnd2)
        self.drop_zone = tk.Frame(
            left_column,
            bg='#e8e8e8',
            highlightthickness=1,
            highlightbackground='#999999',
        )
        self.drop_zone.pack(fill=tk.BOTH, expand=True)

        self.drop_hint = tk.Label(
            self.drop_zone,
            text=(
                "Släpp JPG/PNG här eller välj med \"Välj bilder\". "
                "Du kan också släppa filer på app-ikonen. "
                "Klicka på den gröna knappen när du vill optimera."
            ),
            bg='#e8e8e8',
            fg='#444444',
            font=('Helvetica', 10),
            wraplength=340,
            justify=tk.LEFT,
        )
        self.drop_hint.pack(fill=tk.X, padx=8, pady=(8, 4))

        list_row = tk.Frame(self.drop_zone, bg='#e8e8e8')
        list_row.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 8))

        scrollbar = ttk.Scrollbar(list_row)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(
            list_row,
            yscrollcommand=scrollbar.set,
            background='#f5f5f5',
            selectmode=tk.EXTENDED,
        )
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # Tangentbordsradering av markerade rader.
        self.file_listbox.bind("<KeyPress-BackSpace>", self.delete_selected_files)
        self.file_listbox.bind("<KeyPress-Delete>", self.delete_selected_files)

        # Drag and drop på hela zonen + listan (tkinterdnd2)
        try:
            self.setup_drag_drop()
        except Exception as e:
            print(f"Drag-and-drop init misslyckades: {e}")
            messagebox.showwarning(
                "Drag-and-drop",
                f"Kunne inte initiera drag-and-drop-funktion:\n{e}"
            )

        self.file_listbox.bind('<Enter>', lambda e: self.file_listbox.config(background="#e8f4f8"))
        self.file_listbox.bind('<Leave>', lambda e: self.file_listbox.config(background="#f5f5f5"))

        # HÖGER KOLUMN: Inställningar
        right_column = ttk.LabelFrame(main_container, text="Inställningar", padding="10")
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))

        # API-nyckel
        api_label = ttk.Label(right_column, text="TinyPNG API-nyckel")
        api_label.pack(anchor=tk.W, pady=(0, 5))

        self.api_key_var = tk.StringVar(value=self.api_key or "")
        api_entry = ttk.Entry(right_column, textvariable=self.api_key_var, show="*", width=30)
        api_entry.pack(fill=tk.X, pady=(0, 2))

        save_key_btn = ttk.Button(right_column, text="Spara nyckel", command=self.on_save_api_key)
        save_key_btn.pack(fill=tk.X, pady=(0, 15))

        # Max bredd
        width_label = ttk.Label(right_column, text="Max bildstorlek (px):")
        width_label.pack(anchor=tk.W, pady=(0, 5))

        self.max_width_var = tk.IntVar(value=1920)
        width_entry = ttk.Entry(right_column, textvariable=self.max_width_var, width=10)
        width_entry.pack(fill=tk.X, pady=(0, 15))

        # Output-mapp
        output_label = ttk.Label(right_column, text="Spara optimerade bilder i")
        output_label.pack(anchor=tk.W, pady=(0, 5))

        self.output_label = ttk.Label(
            right_column,
            text="Ingen mapp vald\n(sparas bredvid originalfiler)",
            foreground="gray",
            font=('Helvetica', 9)
        )
        self.output_label.pack(fill=tk.X, pady=(0, 5))

        select_output_btn = ttk.Button(right_column, text="Välj mapp", command=self.select_output_dir)
        select_output_btn.pack(fill=tk.X, pady=(0, 20))

        # Stor knapp längst ner med Canvas för att få färg på macOS
        button_frame = tk.Frame(right_column)
        button_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.button_canvas = tk.Canvas(button_frame, height=80, highlightthickness=0)
        self.button_canvas.pack(fill=tk.BOTH, expand=True)

        self.button_bg = self.button_canvas.create_rectangle(
            0, 0, 1000, 100, fill="#4CAF50", outline="#4CAF50", width=0
        )

        self.button_text_id = self.button_canvas.create_text(
            500, 40, text="Optimera bilder!",
            font=("Arial", 18, "bold"), fill="white"
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

            for w in (self.drop_zone, self.drop_hint, self.file_listbox):
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
