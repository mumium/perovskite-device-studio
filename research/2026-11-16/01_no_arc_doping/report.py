"""Build the offline report from accepted native snapshots, not screen scores."""
import csv,gzip,json,sys
from pathlib import Path
from copy import deepcopy
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from perovskite_studio.physics import profile


def read(folder,name):
    with gzip.open(HERE/folder/(name+'_result.json.gz'),'rt',encoding='utf-8') as f:return json.load(f)


def main():
    a=read('refined','baseline_fine');b=read('sensitivity','linear_fine')
    assert a['settings']['optics']==b['settings']['optics']
    allowed={'Nd','Na','Nd_end','Na_end','Nd_mode','Na_mode'}
    for old,new in zip(a['layers'],b['layers']):
        assert all(old[k]==new[k] for k in old if k not in allowed)
    figure=HERE/'figures';figure.mkdir(exist_ok=True)
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei UI','SimHei','DejaVu Sans'],'axes.unicode_minus':False})
    fig,ax=plt.subplots(figsize=(8.5,5.4))
    for r,label,color in [(a,'原始掺杂','#007aff'),(b,'线性掺杂优化','#269a72')]:
        ax.plot(r['voltage'],r['current'],label=label,lw=2,color=color)
        m=r['metrics'];ax.plot(m['Vmp'],m['Jmp'],'o',color=color)
    ax.set(xlim=(-.03,2.4),ylim=(-.5,16.5),xlabel='端电压 / V',ylabel='输出电流密度 / mA/cm²',title='无减反层 · 仅改钙钛矿掺杂 · 2T 等效连接模型')
    ax.grid(alpha=.18);ax.legend();fig.tight_layout();fig.savefig(figure/'JV.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.5,4.8));offset=0.
    for i,z in enumerate(b['layers']):
        x=np.linspace(0,1,250);p=profile(z,x)
        if z.get('absorber'):
            xx=offset+x*z['thickness']
            ax.plot(xx,p['Nd']/1e17,color='#007aff',label='Nd' if i==1 else None)
            ax.plot(xx,p['Na']/1e17,color='#af52de',label='Na' if i==1 else None)
            ax.axvline(offset,color='#aeaeb2',lw=.8,ls='--')
        offset+=z['thickness']
    ax.set(xlim=(20,1220),ylim=(-.03,1.13),xlabel='从器件入射侧起的位置 / nm',ylabel=r'浓度 / ($10^{17}$ cm$^{-3}$)',title='推荐对照的 Nd / Na 分布（两者分别线性变化）')
    ax.grid(alpha=.18);ax.legend();fig.tight_layout();fig.savefig(figure/'doping.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.5,5.4))
    for folder,name,label in [('verified','energy_doping','1000点 / 24分段 / 0.01V'),
                              ('sensitivity','energy_step','1000点 / 24分段 / 0.005V'),
                              ('sensitivity','energy_mesh','2000点 / 28分段 / 0.01V'),
                              ('refined','energy_fine','2000点 / 28分段 / 0.005V')]:
        r=read(folder,name);ax.plot(r['voltage'],r['current'],label=label,lw=1.7)
    ax.set(xlim=(1.65,2.25),ylim=(0,16),xlabel='端电压 / V',ylabel='输出电流密度 / mA/cm²',title='高对数渐变＋既有能级设计：数值敏感，未作为达标结果')
    ax.grid(alpha=.18);ax.legend(fontsize=8);fig.tight_layout();fig.savefig(figure/'sensitivity.png',dpi=180);plt.close(fig)
    rows=[]
    for name,r in [('baseline',a),('doping_recommended',b)]:
        rows.append(dict(case=name,**r['metrics']))
    with (HERE/'final_performance.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    changes={k:b['metrics'][k]-a['metrics'][k] for k in ['Jsc','Voc','FF','PCE']}
    final=dict(baseline=a['metrics'],recommended=b['metrics'],differences=changes,
               target_PCE=30.,target_reached=False,
               FF_required_at_same_Jsc_Voc=3000/(b['metrics']['Jsc']*b['metrics']['Voc']),
               baseline_numerics=dict(points=2000,slices=28,vstep=.005),
               recommended_numerics=dict(points=2000,slices=28,vstep=.005),
               scope=b['scope'],generation=dict(baseline=a['generation_audit'],recommended=b['generation_audit']))
    (HERE/'final_summary.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    # Deliver parameters in the dedicated library, preserving historical files.
    library=[]
    for r,name,description in [(a,'2026-11-16_无减反叠层_掺杂优化对照基准.json','Original doping; numerical control only.'),
                               (b,'2026-11-16_无减反叠层_线性掺杂优化.json','Doping-only comparison; not a validated 30 percent device.')]:
        data=dict(schema=1,model='tandem_2t_multiscale_input',engine='5.36',layers=r['layers'],settings=r['settings'],tandem=r['tandem'],description=description)
        (ROOT/'device_structures'/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');library.append(name)
    def table_row(title,m):return '<tr><td>'+title+'</td>'+''.join(f'<td>{m[k]:.3f}</td>' for k in ['Jsc','Voc','FF','PCE'])+'</tr>'
    primary=table_row('原始掺杂',a['metrics'])+table_row('推荐对照：线性掺杂渐变',b['metrics'])
    sensitivity=[]
    for folder,name,label in [('verified','doping','强对数渐变：1000点/24分段/0.01V'),
                              ('sensitivity','energy_step','能级＋对数渐变：1000点/24分段/0.005V'),
                              ('sensitivity','energy_mesh','同一能级＋对数渐变：2000点/28分段/0.01V'),
                              ('refined','energy_fine','同一能级＋对数渐变：2000点/28分段/0.005V')]:
        sensitivity.append(table_row(label,read(folder,name)['metrics']))
    html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>无减反层叠层掺杂优化与数值复核</title><style>body{{font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif;background:#f5f5f7;color:#1d1d1f;max-width:1050px;margin:auto;padding:28px}}section{{background:white;border:1px solid #e5e5ea;border-radius:14px;padding:22px;margin:18px 0}}h1{{font-size:28px}}h2{{font-size:21px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:10px;border-bottom:1px solid #e5e5ea;text-align:right}}td:first-child,th:first-child{{text-align:left}}img{{max-width:100%;height:auto}}a{{color:#007aff}}.note{{color:#895c00;background:#fff8e8;padding:12px;border-radius:8px}}.big{{font-size:30px;color:#168564;font-weight:700}}code{{overflow-wrap:anywhere}}</style>
<h1>无减反层叠层掺杂优化与数值复核</h1><p>2026-11-16 · Perovskite Device Studio 1.5.1 · MK Design</p>
<p class="note"><b>结构适用范围更正：</b>本报告改了两主吸收层掺杂，并反转了中间n/p梯度方向，偏离“仅中央高掺杂、向两侧降低”的原设计。26.7191%属于扩展结构及条件串联边界，不能作为原设计的成绩。历史数据保留；正确结构见<a href="../02_center_peak_np/报告.html">中央高掺杂纠正重算</a>。</p>
<section><h2>结果</h2><p class="big">{a['metrics']['PCE']:.3f}% → {b['metrics']['PCE']:.3f}%</p>
<p>仅改变四个钙钛矿功能层的 Nd / Na 及其渐变方式，效率提高 {changes['PCE']:.3f} 个百分点。厚度、Eg、χ、电极功函数、迁移率、寿命、复合系数、n,k、光谱、入射功率和电路参数保持原值。<b>本次未得到经过数值复核达到 30% 的方案。</b></p>
<table><tr><th>结构</th><th>Jsc / mA·cm⁻²</th><th>Voc / V</th><th>FF / %</th><th>PCE / %</th></tr>{primary}</table>
<p>同一 Jsc / Voc 下达到 30% 需要 FF≈{final['FF_required_at_same_Jsc_Voc']:.2f}%，当前为 {b['metrics']['FF']:.2f}%。掺杂优化主要提高电压和 FF，短路电流略降。</p>
<img src="figures/JV.png" alt="原始与推荐掺杂的JV"><p><a href="final_performance.csv">性能 CSV</a> · <a href="final_summary.json">最终汇总 JSON</a> · <a href="sensitivity/linear_fine_input.json">可打开的推荐参数 JSON</a> · <a href="refined/baseline_fine_input.json">对照基准参数 JSON</a></p></section>
<section><h2>推荐对照的掺杂分布</h2><p>结构仍为 NiOx 20 / 宽带隙 380 / n 层 20 / p 层 20 / 窄带隙 780 / C60 40 nm；两主吸收层 Eg 分别为 1.78 / 1.25 eV。Nd、Na 均按各自端点线性变化，单位 cm⁻³：</p>
<table><tr><th>层</th><th>Nd 左→右</th><th>Na 左→右</th></tr><tr><td>宽带隙 380 nm</td><td>0 → 1e17</td><td>1e17 → 0</td></tr><tr><td>n 层 20 nm</td><td>1e17 → 1e16</td><td>0 → 0</td></tr><tr><td>p 层 20 nm</td><td>0 → 0</td><td>1e16 → 1e17</td></tr><tr><td>窄带隙 780 nm</td><td>0 → 1e17</td><td>1e17 → 0</td></tr></table>
<img src="figures/doping.png" alt="Nd和Na渐变分布"><p>中间 n/p 接触端仍各为 1e16。相对原方案，靠吸收层一侧浓度更高，20 nm 缓冲层的浓度梯度方向也相应改变。输运层参数不变。入射侧仍为 Air，前光学占位层也是 n=1、k=0 的 Air/200 nm，背侧 Ag/100 nm；没有 SiO₂ 或其他减反膜。</p></section>
<section><h2>数值复核与未采纳的高效率候选</h2><p>推荐结果采用 2000 空间点、每渐变层 28 分段、0.005 V 步长。26 分段为 26.791%，0.01 V 步长为 26.735%；该组核对的变化小于 0.08 个百分点，不代表数学意义上的最终收敛证明。1000点/24分段/0.01V 为 27.031%，不采用该较粗结果作为主结论。</p>
<p>纯掺杂粗筛 226 个子电池条件，另以先前公布的能级设计作 62 个子电池条件对照，两类共得到 9824 组可组合粗筛曲线。能级对照把原能级设计里的减反膜完全移除。其 χ 与外接触功函数为额外设计变量，不能计为纯掺杂收益。粗筛允许有限光生重映射误差用于排名，所有最终重算都使用软件原有的 1% 总重映射、电流守恒和单调性门槛。</p>
<table><tr><th>探索配置（未选作推荐结论）</th><th>Jsc</th><th>Voc</th><th>FF</th><th>PCE</th></tr>{''.join(sensitivity)}</table>
<p class="note">能级＋对数渐变粗筛最高约 30.225%，重算和分辨率变化后没有保持。部分高掺杂候选因非单调曲线或原生数值溢出被拒绝，没有采用失败的部分曲线，也没有放宽软件接受门槛。强对数渐变结果仅作探索记录，不作为达到 30% 或器件结构优越性的证据。</p>
<img src="figures/sensitivity.png" alt="数值敏感性对照"><p><a href="subcell_scan.csv">纯掺杂子电池粗筛</a> · <a href="pair_scan.csv">纯掺杂组合粗筛</a> · <a href="energy_search/pair_scan.csv">额外能级设计粗筛</a> · <a href="verified_summary.json">完整重算汇总</a> · <a href="refined_summary.json">细化结果</a> · <a href="sensitivity_summary.json">单因素分辨率核对</a> · <a href="convergence_summary.json">推荐方案核对</a></p></section>
<section><h2>模型与文件</h2><p>2T 多尺度模型：完整堆栈 TMM、两个子电池漂移扩散、共同电流串联；固定虚拟选择性内接触与 0.1 Ω·cm² 等效连接电阻，全局 Rs=0.3、Rsh=40000 Ω·cm²，Pin=100 mW/cm²，300–1100 nm。它不预测实际中间 n/p 接触是否形成有效隧穿或复合连接。</p>
<p>掺杂与真实材料缺陷、迁移率、Auger 复合、简并统计及组分变化的联动未在此次模型中标定。当前推荐值最高 1e17，为 Nc=Nv=3e18 的约 3.3%；高掺杂探索的上限为 3e17。钙钛矿 n,k 和 NiOx 的 PTAA 光学代理沿用原输入。所有结果都是既定模型的数值比较，不能直接当作实验效率预测。</p>
<p>参数库另收录推荐方案和同网格基准，历史结构未覆盖。完整原生 JSON（gzip）通过 <a href="https://github.com/mumium/perovskite-device-studio/releases/tag/v1.5.1">v1.5.1 发布页的数据包</a> 提供；曲线、参数、汇总、复现脚本在仓库本目录。报告及图片可离线查看。</p></section></html>'''
    (HERE/'报告.html').write_text(html,encoding='utf-8')
    print(json.dumps(final,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
