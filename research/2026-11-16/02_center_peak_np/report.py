"""Create a portable report and figures from completed, unmodified solver runs."""
import csv,html,json,re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import study as s

plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],
                     'axes.unicode_minus':False,'font.size':10,'figure.dpi':160})
H=s.HERE


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def record(mode,name):
    r=read(H/mode/(name+'_summary.json'))
    if not r['success']:raise RuntimeError('Failed result cannot appear in final table')
    return r


def render_report(text):
    """Render the small Markdown subset used here, without extra dependencies."""
    def inline(t):
        t=html.escape(t)
        t=re.sub(r'!\[([^]]*)\]\(([^)]+)\)',r'<img alt="\1" src="\2">',t)
        t=re.sub(r'(?<!!)\[([^]]*)\]\(([^)]+)\)',r'<a href="\2">\1</a>',t)
        return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',t)
    lines=text.splitlines();out=[];i=0
    while i<len(lines):
        line=lines[i]
        if not line.strip():i+=1;continue
        if line.startswith('```'):
            block=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
            out.append('<pre>'+html.escape('\n'.join(block))+'</pre>');i+=1;continue
        if line.startswith('|'):
            group=[]
            while i<len(lines) and lines[i].startswith('|'):group.append(lines[i]);i+=1
            trs=[]
            for n,row in enumerate(group):
                if n==1:continue
                tag='th' if n==0 else 'td'
                trs.append('<tr>'+''.join(f'<{tag}>{inline(c.strip())}</{tag}>' for c in row.strip('|').split('|'))+'</tr>')
            out.append('<table>'+''.join(trs)+'</table>');continue
        if line.startswith('#'):
            n=len(line)-len(line.lstrip('#'));out.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>')
        else:out.append('<p>'+inline(line)+'</p>')
        i+=1
    return '\n'.join(out)


