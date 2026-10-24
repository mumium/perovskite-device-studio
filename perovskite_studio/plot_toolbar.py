"""Compact themed Matplotlib tools with the original navigation behaviour."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

from .theme import COLORS


class _ToolToggle(ttk.Checkbutton):
    def select(self):
        self.var.set(1)

    def deselect(self):
        self.var.set(0)


class PlotToolbar(NavigationToolbar2Tk):
    def __init__(self, canvas, window=None, **kwargs):
        super().__init__(canvas, window, **kwargs)
        self.configure(background=COLORS['surface'], borderwidth=0, height=38)
        for child in self.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(background=COLORS['surface'], foreground=COLORS['secondary'])

    def _Button(self, text, image_file, toggle, command):
        if toggle:
            var = tk.IntVar(master=self)
            button = _ToolToggle(self, text=text, variable=var, command=command, style='Plot.TCheckbutton')
            button.var = var
        else:
            button = ttk.Button(self, text=text, command=command, style='Plot.TButton')
        button._image_file = image_file
        self._set_tool_image(button)
        button.pack(side='left', padx=1, pady=2)
        return button

    def _set_tool_image(self, button):
        path = Path(button._image_file) if button._image_file else None
        if path is None:
            return
        size = max(18, button.winfo_pixels('15p'))
        large = path.with_name(path.stem+'_large'+path.suffix)
        with Image.open(large if large.exists() else path) as source:
            icon = source.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
        # Use one neutral ink for the icon, retaining the source alpha mask.
        color = Image.new('RGBA', icon.size, COLORS['secondary'])
        color.putalpha(icon.getchannel('A'))
        button._ntimage = ImageTk.PhotoImage(color, master=self)
        disabled = Image.new('RGBA', icon.size, COLORS['disabled_text'])
        disabled.putalpha(icon.getchannel('A'))
        button._disabled_image = ImageTk.PhotoImage(disabled, master=self)
        button.configure(image=(button._ntimage, 'disabled', button._disabled_image))

    def _Spacer(self):
        spacer = ttk.Separator(self, orient='vertical')
        spacer.pack(side='left', fill='y', padx=6, pady=9)
        return spacer

    def _rescale(self):
        for button in self._buttons.values():
            self._set_tool_image(button)
        self._label_font.configure(size=9)
        self.configure(height=max(34, self.winfo_pixels('26p')))
