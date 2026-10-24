"""Small-screen Tk scrolling without process-wide event bindings."""
import tkinter as tk
from tkinter import ttk


def active_grading_inputs(variables):
    independent = variables['affinity_mode'].get() == '独立端点'
    return {**{key+'_end': variables[key+'_mode'].get() != '均匀'
               for key in ('Eg', 'Nd', 'Na')},
            'chi_end': independent,
            'band_fraction': not independent and variables['Eg_mode'].get() != '均匀'}


def refresh_combobox_on_map(event):
    """Reattach hidden-tab text after native geometry settles, without writes."""
    widget = event.widget
    def refresh():
        if widget.winfo_exists() and widget.winfo_ismapped():
            variable = widget.cget('textvariable')
            if variable:
                widget.configure(textvariable=variable)
            widget.xview_moveto(0)
    widget.after_idle(refresh)


def configure_theme(root):
    from .theme import configure_macos_theme, configure_plot_style
    style = configure_macos_theme(root)
    configure_plot_style()
    root.bind_class('TCombobox', '<Map>', refresh_combobox_on_map, add='+')
    return style


class FlowToolbar(ttk.Frame):
    """Left-aligned controls that wrap together when a window becomes narrow."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.items = []
        self.bind('<Configure>', self._layout)

    def add(self, widget):
        self.items.append(widget)
        self.after_idle(self._layout)
        return widget

    def button(self, text, command, **kwargs):
        return self.add(ttk.Button(self, text=text, command=command, **kwargs))

    def menu(self, text, commands, **kwargs):
        button = ttk.Menubutton(self, text=text, **kwargs)
        menu = tk.Menu(button, tearoff=False)
        for label, command in commands:
            menu.add_command(label=label, command=command)
        button.configure(menu=menu)
        return self.add(button)

    def _layout(self, event=None):
        if not self.winfo_exists():
            return
        available = max(1, self.winfo_width())
        row = col = used = 0
        for widget in self.items:
            width = widget.winfo_reqwidth()+6
            if used and used+width > available:
                row += 1
                col = used = 0
            widget.grid(row=row, column=col, padx=(0, 6), pady=2, sticky='w')
            col += 1
            used += width


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, width=340, height=180, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, width=width, height=height, background='#ffffff')
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.content = ttk.Frame(self.canvas, padding=4)
        self.window = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self.content.bind('<Configure>', self._content_changed)
        self.canvas.bind('<Configure>', self._resized)

    def _content_changed(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self._bind_wheel(self.content)

    def _resized(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def _bind_wheel(self, widget):
        if getattr(widget, '_scroll_owner', None) is not self:
            widget.bind('<MouseWheel>', self._wheel, add='+')
            widget._scroll_owner = self
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _wheel(self, event):
        if self.canvas.yview() != (0., 1.):
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'