def main():
    # Historical/current summary files contain identities, not repeated n,k arrays.
    def compact(value):
        if isinstance(value,list):return [compact(z) for z in value]
        if isinstance(value,dict):
            out={k:compact(v) for k,v in value.items()}
            if 'settings' in out:out['settings']=s.summary_settings(out['settings'])
            return out
        return value
    for path in [*H.glob('*summary.json'),*H.glob('physical/*_summary.json')]:
        s.save_json(path,compact(read(path)))
    figdir=H/'figures';figdir.mkdir(exist_ok=True)
    selected=[('完整器件：原中央峰值1e16','physical','dense_base'),
              ('完整器件：中央峰值3e17','physical','dense_peak3e17'),
              ('完整器件：3e17，中央Nt=1e11','physical','dense_peak3e17_Nt1e11'),
              ('条件串联：固定内接触，峰值1e16','conditional','fixed_base'),
              ('条件串联：固定内接触，峰值3e17','conditional','fixed_peak3e17'),
              ('条件串联：匹配理想内接触，峰值3e17','conditional','dense_peak3e17')]
    rows=[dict(label=label,mode=mode,case=name,**record(mode,name)['metrics']) for label,mode,name in selected]
    s.save_json(H/'final_performance.json',rows)
    with (H/'final_performance.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    fig,axes=plt.subplots(1,2,figsize=(11,4.1),layout='constrained')
    for label,mode,name in selected:
        a=np.genfromtxt(H/mode/(name+'_JV.csv'),delimiter=',',names=True)
        ax=axes[0 if mode=='physical' else 1]
        ax.plot(a[a.dtype.names[0]],a[a.dtype.names[1]],label=label.split('：')[1],lw=1.8)
    for ax,title,lim in zip(axes,['完整器件：真实中央界面 SRH','条件串联参考：预设选择性内接触'],[1.5,2.4]):
        ax.set(xlabel='端电压 / V',ylabel='输出电流 / (mA/cm²)',xlim=(0,lim),ylim=(0,18),title=title)
        ax.grid(alpha=.2);ax.legend(fontsize=8,loc='lower left')
    fig.savefig(figdir/'JV.png');plt.close(fig)
    p=read(H/'physical/dense_peak3e17_input.json')
    fig,axes=plt.subplots(1,2,figsize=(11,3.7),layout='constrained')
    x0=0
    for layer in p['layers']:
        x=np.linspace(x0,x0+layer['thickness'],101)
        for key,color in [('Nd','#1676cf'),('Na','#cd4b82')]:
            start=layer[key];end=layer[key+'_end'] if layer[key+'_mode']!='均匀' else start
            y=np.linspace(start,end,len(x))
            if np.any(y>0):
                for ax in axes:ax.plot(x,np.where(y>0,y,np.nan),color=color,lw=2)
        x0+=layer['thickness']
    for ax in axes:
        ax.set(yscale='log',ylim=(5e13,8e17),xlabel='从入光侧起位置 / nm',ylabel=r'输入 Nd / Na / cm$^{-3}$')
        ax.axvline(420,color='gray',ls='--',lw=1);ax.grid(alpha=.2)
        ax.plot([],[],color='#1676cf',label='Nd');ax.plot([],[],color='#cd4b82',label='Na');ax.legend()
    axes[0].set(xlim=(0,1260),title='全结构：主吸收层保持原掺杂')
    axes[1].set(xlim=(390,450),title='中间两层：中央高、两侧低')
    fig.savefig(figdir/'doping.png');plt.close(fig)
    audit=read(H/'spatial/accounting.json')
    a=np.genfromtxt(H/'spatial/MPP_readable.csv',delimiter=',',names=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for key,label,color in [('Ec_eV','Ec','#1879bf'),('Ev_eV','Ev','#42654c'),
                            ('EFn_eV','EFn','#e18b28'),('EFp_eV','EFp','#c34888')]:
        axes[0].plot(a['x_nm'],a[key],label=label,color=color)
    axes[0].set(xlabel='位置 / nm',ylabel='能量 / eV',title='完整器件最大功率点附近能级')
    axes[0].legend(ncol=2)
    for key,label in [('Jn_native_mA_cm2','电子电流 Jn'),('Jp_native_mA_cm2','空穴电流 Jp')]:
        axes[1].plot(a['x_nm'],-a[key],label=label)
    axes[1].plot(a['x_nm'],-a['Jn_native_mA_cm2']-a['Jp_native_mA_cm2'],label='总电流',ls='--')
    axes[1].set(xlim=(390,450),xlabel='位置 / nm',ylabel='−原生电流 / (mA/cm²)',title='中央电流转换：总电流守恒不等于无电压损失')
    for ax in axes:ax.axvline(420,color='gray',ls='--',lw=1);ax.grid(alpha=.2)
    axes[1].legend(fontsize=8)
    fig.savefig(figdir/'state.png');plt.close(fig)
    # Self-contained reusable inputs; remove unused tandem metadata from ordinary JV.
    library=[('physical','dense_peak3e17','2026-11-16_中央高掺杂_np渐变_完整器件.json'),
             ('physical','dense_peak3e17_Nt1e11','2026-11-16_中央高掺杂_np渐变_界面SRH诊断.json'),
             ('conditional','fixed_peak3e17','2026-11-16_中央高掺杂_np渐变_固定内接触串联参考.json'),
             ('conditional','dense_peak3e17','2026-11-16_中央高掺杂_np渐变_匹配内接触串联参考.json')]
    for mode,name,file in library:
        q=read(H/mode/(name+'_input.json'))
        if mode=='physical':q.pop('tandem',None)
        s.save_json(s.ROOT/'device_structures'/file,q)
    dense=[record('physical',n) for n in ['dense_base','dense_peak3e17','dense_peak3e17_Nt1e11']]
    refined=[record('physical',n) for n in ['fine_base','fine_peak3e17','fine_peak3e17_Nt1e11']]
    checks=[dict(case=a['name'],PCE_fine=b['metrics']['PCE'],PCE_dense=a['metrics']['PCE'],
                 delta_pp=a['metrics']['PCE']-b['metrics']['PCE'],pv_current_error=a['pv_current_error'])
            for a,b in zip(dense,refined)]
    s.save_json(H/'numerical_check.json',checks)
    near=next(z for z in audit['points'] if z['label']=='near_OC')
    table='\n'.join('| '+r['label']+' | '+' | '.join(f"{r[k]:.4f}" for k in ['Jsc','Voc','FF','PCE'])+' |' for r in rows)
    states='\n'.join('| '+z['label']+' | '+' | '.join(f"{z[k]:.6f}" for k in ['Vext','J_output_mA_cm2','top_extraction_QF_V','bottom_extraction_QF_V','central_QF_loss_V','outer_QF_V'])+' |' for z in audit['points'])
    text=f'''# 中央高掺杂 n/p 渐变层：纠正结构后的重算

已纠正上一轮结构：380/780 nm 主吸收层恢复原来的均匀弱 n 型掺杂；只提高中间 20 nm n 层和 20 nm p 层在相互接触处的掺杂。没有增加独立互联材料或减反层。**本次尚未证明真实中央接触能实现低损耗串联或 30% 效率。**

[离线图文报告](报告.html) · [最终性能 CSV](final_performance.csv) · [输入参数库](../../../device_structures/README.md)。全部参数内嵌文献代理 n,k，需从对应页面打开参数文件，不能只改几项掺杂后与其他旧设置比较。

## 这次使用什么参数

层序为入射光 → NiOx 20 / 宽带隙 380 / n 渐变 20 / p 渐变 20 / 窄带隙 780 / C60 40 nm。下表沿此方向读取左右端值，浓度单位 cm⁻³：

| 区域 | Eg / χ（eV） | Nd 左→右 | Na 左→右 |
| --- | --- | --- | --- |
| 宽带隙主吸收层 380 nm | 1.78 / 3.8 | 1e14，均匀 | 0 |
| n 型渐变层 20 nm | 1.78 / 3.8 | 1e14 → 3e17，线性 | 0 |
| p 型渐变层 20 nm | 1.25 / 3.9 | 0 | 3e17 → 1e14，线性 |
| 窄带隙主吸收层 780 nm | 1.25 / 3.9 | 1e14，均匀 | 0 |

主吸收层 Nd=1e14、Na=0 与原始输入完全相同，窄带隙主层没有被擅自改成 p 型。p 渐变层外端 Na=1e14 也保留原设计。中央峰值测试 1e16、1e17、3e17；3e17 是本次非简并模型内的较高测试点，并非已确认的材料最优值。掺杂值按有效电离施主/受主处理，不能直接等同于前驱体加入量或界面自由载流子密度。

四个钙钛矿区域均开启产生光载流子。保留 Nc=Nv=3e18、μn=μp=2 cm²/V/s、τn=τp=1e-4 s、体缺陷1e15 cm⁻³、B=1e-10 cm³/s；其余原材料参数、原χ、外功函数5.0/4.1 eV、Rs=0.3 Ωcm²、Rsh=4e4 Ωcm²不变。AM1.5G 300–1100 nm、100 mW/cm²，Air 前侧占位不提供减反作用，背面 Ag 100 nm。n,k 是已有组分代理，NiOx仍沿用原PTAA光学代理，未按实际薄膜标定。

![输入掺杂分布](figures/doping.png)

## 完整器件与条件串联分别得到什么

| 模型与条件 | Jsc / mA cm⁻² | Voc / V | FF / % | PCE / % |
| --- | ---: | ---: | ---: | ---: |
{table}

**完整器件**用同一空间解计算所有层、电势与中央界面，原中央 Nt=0；峰值提高后 PCE 从11.3820%到12.5863%，FF从56.5407%到62.1608%，但 Voc仅从1.3057到1.3168 V。这是现有完整漂移扩散/复合模型的结果，不是对实际样品的预测。

**中央 SRH 诊断**只在 n/p 接触处增加中性界面 Nt=1e11 cm⁻²、Cn=Cp=1e-8 cm³/s，能级取共同禁带中点，得到11.6990%。另测 Nt=1e12，1400/24网格为10.8094%；增大普通陷阱没有产生理想复合连接，反而损失FF。捕获系数、Nt属于机制敏感性假设，未由实验拟合，不作为推荐缺陷密度。

**条件串联**把完整光生分布分给两子电池，预设理想选择性内接触和中央连接电阻0.1 Ωcm²。固定内功函数3.95/5.00 eV时，峰值提高使20.9993%到22.4732%。再把理想内功函数改成随峰值平衡匹配的3.8595/5.0905 eV时，可得到25.1011%；**这个额外提升同时包含内接触边界的改变，不能归因于纯掺杂，更不能说是真实 n/p 接触已实现25.1%。** 内功函数计算采用 χ+kT ln(Nc/Nd) 和 χ+Eg−kT ln(Nv/Na)，只是理想边界设定；0.1 Ωcm²也不是从该掺杂推导出的真实连接电阻。叠层页不会由跨分界面的Nt自动求出连接电阻/复合J0。

![完整器件与条件串联 J–V](figures/JV.png)

## 为什么电子、空穴到了中央，电压仍相加不起来

你提出的方向是正确的：n 层向中央提高施主、p 层向中央提高受主，可在准中性梯度区域形成有利于相应多数载流子向中央输运的扩散场。但中央 n/p 结的耗尽区仍会产生势垒；电流到达界面，并不等于能在几乎零电化学势差下复合。

对峰值3e17、Nt=1e11的同一次完整器件空间求解，接近开路的实际端电压为 {near['Vext']:.6f} V，输出电流 {near['J_output_mA_cm2']:.6f} mA/cm²。电压核算为：

```text
宽侧抽取端准费米差      {near['top_extraction_QF_V']:.6f} V
+ 窄侧抽取端准费米差    {near['bottom_extraction_QF_V']:.6f} V
− 中央 n/p 准费米差     {near['central_QF_loss_V']:.6f} V
= 两外侧吸收层抽取端差  {near['outer_QF_V']:.6f} V
器件端电压              {near['Vext']:.6f} V
```

这是同一个完整状态的电压账本，上面两侧差值不是独立子电池的Voc；各边界取相邻对应材料网格点。其余差值来自外侧传输/接触。原生 Jn/Jp 的转换显示中央存在复合交换，同时仍有显著准费米差及非理想选择性。不能将界面复合电流大直接解释为高效率串联。

| 状态 | 实际端电压/V | 输出电流/mA cm⁻² | 宽侧准费米差/V | 窄侧准费米差/V | 中央差/V | 外端差/V |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{states}

SC、MPP、near_OC为空间单点求解，选用完整JV中最近实际记录的内部电压Vint；不是精确短路/MPP/开路。已核验单点与原JV电流差小于0.01 mA/cm²，报告保留实际Vext。原生SI表和便读单位表均在spatial目录，电流原生正号与输出电流正号相反。

![最大功率点附近空间解](figures/state.png)

## 为什么没有直接把峰值填成1e19

本引擎使用非简并玻尔兹曼统计，没有费米–狄拉克简并统计、带间或非局域隧穿。当前 Nc/Nv=3e18 cm⁻³；若直接填1e19，已经大于有效态密度，不能凭一个能运行的数值就给出可靠效率。真实重掺杂还需要电离、缺陷、迁移率、Auger/带隙变化等材料数据；本次没有通过修改态密度或寿命掩盖这些限制。

仅为理解尺度，按对称突变均匀结、εr=6.55、固定耗尽电势1.2V，W≈√(4εV/qN)：1e16、1e17、3e17、1e18、1e19对应约417、132、76、42、13 nm。**这不是当前有限厚度渐变异质结的耗尽区解，也不是隧穿电流预测**，只说明把两侧提高至1e16并不足以自动形成很薄的高效连接；即使估计宽度变薄，仍须有实际的复合/隧穿通道。

可验证的下一步应是为这两层本身补充适用的重掺杂/隧穿或经实验标定的界面复合模型，而不一定增加独立材料层。现有模型能做上述提取趋势与损失对照，不能证明所有无独立互联材料的结构都不可行。

## 数值和复现

本次8组完整器件粗扫、4组细化、3组进一步细化，共15条完整器件JV；另9条条件串联参考。主完整器件结论采用2000点/40分段/0.005V；固定内接触对照为1400/24/0.01V，匹配内接触参考为2000/40/0.005V。全程沿用生产求解器、原始接受规则，未把扫描上限当Voc，未采用失败/部分/非有限结果。

1400/24/0.01V → 2000/40/0.005V：完整器件原峰值11.3908→11.3820%，高峰值无界面陷阱12.6030→12.5863%，高峰值Nt1e11诊断11.7539→11.6990%；匹配内接触参考25.0996→25.1011%。网格/分段/步长共同变化，不分别归因，也不宣称严格数学收敛。粗/细Nt1e12诊断存在约0.27个百分点差异，因此不将其作定量优化方案；其FF下降的方向与其他对照一致。

生产引擎{record('physical','dense_peak3e17')['engine_build']}；各原生运行日志/电流误差与完整结果保留。完整器件光伏区最大原生errJ/总光生电流小于0.5%才接受，具体比值见summary与numerical_check.json。

按顺序运行 study.py、refine.py、converge.py、fixed_contacts.py、report.py。Python环境安装项目requirements，使用配套SimSS 5.36-pds3。最终参数库的“完整器件/界面SRH诊断”文件在**器件性能模拟**页打开；两份“串联参考”在**叠层电池模拟**页打开。1.5.1程序可用，不需要重新打包。两种页面代表不同模型，结果不应混用。

Git保留汇总、两列JV、所选自包含参数、空间原始数据与复现脚本；全部原生多列JV、日志、全部输入和完整JSON gzip另放在[研究数据发布页](https://github.com/mumium/perovskite-device-studio/releases/tag/research-2026-11-16-center-peak-np)。ZIP中的SHA256清单可核对文件完整性。

上一轮26.7191%改变了两主吸收层的Nd/Na及中间梯度方向，属于另一种扩展结构，**不是你要求的中央高掺杂方案**；其原数据保留作为历史对照，不应继续作为本设计的优化结果。

依据：[SIMsalabim 5.36源码](https://github.com/kostergroup/SIMsalabim/tree/v5.36)、[本项目求解器修改记录](../../../vendor/simsalabim/PROVENANCE.md)。[Schramm等2024年电掺杂与PN结实验](https://advanced.onlinelibrary.wiley.com/doi/full/10.1002/adma.202314289)支持钙钛矿n/p电掺杂及费米能级调节的可行性，但不是本次峰值浓度、隧穿能力或效率的验证。光学来源沿用[300–1100nm文献代理研究](../../2026-11-13/02_extended_optics/README.md)。
'''
    (H/'README.md').write_text(text,encoding='utf-8')
    body=render_report(text)
    css='body{max-width:1120px;margin:36px auto;padding:0 24px;font:16px/1.75 "Microsoft YaHei",sans-serif;color:#223044;background:#f8fafc}h1,h2{line-height:1.4;color:#16243b}h2{margin-top:2em}img{max-width:100%;height:auto;background:white;border:1px solid #dde5ef;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:14px;background:white;display:block;overflow:auto}td,th{border:1px solid #dce3ed;padding:8px 12px;white-space:nowrap}th{background:#edf3fa}pre{background:#eaf0f7;padding:18px;overflow:auto;border-radius:8px}a{color:#136ac4}strong{color:#254d7c}'
    (H/'报告.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>中央高掺杂 n/p 渐变层重算</title><style>'+css+'</style><body>'+body+'</body></html>',encoding='utf-8')
    print('Report, figures, parameter library and final tables written',flush=True)


if __name__=='__main__':main()
