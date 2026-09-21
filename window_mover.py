# nuitka-project: --mode=onefile
# nuitka-project: --windows-console-mode=disable
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project: --product-name="Window Mover"
# nuitka-project: --product-version="1.0.0.0"
# nuitka-project: --file-description="Window Mover"

import customtkinter as ctk
import io, base64, json, ctypes
from ctypes import wintypes

from PIL import ImageGrab, Image

# 0. lade user32
user32 = ctypes.WinDLL('user32', use_last_error=True)

# 1. DPI-Awareness setzen,
user32.SetProcessDPIAware()  # Verhindert Skalierungsfehler bei der Positionierung

# 2. Funktions-Prototypen für Typsicherheit definieren
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# EnumWindows
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

# GetWindowTextW
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

# IsWindowVisible
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

# SetWindowPos
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, 
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, 
    wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL

# Config Stuff
config_file = 'config.json'

default_settings = {'Links': 0, 'Oben': 0, 'Breite': 1024, 'Höhe': 800}

def write_config(data: dict[str, int]) -> None:
    ...

def find_windows(search_string: str) -> list[tuple[int, str, tuple[int, int, int, int]]]:
    """Durchsucht alle sichtbaren Fenster nach einem Teilstring im Titel."""
    found_windows = []
    
    def enum_callback(hwnd, lparam):
        # Nur Fenster prüfen, die für den Nutzer sichtbar sind
        if user32.IsWindowVisible(hwnd):
            # Puffer für den Fenstertitel erstellen (max 512 Zeichen)
            buffer_length = 512
            buffer = ctypes.create_unicode_buffer(buffer_length)
            
            # Text auslesen
            user32.GetWindowTextW(hwnd, buffer, buffer_length)
            window_title = buffer.value

            # Koordinaten auslesen
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.pointer(rect))
            coords = (rect.left, rect.top, rect.right, rect.bottom)

            # Falls Suchbegriff im Titel existiert, Handle, Titel und Koordinaten speichern
            if search_string.lower() in window_title.lower() and coords[0] > 0:
                found_windows.append((hwnd, window_title, coords))
                
        return True # Weiteres Suchen erlauben
        
    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
    return sorted(found_windows)

def move_windows(hwnd: int, coordinates: dict[str, int]) -> bool:
    """ hwnd = Fenster Handle
        coordinates = {'Links': int, 'Oben': int, 'Breite': int, 'Höhe': int}
        success = 1 wenn erfolgreich
        success = 0 wenn Fehler
    """
    HWND_TOP = 0
    SWP_SHOWWINDOW = 0x0040

    success = user32.SetWindowPos(
        hwnd,
        HWND_TOP,
        coordinates.get('Links'),
        coordinates.get('Oben'),
        coordinates.get('Breite'),
        coordinates.get('Höhe'),
        SWP_SHOWWINDOW)

    return success

def get_screen_resolution() -> tuple[int, int]:
    screen_breite = user32.GetSystemMetrics(0)
    screen_höhe = user32.GetSystemMetrics(1)
    return (screen_breite, screen_höhe)

def read_config() -> dict[str, int]:
    try:
        with open(config_file, 'r', encoding='UTF-8') as file:
            return json.load(file)

    except FileNotFoundError:
        return default_settings

def write_config(data: dict):
    try:
        with open(config_file, "w", encoding='UTF-8') as file:
            file.write(json.dumps(data, ensure_ascii=False))
    except IOError:
        pass

def get_screenshot():
    return ImageGrab.grab()


