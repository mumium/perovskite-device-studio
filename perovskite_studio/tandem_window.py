"""A visibly separate series-reference view; never overwrites single-stack JV."""
from copy import deepcopy
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from .physics import profile
from .performance import SimulationCancelled,validate_device,calculate_metrics
from .tandem_reference import run_tandem_reference


class TandemReferenceWindow(tk.Toplevel):
    def __init__(self,parent,layers,settings):
        super().__init__(parent)
        self.title('两子电池串联参考 · 未验证真实n/p连接 · MK Design')
        width=max(850,min(1120,self.winfo_screenwidth()-80))
        height=max(550,min(800,self.winfo_screenheight()-100))
        self.geometry(f'{width}x{height}');self.minsize(850,550)
        self.layers=deepcopy(layers);self.settings=deepcopy(settings)
        self.result=None;self.running=False;self.closed=False;self.poll_id=None
        self.events=queue.Queue();self.cancel_event=threading.Event()
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Destroy>',self.on_destroy,add='+')
        body=ttk.Frame(self,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text='两子电池串联参考',font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w')
        ttk.Label(body,text='同一完整结构的光生分配 · 同电流串联 · 电压相加',foreground='#007aff').pack(anchor='w',pady=(2,5))
        ttk.Label(body,text='此模式用虚拟选择性内接触建立参考；连接电阻为假设参数。它不能证明实际20n/20p接触已形成隧穿或复合连接。',
                  wraplength=790,foreground='#9b4f00').pack(anchor='w',pady=(0,10))
        controls=ttk.Frame(body);controls.pack(fill='x')
        ttk.Label(controls,text='分界（左n / 右p）').pack(side='left')
        labels=[f'{i+1}：{layers[i]["name"]}  |  {layers[i+1]["name"]}' for i in range(len(layers)-1)]
        self.split=ttk.Combobox(controls,values=labels,state='readonly',width=40);self.split.pack(side='left',padx=6)
        best=0
        for i in range(len(layers)-1):
            a=profile(layers[i],[1.]);b=profile(layers[i+1],[0.])
            if a['Nd'][0]>a['Na'][0] and b['Na'][0]>b['Nd'][0]:best=i;break
        if labels:self.split.current(best)
        ttk.Label(controls,text='连接电阻 Ω·cm²').pack(side='left',padx=(8,3))
        self.resistance=tk.StringVar(value='0');self.entry=ttk.Entry(controls,textvariable=self.resistance,width=7);self.entry.pack(side='left')
        actions=ttk.Frame(body);actions.pack(fill='x',pady=10)
        self.run_button=ttk.Button(actions,text='运行串联参考',style='Accent.TButton',command=self.run);self.run_button.pack(side='left')
        self.cancel_button=ttk.Button(actions,text='取消',command=self.cancel,state='disabled');self.cancel_button.pack(side='left',padx=6)
        self.save_button=ttk.Button(actions,text='导出参考 JSON',command=self.export,state='disabled');self.save_button.pack(side='left')
        self.status=tk.StringVar(value='0表示理想零损连接参考；总入射功率只计一次，原J–V结果独立保留。')
        ttk.Label(body,textvariable=self.status,wraplength=1030).pack(anchor='w',pady=(0,8))
        self.table=ttk.Treeview(body,columns=('Jsc','Voc','FF','PCE'),height=3,show='tree headings')
        self.table.heading('#0',text='模型 / 子电池');self.table.column('#0',width=200)
        for key,title in [('Jsc','Jsc / mA/cm²'),('Voc','Voc / V'),('FF','FF / %'),('PCE','效率 / %')]:
            self.table.heading(key,text=title);self.table.column(key,width=135,anchor='center')
        self.table.pack(fill='x')
        self.fig=Figure(figsize=(9,4),dpi=100);self.ax=self.fig.add_subplot(111)
        self.canvas=FigureCanvasTkAgg(self.fig,master=body);self.canvas.get_tk_widget().pack(fill='both',expand=True,pady=(8,0))

    def run(self):
        if self.running:return
        try:
            split=self.split.current()+1;rc=float(self.resistance.get())
            import math
            if not math.isfinite(rc) or rc<0:raise ValueError('连接电阻须为有限非负数')
        except Exception as e:messagebox.showerror('无法运行',str(e),parent=self);return
        self.running=True;self.cancel_event=threading.Event()
        self.run_button.configure(state='disabled');self.split.configure(state='disabled');self.entry.configure(state='disabled')
        self.cancel_button.configure(state='normal');self.save_button.configure(state='disabled')
        self.status.set('正在建立参考；已有曲线保留至本次成功。')
        def worker():
            try:
                r=run_tandem_reference(self.layers,self.settings,split,rc,self.cancel_event,lambda t:self.events.put(('progress',t)))
                self.events.put(('result',r))
            except SimulationCancelled:self.events.put(('cancel','已取消，原结果保留。'))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=False).start();self.poll_id=self.after(80,self.poll)

    def poll(self):
        self.poll_id=None
        if self.closed:return
        try:kind,data=self.events.get_nowait()
        except queue.Empty:self.poll_id=self.after(80,self.poll);return
        if kind=='progress':self.status.set(data);self.poll_id=self.after(80,self.poll);return
        self.running=False;self.run_button.configure(state='normal');self.split.configure(state='readonly');self.entry.configure(state='normal');self.cancel_button.configure(state='disabled')
        if kind=='result' and not self.cancel_event.is_set():self.show_result(data)
        elif kind=='error':self.status.set('未得到有效串联参考，原结果保留。');messagebox.showerror('串联参考失败',data,parent=self)
        else:self.status.set('已取消，原结果保留。')
        self.save_button.configure(state='normal' if self.result else 'disabled')

    def show_result(self,result):
        self.result=result;self.table.delete(*self.table.get_children());self.ax.clear()
        entries=[('宽带隙侧',result['subcells']['top']),('窄带隙侧',result['subcells']['bottom']),('串联参考',result)]
        for label,r in entries:
            m=r['metrics'];self.table.insert('', 'end',text=label,values=[f'{m[k]:.4f}' for k in ('Jsc','Voc','FF','PCE')])
            self.ax.plot(r['voltage'],r['current'],label=label,lw=2)
        self.ax.set(xlabel='端电压 / V',ylabel='电流密度 / mA/cm²',xlim=(0,result['metrics']['Voc']*1.1),
                    ylim=(-1,max(r['metrics']['Jsc'] for _,r in entries)*1.12),title='串联参考：虚拟内接触，未验证真实连接区')
        self.ax.grid(alpha=.2);self.ax.legend();self.fig.tight_layout();self.canvas.draw()
        g=result['generation_audit'];rc=result['connection']['resistance_ohm_cm2']
        self.status.set(f'参考完成 · 假设连接电阻 {rc:g} Ω·cm² · 光生拆分 {g["split_integral_sum"]:.3f} mA/cm² · 非真实n/p连接预测')
        self.save_button.configure(state='normal')

    def cancel(self):
        self.cancel_event.set();self.status.set('正在取消…')

    def export(self):
        if not self.result:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',initialfile='两子电池串联参考_非真实连接预测.json',filetypes=[('JSON','*.json')])
        if not path:return
        try:
            with open(path,'w',encoding='utf-8') as f:json.dump(self.result,f,ensure_ascii=False,indent=2)
        except Exception as e:messagebox.showerror('导出失败',str(e),parent=self)

    def close(self):
        self.closed=True;self.cancel_event.set()
        if self.poll_id:self.after_cancel(self.poll_id)
        self.destroy()

    def on_destroy(self,event):
        if event.widget is not self or self.closed:return
        self.closed=True;self.cancel_event.set()
        if self.poll_id:
            try:self.after_cancel(self.poll_id)
            except tk.TclError:pass
            self.poll_id=None


