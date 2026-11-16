"""Editable, independent two-terminal tandem workspace."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np

from .performance_page import PerformancePage
from .performance import SimulationCancelled, ENGINE_VERSION
from .device_structure import STRUCTURES_DIR
from .ui_helpers import FlowToolbar, ScrollableFrame
from .tandem import (MODEL, DEFAULTS, MODES, auto_partition, parameters,
                     run_tandem, run_tandem_eqe)


EXAMPLE = '2026-11-16_2T叠层_380nm_20n_20p_780nm.json'
VIEWS = ['J–V 曲线', '子电池参数', '电流匹配', '连接损失', '入射光谱', '光生分布', 'EQE']


def json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def curve_table(result, view):
    """Export the displayed successful snapshot, never the current form."""
    if view == 'EQE':
        keys = ['wavelength_nm', 'EQE', 'top_EQE', 'bottom_EQE',
                'junction_absorptance', 'numerical_error_estimate']
        names = ['wavelength_nm', 'terminal_differential_EQE_fraction', 'top_operating_EQE_fraction',
                 'bottom_operating_EQE_fraction', 'junction_active_absorptance', 'error_estimate_fraction']
    elif view == '光生分布':
        result = result['optics']; keys = ['x_nm', 'G_cm3_s', 'layer_index']
        names = ['x_nm', 'G_cm3_s', 'layer_index_zero_based']
    elif view == '入射光谱':
        return np.asarray(result['optics']['spectrum_nm_W_m2_nm']), 'wavelength_nm,irradiance_W_m2_nm'
    elif view == '子电池参数':
        keys = ['Jsc', 'Voc', 'FF', 'PCE', 'Vmp', 'Jmp', 'Pmax']
        cells = [result['subcells']['top'], result['subcells']['bottom'], result]
        return np.array([[i]+[c['metrics'][k] for k in keys] for i, c in enumerate(cells)]), (
            'cell_0_top_1_bottom_2_tandem,Jsc_mA_cm2,Voc_V,FF_percent,PCE_percent,Vmp_V,Jmp_mA_cm2,Pmax_mW_cm2')
    elif view == '连接损失':
        keys = ['external_voltage', 'series_current', 'external_current', 'top_voltage', 'bottom_voltage',
                'connection_drop', 'top_power', 'bottom_power', 'connection_power', 'series_power',
                'shunt_power', 'output_power', 'power_residual']
        points = result['workpoints']
        names = ['external_voltage_V', 'series_current_mA_cm2', 'external_current_mA_cm2',
                 'top_voltage_V', 'bottom_voltage_V', 'connection_drop_V']+[k+'_mW_cm2' for k in keys[6:]]
        return np.array([[i]+[points[p][k] for k in keys] for i, p in enumerate(['SC', 'MPP', 'OC'])]), (
            'point_0_SC_1_MPP_2_OC,'+','.join(names))
    elif view == '电流匹配':
        result = result['matching']
        keys = ['series_current', 'external_current', 'external_voltage', 'top_voltage', 'bottom_voltage', 'connection_drop']
        names = ['series_current_mA_cm2', 'external_current_mA_cm2', 'external_voltage_V',
                 'top_voltage_V', 'bottom_voltage_V', 'connection_drop_V']
    else:
        m = result['metrics']; n = len(result['voltage'])
        return np.column_stack([result['voltage'], result['current']]+[np.full(n, m[k]) for k in ['Jsc', 'Voc', 'FF', 'PCE']]), (
            'V_terminal_V,J_output_mA_cm2,Jsc_mA_cm2,Voc_V,FF_percent,PCE_percent')
    return np.column_stack([result[k] for k in keys]), ','.join(names)


class TandemPage(PerformancePage):
    def __init__(self, parent, app):
        self.ready = False
        super().__init__(parent, app, tandem=True)
        self.run_button.configure(text='▶ 运行叠层 J–V')
        self.eqe_button.configure(text='▶ 运行叠层 EQE')
        self.plot_choice.configure(values=VIEWS)
        self.mode_badge.set('2T · 多域漂移扩散 · 等效连接')
        self.partition_bar = FlowToolbar(self, padding=(0, 2))
        self.partition_bar.pack(fill='x', before=self.body, pady=(0, 4))
        self.partition_bar.add(ttk.Label(self.partition_bar, text='顶电池末层'))
        self.top_end = ttk.Combobox(self.partition_bar, state='readonly', width=23)
        self.partition_bar.add(self.top_end)
        self.partition_bar.add(ttk.Label(self.partition_bar, text='底电池首层'))
        self.bottom_start = ttk.Combobox(self.partition_bar, state='readonly', width=23)
        self.partition_bar.add(self.bottom_start)
        self.input_widgets.append(self.partition_bar.button('自动分界', self.reset_partition))
        for combo in [self.top_end, self.bottom_start]:
            self.input_widgets.append(combo)
            combo.bind('<<ComboboxSelected>>', lambda e: self.partition_changed())
        self.assignment = tk.StringVar()
        self.partition_bar.add(ttk.Label(self.partition_bar, textvariable=self.assignment, foreground='#6e6e73'))
        scroll = ScrollableFrame(self.settings_tabs, width=560, height=150)
        self.settings_tabs.insert(0, scroll, text='叠层与连接')
        self.settings_tabs.select(scroll)
        self.tandem_vars = {}
        self.connection_entries = {}
        f = scroll.content
        self.automatic_contacts = tk.BooleanVar(value=True)
        check = ttk.Checkbutton(f, text='按带边设置虚拟选择性内接触（假设）', variable=self.automatic_contacts,
                                command=self.connection_changed)
        check.grid(row=0, column=0, columnspan=3, sticky='w', padx=5, pady=4)
        self.input_widgets.append(check)
        fields = [('mode', '连接模型', ''), ('resistance', '连接面积电阻', 'Ω·cm²'),
                  ('j0', '复合结 J0（需标定）', 'mA/cm²'), ('ideality', '复合结理想因子 n', ''),
                  ('junction_collection', '连接区光生收集比例', '0–1'),
                  ('contact_offset', '自动内接触距带边', 'eV'),
                  ('top_work', '顶电池右内接触功函数', 'eV'), ('bottom_work', '底电池左内接触功函数', 'eV'),
                  ('eqe_voltage', '叠层 EQE 外部工作电压', 'V')]
        for row, (key, title, unit) in enumerate(fields, 1):
            ttk.Label(f, text=title).grid(row=row, column=0, sticky='w', padx=5, pady=4)
            var = tk.StringVar(value=MODES['ohmic'] if key == 'mode' else f'{DEFAULTS[key]:g}')
            self.tandem_vars[key] = var
            widget = (ttk.Combobox(f, textvariable=var, values=list(MODES.values()), state='readonly', width=18)
                      if key == 'mode' else ttk.Entry(f, textvariable=var, width=18))
            widget.grid(row=row, column=1, padx=5, sticky='ew')
            ttk.Label(f, text=unit).grid(row=row, column=2, sticky='w')
            self.connection_entries[key] = widget
            self.input_widgets.append(widget)
            var.trace_add('write', self.connection_changed)
        ttk.Label(f, text='分界之间的层属于等效连接区：参与整栈光学，电学由连接模型替代。\n'
                  '子电池内部的体/界面复合保留；跨域界面由连接参数表示，不能由 Nt 自动推算 J0。\n'
                  '理想/电阻模式忽略连接区的光生电压；复合结模式包含其反向光电压。\n'
                  'J0 越大，给定电流的连接压降越小；默认值是演示假设。\n'
                  '子电池扫描自动覆盖短路/开路；光照与扫描页的电压起止不用于串联组合。',
                  foreground='#6e6e73', wraplength=460).grid(row=10, column=0, columnspan=3, padx=5, pady=8, sticky='w')
        self.ready = True
        # A reproducible starter device, not a silent rewrite of the other pages.
        path = STRUCTURES_DIR / EXAMPLE
        if path.exists():
            self.load_document(json.loads(path.read_text(encoding='utf-8')))
        else:
            path = STRUCTURES_DIR / '2026-11-15_串联参考输入_原始能级.json'
            self.load_document(json.loads(path.read_text(encoding='utf-8')))
        self.connection_changed()
        self.plot()
        self.status.set('已打开内置 1.78 / 1.25 eV 叠层示例；请核对分界及连接假设后运行。')

    def update_optical_mode(self, *_):
        super().update_optical_mode()
        if self.ready:
            self.mode_badge.set('2T · 左入射/左阳极 · 等效连接')

    def refresh_list(self):
        super().refresh_list()
        if hasattr(self, 'top_end'):
            a, b = self.top_end.current(), self.bottom_start.current()
            labels = [f'{i+1} · {x["name"]}' for i, x in enumerate(self.layers)]
            self.top_end.configure(values=labels[:-1])
            self.bottom_start.configure(values=labels[1:])
            self.top_end.current(min(max(a, 0), len(labels)-2))
            self.bottom_start.current(min(max(b, 0), len(labels)-2))
            self.update_assignment()

    def update_assignment(self):
        a = self.top_end.current()+1; b = self.bottom_start.current()+1
        self.assignment.set(f'顶 1–{a} · 连接 {b-a} 层 · 底 {b+1}–{len(self.layers)}' if a<=b else '分界顺序无效')

    def reset_partition(self):
        a = auto_partition(self.layers)
        self.top_end.current(a-1); self.bottom_start.current(a-1)
        self.partition_changed()

    def remove(self):
        if len(self.layers)>2:
            super().remove()

    def partition_changed(self):
        self.update_assignment(); self.mark_dirty()

    def connection_changed(self, *_):
        if not self.ready:
            return
        mode = self.tandem_vars['mode'].get()
        for key, widget in self.connection_entries.items():
            enabled = not self.running
            if key in ('j0', 'ideality', 'junction_collection'):
                enabled &= mode == MODES['diode']
            if key == 'resistance':
                enabled &= mode != MODES['ideal']
            if key in ('top_work', 'bottom_work'):
                enabled &= not self.automatic_contacts.get()
            if key == 'contact_offset':
                enabled &= self.automatic_contacts.get()
            widget.configure(state=('readonly' if key == 'mode' else 'normal') if enabled else 'disabled')
        self.mark_dirty()

    def tandem_values(self):
        mode = {v:k for k,v in MODES.items()}[self.tandem_vars['mode'].get()]
        auto = self.automatic_contacts.get()
        inactive = set()
        if mode != 'diode':inactive.update(['j0','ideality','junction_collection'])
        if mode == 'ideal':inactive.add('resistance')
        inactive.update(['top_work','bottom_work'] if auto else ['contact_offset'])
        t = {key: DEFAULTS[key] if key in inactive else float(var.get())
             for key, var in self.tandem_vars.items() if key != 'mode'}
        t.update(mode=mode,
                 automatic_contacts=auto,
                 top_end=self.top_end.current()+1, bottom_start=self.bottom_start.current()+1)
        return t

    def validate_collected(self, layers, settings):
        parameters(layers, settings, self.tandem_values())

    def set_running(self, running):
        super().set_running(running)
        if self.ready:
            # Re-enabling a finished task must not mark unchanged inputs dirty.
            previous = self.loading; self.loading = True
            self.connection_changed(); self.loading = previous

    def import_from_band(self):
        try:
            layers, settings = self.app.performance.collect()
            self.import_snapshot(layers, settings)
        except Exception as e:
            messagebox.showerror('复制失败', str(e), parent=self)

    def import_snapshot(self, layers, settings):
        self.load_document(dict(schema=1, model='simss', layers=layers, settings=settings))
        self.status.set('已复制性能页输入；原页输入与结果保留。请核对自动分界、内接触和连接参数。')

    def load_document(self, data):
        if self.running:
            raise ValueError('请先取消当前计算，再打开参数')
        data = deepcopy(data)
        if data.get('schema') != 1 or data.get('model') not in (
                MODEL, MODEL+'_input', MODEL+'_eqe', 'simss', 'tandem_series_reference_input', 'tandem_series_reference'):
            raise ValueError('请选择性能页或叠层页保存的参数/完整结果 JSON')
        split = auto_partition(data['layers'])
        t = dict(DEFAULTS, top_end=split, bottom_start=split)
        if data['model'].startswith(MODEL):
            t.update(data['tandem'])
        elif 'split_after_layer' in data:
            t.update(top_end=data['split_after_layer'], bottom_start=data['split_after_layer'],
                     resistance=data.get('connection_resistance', .1))
        t = parameters(data['layers'], data['settings'], t)
        self.apply_parameters(data, validator=lambda l, s: parameters(l, s, t))
        self.loading = True
        self.top_end.current(t['top_end']-1); self.bottom_start.current(t['bottom_start']-1)
        self.automatic_contacts.set(t['automatic_contacts'])
        for key, var in self.tandem_vars.items():
            var.set(MODES[t[key]] if key=='mode' else f'{t[key]:g}')
        self.loading = False
        self.connection_changed(); self.update_assignment()
        self.status.set('叠层参数已打开；原结果保留至运行成功。打开完整结果时只载入其输入。')

    def load(self):
        path = filedialog.askopenfilename(parent=self, initialdir=str(STRUCTURES_DIR), filetypes=[('叠层/性能参数', '*.json')])
        if path:
            try:
                self.load_document(json.loads(Path(path).read_text(encoding='utf-8-sig')))
            except Exception as e:
                messagebox.showerror('打开失败', str(e), parent=self)

    def save(self):
        try:
            layers, settings = self.collect()
            t = parameters(layers, settings, self.tandem_values())
            data = dict(schema=1, model=MODEL+'_input', engine=ENGINE_VERSION, layers=layers, settings=settings, tandem=t)
            self.write_json(data, '叠层参数')
        except Exception as e:
            messagebox.showerror('保存失败', str(e), parent=self)

    def write_json(self, data, title):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.json', filetypes=[(title, '*.json')])
        if path:
            Path(path).write_text(json.dumps(json_value(data), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

    def run(self):
        self.start_task(False)

    def run_eqe(self):
        self.start_task(True)

    def start_task(self, eqe):
        if self.running:
            return
        try:
            layers, settings = self.collect(); t = parameters(layers, settings, self.tandem_values())
            q = settings['eqe']
            if eqe and not (1<=q['step_nm']<=200 and q['photon_flux_cm2_s']>0 and q['background_scale']>0):
                raise ValueError('叠层工作点EQE要求步长1–200nm，探测通量和背景比例均>0')
        except Exception as e:
            messagebox.showerror('无法开始叠层模拟', str(e), parent=self); return
        self.set_running(True); self.toggle_settings(False)
        self.cancel_event = threading.Event(); cancel = self.cancel_event
        self.progress = ttk.Progressbar(self.footer, mode='indeterminate')
        self.progress.pack(fill='x', pady=3); self.progress.start(15)
        self.status.set('正在后台计算叠层工作点EQE…' if eqe else '正在后台计算叠层 J–V…')
        def worker():
            try:
                fn = run_tandem_eqe if eqe else run_tandem
                result = fn(layers, settings, t, cancel, lambda s:self.events.put(('progress', s)))
                self.events.put(('eqe_result' if eqe else 'result', result))
            except SimulationCancelled as e:
                self.events.put(('cancel', str(e)))
            except Exception as e:
                self.events.put(('error', str(e)))
        self.worker = threading.Thread(target=worker, daemon=False); self.worker.start()
        self.poll_id = self.after(80, self.poll)

    def poll(self):
        self.poll_id = None
        if self.closed:
            return
        try:
            kind, data = self.events.get_nowait()
        except queue.Empty:
            self.poll_id = self.after(80, self.poll); return
        if kind == 'progress':
            if not self.cancel_event.is_set():self.status.set(data)
            self.poll_id = self.after(20, self.poll); return
        self.progress.stop(); self.progress.destroy(); self.set_running(False)
        if kind in ('result', 'eqe_result') and not self.cancel_event.is_set():
            self.show_result(data, eqe=kind=='eqe_result')
        elif kind == 'cancel' or self.cancel_event.is_set():
            self.status.set('已取消；上次成功的 J–V 和 EQE 均保留。')
        else:
            self.status.set('本次失败；上次成功结果保留，未采用失败的部分结果。')
            messagebox.showerror('叠层模拟失败', data, parent=self)

    def show_result(self, result, *, eqe=False):
        if eqe:
            self.previous_eqe = self.eqe_result; self.eqe_result = result
            self.plot_view.set('EQE')
        else:
            self.previous_result = self.result; self.result = result
            self.plot_view.set('J–V 曲线'); self.dirty = False
        self.warning.set('等效连接参数需标定；此结果不验证实际隧穿/复合连接。'+
                         (' EQE 是工作点微分响应，积分值不等于 Jsc。' if eqe else ''))
        if eqe and max(result['numerical_error_estimate'])>.01:
            self.warning.set(self.warning.get()+' 探测数值误差估计超过1个百分点，请调整通量和网格。')
        self.status.set(f"叠层{' EQE' if eqe else ' J–V'} 完成 · {result['elapsed']:.1f} s · 输入和结果独立于原性能页。")
        for button in self.export_buttons:button.configure(state='normal')
        self.plot()

    def plot(self):
        ax = self.ax; ax.clear(); self.analysis_label.pack_forget()
        if not self.ready:
            ax.set(xlabel='端电压 / V', ylabel='输出电流密度 / mA/cm²'); self.canvas.draw_idle(); return
        view = self.plot_view.get(); r = self.eqe_result if view=='EQE' else self.result
        self.loss_choice.configure(state='readonly' if view=='连接损失' else 'disabled')
        self.comparison_label.pack_forget()
        if view=='EQE':
            self.summary.pack_forget(); self.mpp_label.pack_forget()
        else:
            self.summary.pack(fill='x', before=self.plot_controls)
            self.mpp_label.pack(anchor='w', padx=8, before=self.plot_controls)
            for key, var in self.metric_vars.items():var.set('—' if r is None else f"{r['metrics'][key]:.3f}")
            self.mpp_text.set('请运行叠层 J–V；结果保留到下次成功。' if r is None else
                              f"MPP：{r['metrics']['Vmp']:.3f} V · {r['metrics']['Jmp']:.3f} mA/cm² · {r['metrics']['Pmax']:.3f} mW/cm²")
        if r is None:
            ax.text(.5,.5,'运行叠层 EQE 后显示工作点响应' if view=='EQE' else '设置分界与连接参数后，运行叠层 J–V',
                    ha='center', va='center', transform=ax.transAxes, color='#6e6e73')
            self.canvas.draw_idle(); return
        if view=='EQE':
            for key, label, color in [('top_EQE','顶电池（实际工作偏压）','#007aff'),
                    ('bottom_EQE','底电池（实际工作偏压）','#34a17b'),('EQE','叠层端口微分 EQE','#af52de')]:
                ax.plot(r['wavelength_nm'], np.asarray(r[key])*100, label=label, color=color)
            if self.show_previous.get() and self.previous_eqe is not None:
                old=self.previous_eqe; ax.plot(old['wavelength_nm'], np.asarray(old['EQE'])*100, '--', label='上次端口EQE', color='#c77700')
            ax.set(xlabel='波长 / nm', ylabel='微分 EQE / %', title=f"叠层工作点响应 · 外部偏压 {r['tandem']['eqe_voltage']:g} V")
            c=r['weighted_currents']
            self.show_analysis_note(f"光谱积分响应 / mA/cm²：顶 {c['top']:.3f} · 底 {c['bottom']:.3f} · 端口 {c['terminal']:.3f}；不是偏置光测量或Jsc预测。")
        elif view=='J–V 曲线':
            for name, cell, color in [('顶子电池',r['subcells']['top'],'#007aff'),('底子电池',r['subcells']['bottom'],'#34a17b'),('2T 串联',r,'#af52de')]:
                ax.plot(cell['voltage'], cell['current'], label=name, color=color, lw=2)
            if self.show_previous.get() and self.previous_result is not None:
                old=self.previous_result; ax.plot(old['voltage'],old['current'],'--',color='#c77700',label='上次2T')
            if not self.full_scan.get():
                ax.set(xlim=(-.03,r['metrics']['Voc']*1.08),ylim=(-1,max(c['metrics']['Jsc'] for c in r['subcells'].values())*1.12))
            ax.set(xlabel='端电压 / V',ylabel='输出电流密度 / mA/cm²',title='2T 多尺度叠层 · 等效连接假设')
        elif view=='子电池参数':
            ax.axis('off'); cells=[r['subcells']['top'],r['subcells']['bottom'],r]
            table=ax.table(cellText=[[label]+[f"{c['metrics'][k]:.3f}" for k in ['Jsc','Voc','FF','PCE']]
                                     for label,c in zip(['顶子电池','底子电池','2T串联'],cells)],
                           colLabels=['模型','Jsc / mA/cm²','Voc / V','FF / %','PCE / %'], loc='center')
            table.auto_set_font_size(False);table.set_fontsize(10);table.scale(1,1.8)
            self.show_analysis_note('子电池效率均以整器件入射功率为分母；子电池各自最大功率不能直接相加得到串联功率。')
        elif view=='电流匹配':
            m=r['matching'];js=np.asarray(m['series_current']);keep=(js>=0)&(js<=r['metrics']['Jsc']*1.05)
            for key,label in [('top_voltage','顶电池电压'),('bottom_voltage','底电池电压'),('connection_drop','连接压降'),('external_voltage','端口电压')]:
                ax.plot(js[keep],np.asarray(m[key])[keep],label=label)
            ax.axvline(r['workpoints']['MPP']['series_current'],ls='--',color='#aeaeb2',label='MPP共同电流')
            ax.set(xlabel='串联共同电流 / mA/cm²',ylabel='电压 / V')
            g=r['generation_audit'];self.show_analysis_note(f"q∫Gdx / mA/cm²：顶 {g['top']:.3f} · 连接区 {g['junction']:.3f} · 底 {g['bottom']:.3f}；端口电流由串联工作点确定。")
        elif view=='连接损失':
            key={'短路':'SC','最大功率点':'MPP','开路':'OC'}[self.loss_point.get()];p=r['workpoints'][key]
            keys=['top_power','bottom_power','connection_power','series_power','shunt_power','output_power']
            ax.barh(['顶电池供给','底电池供给','连接损耗','外部Rs损耗','Rsh损耗','端口输出'],[p[k] for k in keys],color=['#007aff','#34a17b','#ff9500','#ff9500','#ff9500','#af52de'])
            ax.invert_yaxis();ax.set(xlabel='功率密度 / mW/cm²',title=self.loss_point.get()+'功率收支（非完整光子损失分解）')
            self.show_analysis_note(f"V顶 {p['top_voltage']:.4f} + V底 {p['bottom_voltage']:.4f} − V连接 {p['connection_drop']:.4f} − V外部Rs = V端口 {p['external_voltage']:.4f} V；功率残差 {p['power_residual']:.2e} mW/cm²。")
        elif view=='入射光谱':
            o=np.asarray(r['optics']['spectrum_nm_W_m2_nm']);ax.plot(o[:,0],o[:,1],color='#ff9500',label='实际入射光谱')
            ax.set(xlabel='波长 / nm',ylabel='光谱辐照度 / W/m²/nm')
        else:
            o=r['optics'];ax.plot(o['x_nm'],o['G_cm3_s'],color='#007aff',label='完整堆栈 G(x)')
            t=r['tandem'];a=sum(x['thickness'] for x in r['layers'][:t['top_end']]);b=sum(x['thickness'] for x in r['layers'][:t['bottom_start']])
            ax.axvline(a,color='#af52de',ls='--',label='顶电池终点')
            if b>a:ax.axvspan(a,b,color='#ff9500',alpha=.15,label='等效连接区')
            ax.set(xlabel='从入射侧起的位置 / nm',ylabel='光生率 G / [1/(cm³·s)]',ylim=(0,None))
        if view not in ('子电池参数','连接损失'):
            ax.grid(alpha=.2); ax.legend(loc='best',fontsize=8)
        self.canvas.draw_idle()

    def export_csv(self):
        view=self.plot_view.get();r=self.eqe_result if view=='EQE' else self.result
        if r is None:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=[('当前叠层曲线/参数','*.csv')])
        if path:
            try:
                table,header=curve_table(r,view);np.savetxt(path,table,delimiter=',',header=header,comments='')
            except Exception as e:messagebox.showerror('导出失败',str(e),parent=self)

    def export_result(self):
        r=self.eqe_result if self.plot_view.get()=='EQE' else self.result
        if r is None:return
        try:
            self.write_json(dict(r,created_utc=datetime.now(timezone.utc).isoformat(),
                                 current_convention='positive delivered, mA/cm2'),'完整叠层结果')
        except Exception as e:messagebox.showerror('导出失败',str(e),parent=self)

    def export_image(self):
        view=self.plot_view.get();r=self.eqe_result if view=='EQE' else self.result
        if r is None:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.png',filetypes=[('PNG','*.png'),('SVG','*.svg')])
        if not path:return
        if view=='EQE':
            text='工作点微分 EQE · 等效连接 · 积分响应不等于 Jsc'
        else:
            m=r['metrics'];text=f"2T 等效连接 · Jsc {m['Jsc']:.3f} mA/cm² · Voc {m['Voc']:.3f} V · FF {m['FF']:.2f}% · PCE {m['PCE']:.2f}%"
        caption=self.fig.text(.5,1.02,text,ha='center',fontsize=10)
        try:self.fig.savefig(path,dpi=200,bbox_inches='tight',facecolor='white')
        except Exception as e:messagebox.showerror('导出失败',str(e),parent=self)
        finally:caption.remove()

