"""Recheck the requested 2T tandem only, holding inner contacts fixed."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import csv,gzip,json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import study as s


def main():
    rows=[]
    if '--report-only' in sys.argv[1:]:
        rows=json.loads((s.HERE/'tandem_only_summary.json').read_text(encoding='utf-8'))
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(s.conditional,f'fixed_dense_{n:.0e}',n,n,2000,40,.005,False)
                  for n in [1e16,1e17,3e17]]
            for f in as_completed(jobs):
                rows.append(f.result());s.save_json(s.HERE/'tandem_only_summary.json',rows)
    rows.sort(key=lambda x:x['nd_peak'])
    if not all(r['success'] for r in rows):raise RuntimeError('Incomplete tandem result; inspect summaries')
    folder=s.HERE/'conditional'
    validation=[]
    for row in rows:
        with gzip.open(folder/(row['name']+'_result.json.gz'),'rt',encoding='utf-8') as f:r=json.load(f)
        s.save_json(folder/(row['name']+'_subcells.json'),dict(subcells=r['subcells'],
                    workpoints=r['workpoints'],generation_audit=r['generation_audit'],
                    warnings=r['warnings'],engine_build=r.get('engine_build')))
        validation.append(dict(case=row['name'],model=r['model'],
            top_metrics=r['subcells']['top']['metrics'],bottom_metrics=r['subcells']['bottom']['metrics'],
            relative_current_error=r['relative_current_error'],
            max_power_balance_residual=max(abs(p['power_residual']) for p in r['workpoints'].values()),
            MPP=r['workpoints']['MPP']))
    s.save_json(s.HERE/'tandem_only_validation.json',validation)
    best=max(rows,key=lambda x:x['metrics']['PCE'])
    audit=next(v for v in validation if v['case']==best['name'])
    p=json.loads((folder/(best['name']+'_input.json')).read_text(encoding='utf-8'))
    s.save_json(s.ROOT/'device_structures/2026-11-16_中央高掺杂_np渐变_叠层性能重算.json',p)
    columns=['peak_cm3','Jsc','Voc','FF','PCE','Vmp','Jmp']
    with (s.HERE/'tandem_only_performance.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for row in rows:w.writerow(dict(peak_cm3=row['nd_peak'],**{k:row['metrics'][k] for k in columns[1:]}))
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False})
    fig,ax=plt.subplots(figsize=(7,4.6),layout='constrained')
    for row in rows:
        a=np.genfromtxt(folder/(row['name']+'_JV.csv'),delimiter=',',names=True)
        ax.plot(a['V_terminal_V'],a['J_output_mA_cm2'],label=f"中央峰值 {row['nd_peak']:.0e} cm$^{{-3}}$")
    ax.set(xlim=(0,2.4),ylim=(0,17),xlabel='叠层端电压 / V',ylabel='叠层输出电流 / (mA/cm²)',title='2T 叠层 J–V：保持相同连接及内接触设置')
    ax.grid(alpha=.2);ax.legend();fig.savefig(s.HERE/'figures/tandem_only_JV.png',dpi=160);plt.close(fig)
    table='\n'.join('| '+f"{r['nd_peak']:.0e}"+' | '+' | '.join(f"{r['metrics'][k]:.4f}" for k in ['Jsc','Voc','FF','PCE'])+' |' for r in rows)
    text=f'''# 中央高掺杂渐变层：2T叠层性能重算

本报告只以软件“叠层电池模拟”页的2T串联为结果：顶子电池NiOx/380nm宽带隙/20nm n层，底子电池20nm p层/780nm窄带隙/C60。相同电流下相加两子电池电压，再计一次外电路损失。没有使用整栈单域JV的11%–12%数值作为叠层结果。

保留两个主吸收层原均匀Nd=1e14、Na=0；只改变中央两层：n20nm的Nd从1e14升至中央峰值，p20nm的Na从中央峰值降至1e14。二者另一掺杂种类均为0。厚度、Eg/χ、材料质量、光学与外接触均保持原值，无减反膜、无独立新增互联材料。四个钙钛矿区域均产生光载流子。

| n/p中央峰值 / cm⁻³ | Jsc / mA cm⁻² | Voc / V | FF / % | PCE / % |
| --- | ---: | ---: | ---: | ---: |
{table}

![叠层JV](figures/tandem_only_JV.png)

三组均为2000空间点、40渐变分段、0.005V步长；AM1.5G 300–1100nm、100mW/cm²。采用相同固定虚拟内功函数3.95/5.00eV和面积连接电阻0.1Ωcm²，外Rs=0.3Ωcm²、Rsh=4e4Ωcm²。这样比较时不把内接触边界的改变算成纯掺杂收益。均通过现有生产路径完整成功计算及接受检查，没有采用失败的部分结果。

三组中最高为中央峰值{best['nd_peak']:.0e}：PCE={best['metrics']['PCE']:.4f}%。此前同条件1400点/24分段/0.01V的3e17结果为22.4732%，本次精细重算为{next(r for r in rows if r['nd_peak']==3e17)['metrics']['PCE']:.4f}%。最优仅指本次三个测试点，不代表已找到真实材料最优浓度。

该组顶/底子电池独立Voc分别为{audit['top_metrics']['Voc']:.6f}/{audit['bottom_metrics']['Voc']:.6f}V；经过全局并联与串联电阻后的叠层Voc为{best['metrics']['Voc']:.6f}V。最大功率点内部共同电流为{audit['MPP']['series_current']:.6f}mA/cm²，顶/底电压分别为{audit['MPP']['top_voltage']:.6f}/{audit['MPP']['bottom_voltage']:.6f}V，扣除连接与外串联电阻压降后端电压为{audit['MPP']['external_voltage']:.6f}V。这是同电流下的串联求解。子电池最大原生errJ/光生电流为{audit['relative_current_error']:.3g}，工作点功率收支残差最大{audit['max_power_balance_residual']:.3g}mW/cm²，均沿用原接受规则。详见tandem_only_validation.json。

另有一组3e17的**匹配理想内接触参考**已计算为Jsc15.4091mA/cm²、Voc2.1883V、FF74.4417%、PCE25.1011%；它还将虚拟功函数改为3.8595/5.0905eV，不能与上表当成纯掺杂对照。两种输入均已分开保存。

该2T页预设选择性内接触及等效中央连接，能给出叠层串联性能；它不从这两层掺杂和界面Nt自动求出真实隧穿复合能力。上述是明确连接假设下的叠层模型结果，不是实际n/p界面已高效连接的证明。没有为达到30%调整连接电阻或材料质量。

打开参数库“2026-11-16_中央高掺杂_np渐变_叠层性能重算.json”，必须在**叠层电池模拟**页打开并运行。它对应本表中最高的一组；其他组可按本脚本重算，全部JV、子电池曲线与工作点已随报告保存。当前1.5.1程序无需升级。

源数据：[性能CSV](tandem_only_performance.csv)、[精确汇总JSON](tandem_only_summary.json)；conditional/fixed_dense_*_JV.csv为串联输出，*_subcells.json为两个子电池JV、工作点、光生守恒及警告。完整输出JSON gzip另保留在本地同目录。复现：python research/2026-11-16/02_center_peak_np/tandem_only.py。单域物理机制诊断仍保留在[原报告](README.md)，与本2T性能报告区分。
'''
    (s.HERE/'叠层性能重算.md').write_text(text,encoding='utf-8')
    from report import render_report
    css='body{max-width:1000px;margin:32px auto;padding:0 24px;font:16px/1.8 "Microsoft YaHei",sans-serif;color:#223044}table{border-collapse:collapse;width:100%}td,th{padding:8px 14px;border:1px solid #dce4ee;text-align:right}img{max-width:100%}a{color:#176bc0}'
    (s.HERE/'叠层性能重算.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2T叠层性能重算</title><style>'+css+'</style><body>'+render_report(text)+'</body></html>',encoding='utf-8')
    print('TANDEM ONLY REPORT COMPLETE',flush=True)


if __name__=='__main__':main()