class Main(ctk.CTk):
    def __init__(self, search_string, screenshot):
        super().__init__()

        self.wm_title('Window Mover')
        self.style = {'padx':10, 'pady':5}

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)


        self.settings = read_config()
        self.settings_vars = {}
        
        self.search_string = search_string
        self.clients = []

        self.preview = None

        self.screenshot = screenshot

        # Position Text
        self.text = ctk.CTkLabel(self, text="Position Fenster:")
        self.text.grid(row=0,column=0, sticky='w', **self.style)

        # Clients Text
        self.text = ctk.CTkLabel(self, text="Clients:")
        self.text.grid(row=0,column=1, sticky='w', **self.style)

        # Button reload Clients 
        self.button = ctk.CTkButton(self, text='Clients neu laden', width=20, command=self.reload_button_callback)
        self.button.grid(row=0,column=2, sticky='e', **self.style)



        # Settings Frame
        self.settingsFrame = ctk.CTkFrame(self)
        for row,(name,value) in enumerate(self.settings.items()):
            label = ctk.CTkLabel(self.settingsFrame, text=f'{name}:')
            label.grid(row=row, column=0, **self.style)

            var = ctk.StringVar(self, value=value)
            entry = ctk.CTkEntry(self.settingsFrame, textvariable=var, width=55)
            entry.bind("<Return>", self.on_enter_callback)
            entry.bind("<FocusOut>", self.on_enter_callback)
            entry.grid(row=row, column=1, **self.style)

            # In ein Dictionary speichern, damit wir sie leicht finden können
            self.settings_vars[name] = var
        self.settingsFrame.grid(row=1,column=0, sticky='n', **self.style)



        # Clients Frame
        # self.clientListFrame = ctk.CTkScrollableFrame(self, width=400)
        self.clientListFrame = ctk.CTkScrollableFrame(self, width=400, height=300)

        self.get_clients()

        self.clientListFrame.grid(row=1, column=1, columnspan=2, sticky="nsew", **self.style)



        # Button Vorschau
        self.vorschau = ctk.CTkButton(self, text='Vorschau', command=self.vorschau)
        self.vorschau.grid(row=2,column=0, **self.style)

        # Button verschieben
        self.verschieben = ctk.CTkButton(self, text='selekt. Fenster verschieben', command=self.move_clients, fg_color='red')
        self.verschieben.grid(row=2,column=1, sticky='e', **self.style, columnspan=2)


    def get_clients(self):
        # generiert 
        self.clients = find_windows(self.search_string)

        for row,name in enumerate(self.clients):
            hwnd = name[0]

            txt =  ctk.StringVar(self,
            value = f'Name: {name[1]} | Pos: {name[2][0]} x {name[2][1]} x {name[2][2]-name[2][0]} x {name[2][3]-name[2][1]}')

            var = ctk.BooleanVar()

            checkbox = ctk.CTkCheckBox(
            self.clientListFrame, 
            checkbox_width=18,
            checkbox_height=18,
            border_width=2,
            textvariable = txt,
            variable = var,
            onvalue=hwnd)

            if name[2][3]-name[2][1] <= 410:
                checkbox.configure(text_color='gray')
            checkbox.grid(row=row, **self.style, sticky='W')


    def reload_button_callback(self):
        for checkbox in self.clientListFrame.winfo_children():
            checkbox.destroy()
            
        self.clients = []
        self.get_clients()


    def on_enter_callback(self, event):
        for k in self.settings_vars.keys():
            try:
                self.settings[k] = int(self.settings_vars[k].get())
            except ValueError:
                self.settings_vars[k].set(0)
        if self.preview is None or not self.preview.winfo_exists():
            self.preview = Vorschau(self.settings, self.screenshot)
        else:
            self.preview.gen_image(self.settings)


    def move_clients(self):
        for checkbox in self.clientListFrame.winfo_children():
            if checkbox.get():
                move_windows(checkbox.cget('onvalue'),self.settings)


    def vorschau(self):
        if self.preview is None or not self.preview.winfo_exists():
            self.preview = Vorschau(self.settings, self.screenshot)
        else:
            self.preview.gen_image(self.settings)



class Vorschau(ctk.CTkToplevel):

    def __init__(self, coordinates, screenshot):
        super().__init__()

        self.wm_title('Vorschau')
        #self.wm_attributes('-topmost', True)
        self.style = {'padx':15, 'pady':5}

        self.screen_breite, self.screen_höhe = get_screen_resolution()

        # Images
        self.ss_image = screenshot

        from img_data import data
        self.login_image = Image.open(io.BytesIO(base64.b64decode(data)))


        # skalieren wenn nötig
        if self.screen_breite / self.screen_höhe < 1.8:
            self.login_image = self.login_image.crop((300,0,self.login_image.width-300,self.login_image.height))


        # "<width>x<height>" or "<width>x<height>+<x_pos>+<y_pos>"
        self.geometry(f'{self.screen_breite//4+50}x{self.screen_höhe//4+60}+100+600')

        # erzeuge CTkLabel Object ohne Bild
        self.label = ctk.CTkLabel(self, width=self.screen_breite//4, height=self.screen_höhe//4, text='')
        self.gen_image(coordinates)
        self.label.pack(**self.style)

        # Button Schliessen
        button_close = ctk.CTkButton(self, text='Fenster schließen', command=self.destroy)
        button_close.pack(**self.style)

    # erzeuge Bild und update CTkLabel Object mit Bild
    def gen_image(self, coordinates):
        ratio = coordinates.get('Breite') / coordinates.get('Höhe')

        login_image = self.login_image.copy()

        if ratio < 1.8:
            login_image = login_image.crop((300,0,login_image.width-300,login_image.height))
        login_image = login_image.resize([coordinates.get('Breite'), coordinates.get('Höhe')])

        ss_image = self.ss_image.copy()
        ss_image.paste(login_image, [coordinates.get('Links'), coordinates.get('Oben')])

        ctk_image = ctk.CTkImage(ss_image, size= [self.screen_breite//4, self.screen_höhe//4])
        self.label.configure(image=ctk_image)
        

# App = Main('Eve ')

ss_img = get_screenshot()

App = Main('Eve', ss_img)
App.mainloop()

try:
    write_config(App.settings)
except IOError:
    pass