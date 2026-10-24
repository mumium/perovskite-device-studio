"""macOS-inspired light controls, drawn locally for the Tk desktop interface."""
import tkinter as tk
from tkinter import ttk
from tkinter.font import families

from PIL import Image, ImageDraw, ImageTk


COLORS = dict(window='#f5f5f7', surface='#ffffff', grouped='#e8e8ed',
              text='#1d1d1f', secondary='#6e6e73', muted='#86868b',
              border='#d1d1d6', separator='#e5e5ea', hover='#f0f0f4',
              disabled='#f2f2f7', disabled_text='#aeaeb2',
              blue='#007aff', blue_hover='#0069df', blue_pressed='#0059bd',
              selection='#dbeafe', purple='#af52de', purple_hover='#9945c5',
              orange='#c77700', error='#c9342b')


def _rounded(fill, outline=None, size=(28, 28), radius=7, shadow=False, width=1):
    scale = 3
    w, h = size
    image = Image.new('RGBA', (w*scale, h*scale))
    draw = ImageDraw.Draw(image)
    if shadow:
        draw.rounded_rectangle((scale, 2*scale, (w-1)*scale, (h-1)*scale),
                               radius=radius*scale, fill='#dcdce1')
    draw.rounded_rectangle((scale, scale, (w-1)*scale, (h-2 if shadow else h-1)*scale),
                           radius=radius*scale, fill=fill, outline=outline, width=width*scale)
    return image.resize(size, Image.Resampling.LANCZOS)