def open_reference_file(parent,data):
    """Restore only into the reference window, never the ordinary JV page."""
    import math
    import numpy as np
    if data.get('schema')!=1 or data.get('model') not in ('tandem_series_reference','tandem_series_reference_input'):
        raise ValueError('不是串联参考项目')
    validate_device(data['layers'],data['settings'])
    split=data['split_after_layer']
    if not isinstance(split,int) or not 0<split<len(data['layers']):raise ValueError('无效的串联分界')
    rc=data.get('connection',{}).get('resistance_ohm_cm2',data.get('connection_resistance',0.))
    if not math.isfinite(rc) or rc<0:raise ValueError('无效的连接电阻')
    if data['model']=='tandem_series_reference':
        for r in [data,data['subcells']['top'],data['subcells']['bottom']]:
            actual=calculate_metrics(r['voltage'],r['current'],data['settings']['pin'])[2]
            if any(actual[k] is None or not np.isclose(actual[k],r['metrics'][k],rtol=1e-8,atol=1e-8) for k in ('Jsc','Voc','FF','PCE')):
                raise ValueError('保存的参考指标与曲线不一致')
        g=data['generation_audit']['split_integral_sum']
        if not math.isfinite(g) or g<0:raise ValueError('无效的光生核对记录')
    win=TandemReferenceWindow(parent,data['layers'],data['settings']);win.split.current(split-1);win.resistance.set(f'{rc:g}')
    if data['model']=='tandem_series_reference':win.show_result(data)
    return win