def configure_macos_theme(root):
    """Nine-slice assets retain identical geometry in every interaction state."""
    style = ttk.Style(root)
    style.theme_use('clam')
    available = set(families(root))
    family = next((f for f in ('SF Pro Text', 'Microsoft YaHei UI', 'Microsoft YaHei', 'Segoe UI')
                   if f in available), 'TkDefaultFont')
    root.ui_font = family
    root.configure(background=COLORS['window'])
    images = []

    def photo(image):
        result = ImageTk.PhotoImage(image, master=root)
        images.append(result)
        return result

    def element(name, fill, outline=None, states=(), shadow=False, padding=1):
        specs = [(state, photo(_rounded(f, b, shadow=shadow))) for state, f, b in states]
        style.element_create(name, 'image', photo(_rounded(fill, outline, shadow=shadow)),
                             *specs, border=8, padding=padding, sticky='nsew')

    style.configure('.', font=(family, 10), foreground=COLORS['text'],
                    background=COLORS['surface'], bordercolor=COLORS['border'])
    style.configure('TFrame', background=COLORS['surface'])
    style.configure('Toolbar.TFrame', background=COLORS['window'])
    style.configure('TLabel', background=COLORS['surface'])
    style.configure('Secondary.TLabel', foreground=COLORS['secondary'])
    style.configure('TSeparator', background=COLORS['separator'])
    style.configure('TPanedwindow', background=COLORS['separator'])
    style.configure('Sash', sashthickness=5, background=COLORS['separator'])

    element('Mac.Button', COLORS['surface'], COLORS['border'], shadow=True, states=(
        ('disabled', COLORS['disabled'], COLORS['separator']),
        ('pressed', '#e5e5ea', '#b8b8be'), ('focus', COLORS['surface'], COLORS['blue']),
        ('active', COLORS['hover'], '#b8b8be')))
    button_layout = lambda border: [(border, dict(sticky='nsew', children=[
        ('Button.padding', dict(sticky='nsew', children=[('Button.label', dict(sticky='nsew'))]))]))]
    style.layout('TButton', button_layout('Mac.Button'))
    style.configure('TButton', padding=(9, 4), width=0, anchor='center', shiftrelief=0)
    style.map('TButton', foreground=[('disabled', COLORS['disabled_text'])])
    for name, color, hover, pressed in (
            ('Accent.TButton', COLORS['blue'], COLORS['blue_hover'], COLORS['blue_pressed']),
            ('EQE.Accent.TButton', COLORS['purple'], COLORS['purple_hover'], '#8336ac')):
        border = 'Mac.'+name
        element(border, color, states=(('disabled', '#b8cbe3' if color == COLORS['blue'] else '#d5bee2', None),
                                      ('pressed', pressed, None), ('active', hover, None),
                                      ('focus', color, '#004da1' if color == COLORS['blue'] else '#71308e')))
        style.layout(name, button_layout(border))
        style.configure(name, font=(family, 11, 'bold'), foreground='white', padding=(16, 12))
        style.map(name, foreground=[('disabled', '#f7f7fa'), ('!disabled', 'white')])

    # Menus and selectors use the same chevron instead of a separate square arrow.
    arrow = Image.new('RGBA', (20*3, 16*3))
    d = ImageDraw.Draw(arrow)
    d.line([(7*3, 6*3), (10*3, 9*3), (13*3, 6*3)],
           fill=COLORS['secondary'], width=3, joint='curve')
    style.element_create('Mac.Chevron', 'image', photo(arrow.resize((20, 16), Image.Resampling.LANCZOS)),
                         sticky='')
    style.layout('TMenubutton', [('Mac.Button', dict(sticky='nsew', children=[
        ('Menubutton.padding', dict(sticky='nsew', children=[
            ('Mac.Chevron', dict(side='right', sticky='e')),
            ('Menubutton.label', dict(side='left', sticky='nsew'))]))]))])
    style.configure('TMenubutton', padding=(9, 4), width=0, background=COLORS['surface'])
    style.map('TMenubutton', foreground=[('disabled', COLORS['disabled_text'])],
              background=[('disabled', COLORS['disabled']), ('!disabled', COLORS['surface'])])

    element('Mac.Field', COLORS['surface'], COLORS['border'], states=(
        ('disabled', COLORS['disabled'], COLORS['separator']),
        ('focus', COLORS['surface'], COLORS['blue']), ('active', COLORS['surface'], '#aeaeb2')))
    for name, prefix in (('TEntry', 'Entry'), ('TCombobox', 'Combobox')):
        children = [(prefix+'.padding', dict(sticky='nsew', children=[
            (prefix+'.textarea', dict(sticky='nsew'))]))]
        if name == 'TCombobox':
            children.insert(0, ('Mac.Chevron', dict(side='right', sticky='ns')))
        style.layout(name, [('Mac.Field', dict(sticky='nsew', children=children))])
        style.configure(name, padding=(7, 4), foreground=COLORS['text'],
                        fieldbackground=COLORS['surface'], insertcolor=COLORS['text'],
                        selectbackground=COLORS['selection'], selectforeground=COLORS['text'])
        style.map(name, foreground=[('disabled', COLORS['disabled_text'])],
                  fieldbackground=[('disabled', COLORS['disabled']), ('readonly', COLORS['surface'])])

    # Tabs keep their hit boxes when selected, pressed or focused.
    element('Mac.Tab', COLORS['grouped'], states=(
        ('disabled', COLORS['disabled'], None), ('selected', COLORS['surface'], COLORS['border']),
        ('active', '#f0f0f4', None)))
    tabs = [('Mac.Tab', dict(sticky='nsew', children=[('Notebook.padding', dict(sticky='nsew',
            children=[('Notebook.label', dict(sticky='nsew'))]))]))]
    for name in ('TNotebook', 'Main.TNotebook'):
        style.configure(name, background=COLORS['window'], borderwidth=0,
                        tabmargins=(10, 8, 10, 6) if name == 'Main.TNotebook' else (2, 3, 2, 3))
        tab = name+'.Tab'
        padding = (22, 9) if name == 'Main.TNotebook' else (12, 7)
        style.layout(tab, tabs)
        style.configure(tab, padding=padding, font=(family, 12, 'bold') if name == 'Main.TNotebook' else (family, 10),
                        foreground=COLORS['secondary'])
        style.map(tab, padding=[('selected', padding), ('!selected', padding)],
                  expand=[('selected', (0, 0, 0, 0)), ('!selected', (0, 0, 0, 0))],
                  foreground=[('disabled', COLORS['disabled_text']), ('selected', COLORS['text']),
                              ('!selected', COLORS['secondary'])])

    element('Mac.Group', COLORS['surface'], COLORS['separator'])
    style.layout('TLabelframe', [('Mac.Group', dict(sticky='nsew'))])
    style.configure('TLabelframe', background=COLORS['surface'], padding=8)
    style.configure('TLabelframe.Label', foreground=COLORS['secondary'],
                    background=COLORS['surface'], font=(family, 9))

    def indicator(selected=False, disabled=False, radio=False):
        im = Image.new('RGBA', (54, 54))
        draw = ImageDraw.Draw(im)
        fill = '#b8cbe3' if selected and disabled else COLORS['blue'] if selected else COLORS['disabled'] if disabled else 'white'
        shape = draw.ellipse if radio else draw.rounded_rectangle
        kwargs = dict(fill=fill, outline=fill if selected else COLORS['border'], width=3)
        if not radio:
            kwargs['radius'] = 4*3
        shape((3, 3, 48, 48), **kwargs)
        if selected:
            if radio:
                draw.ellipse((18, 18, 33, 33), fill='white')
            else:
                draw.line([(13, 26), (22, 34), (38, 17)], fill='white', width=5, joint='curve')
        return photo(im.resize((18, 18), Image.Resampling.LANCZOS))

    for name, radio in (('TCheckbutton', False), ('TRadiobutton', True)):
        prefix = 'Checkbutton' if not radio else 'Radiobutton'
        custom = 'Mac.'+prefix
        style.element_create(custom, 'image', indicator(radio=radio),
                             ('disabled', 'selected', indicator(True, True, radio)),
                             ('disabled', indicator(False, True, radio)),
                             ('selected', indicator(True, radio=radio)), sticky='')
        style.layout(name, [(prefix+'.padding', dict(sticky='nsew', children=[
            (custom, dict(side='left', sticky='w')), (prefix+'.focus', dict(side='left', sticky='nsew',
                children=[(prefix+'.label', dict(sticky='nsew'))]))]))])
        style.configure(name, background=COLORS['surface'], padding=(2, 3), focuscolor=COLORS['blue'])
        style.map(name, foreground=[('disabled', COLORS['disabled_text'])],
                  background=[('active', COLORS['surface'])])

    for orientation in ('Vertical', 'Horizontal'):
        size = (12, 28) if orientation == 'Vertical' else (28, 12)
        # ttk's native mouse bindings identify draggable elements by *thumb.
        thumb = 'Mac.'+orientation+'.thumb'
        style.element_create(thumb, 'image', photo(_rounded('#c7c7cc', size=size, radius=5)),
                             ('active', photo(_rounded('#aeaeb2', size=size, radius=5))),
                             ('pressed', photo(_rounded('#8e8e93', size=size, radius=5))), border=5, sticky='nsew')
        style.layout(orientation+'.TScrollbar', [(orientation+'.Scrollbar.trough', dict(sticky='nsew',
            children=[(thumb, dict(sticky='ns' if orientation == 'Vertical' else 'ew',
                                  expand=True))]))])
        style.configure(orientation+'.TScrollbar', background=COLORS['window'],
                        troughcolor=COLORS['window'], borderwidth=0, arrowsize=12)
    style.configure('Horizontal.TProgressbar', background=COLORS['blue'], troughcolor=COLORS['separator'],
                    borderwidth=0, lightcolor=COLORS['blue'], darkcolor=COLORS['blue'], thickness=6)

    # Toolbar toggles have the same footprint as toolbar buttons.
    element('Mac.PlotButton', COLORS['surface'], states=(('disabled', COLORS['surface'], None),
        ('selected', COLORS['selection'], '#bfdbfe'), ('pressed', '#bfdbfe', None),
        ('active', COLORS['hover'], None), ('focus', COLORS['hover'], COLORS['blue'])))
    style.layout('Plot.TButton', button_layout('Mac.PlotButton'))
    style.layout('Plot.TCheckbutton', button_layout('Mac.PlotButton'))
    style.configure('Plot.TButton', padding=4)
    style.configure('Plot.TCheckbutton', padding=4)

    for key, value in dict(background=COLORS['surface'], foreground=COLORS['text'],
                           activeBackground=COLORS['selection'], activeForeground=COLORS['text'],
                           selectBackground=COLORS['selection'], selectForeground=COLORS['text'],
                           relief='flat', borderWidth=1).items():
        root.option_add('*TCombobox*Listbox.'+key, value)
    for key, value in dict(background=COLORS['surface'], foreground=COLORS['text'],
                           activeBackground=COLORS['selection'], activeForeground=COLORS['text'],
                           disabledForeground=COLORS['disabled_text'], relief='flat', borderWidth=1,
                           font=(family, 10), tearOff=False).items():
        root.option_add('*Menu.'+key, value)
    root._style_images = images
    return style


def configure_plot_style():
    from matplotlib import rcParams
    rcParams.update({'figure.facecolor': COLORS['surface'], 'axes.facecolor': COLORS['surface'],
                     'axes.edgecolor': COLORS['border'], 'axes.labelcolor': COLORS['text'],
                     'text.color': COLORS['text'], 'xtick.color': COLORS['secondary'],
                     'ytick.color': COLORS['secondary'], 'grid.color': COLORS['separator'],
                     'grid.linewidth': .7, 'axes.spines.top': False, 'axes.spines.right': False,
                     'legend.edgecolor': COLORS['separator'], 'legend.facecolor': COLORS['surface'],
                     'legend.framealpha': .95, 'axes.titleweight': 'normal'})


def style_layer_list(widget):
    widget.configure(background=COLORS['surface'], foreground=COLORS['text'],
                     selectbackground=COLORS['selection'], selectforeground=COLORS['text'],
                     highlightbackground=COLORS['separator'], highlightcolor=COLORS['blue'],
                     activestyle='none', borderwidth=0)
