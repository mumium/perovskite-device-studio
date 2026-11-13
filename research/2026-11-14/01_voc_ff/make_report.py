from run_diagnosis import *
import hashlib,base64,html,shutil,zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False,'svg.fonttype':'none'})
def read(p):return json.loads(p.read_text(encoding='utf-8'))
rows=[];audit=[]
for path in sorted(OUT.glob('grid*/*.json')):
 if '.error.' in path.name:continue
 r=read(path);grid=int(path.parent.name[4:]);stem=path.stem;design='graded_np' if stem.startswith('graded_np') else 'direct';case=stem[len(design)+1:]
 m=r['metrics'];v=np.asarray(r['voltage']);j=np.asarray(r['current']);dense=np.unique(np.r_[np.linspace(0,m['Voc'],100001),v[(v>=0)&(v<=m['Voc'])]]);power=dense*np.interp(dense,v,j);pce=float(max(power))
 assert abs(pce-m['PCE'])<2e-5 and r['relative_current_error']<.005
 audit.append(dict(file=str(path.relative_to(OUT)),dense_PCE=pce,delta=pce-m['PCE'],current_error=r['relative_current_error']))
 rows.append(dict(grid=grid,design=design,case=case,metrics=m,loss_sc=loss_at_voltage(r,0),loss_mpp=loss_at_voltage(r,m['Vmp']),loss_voc=loss_at_voltage(r,m['Voc'])))
for design in ('direct','graded_np'):
 base=project(design,'baseline',2000)
 for case in ('align','align_quality'):
  new=project(design,case,2000);assert len(base['layers'])==len(new['layers']) and base['settings']==new['settings']
  changes=[]
  for idx,(a,b) in enumerate(zip(base['layers'],new['layers'])):
   for k in a:
    if a[k]!=b[k]:
     assert (k in ('chi','chi_end') and a['Eg']==1.78) or (case=='align_quality' and a['absorber'] and k in ('mun','mup','taun','taup'))
     changes.append(dict(layer=idx+1,parameter=k,before=a[k],after=b[k]))
  save(OUT/'changes'/f'{design}_{case}.json',changes)
save(OUT/'核对记录.json',audit);save(OUT/'指标与工作点损失.json',rows)
figdir=OUT/'figures';figdir.mkdir(exist_ok=True)
def figure(name,fig):
 fig.tight_layout();fig.savefig(figdir/(name+'.png'),dpi=170,bbox_inches='tight');fig.savefig(figdir/(name+'.svg'),bbox_inches='tight');plt.close(fig)
 p=figdir/(name+'.svg');p.write_text('\n'.join(s.rstrip() for s in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,design,title in zip(axs,('direct','graded_np'),('结构一：400 / 800 nm','结构二：380 / 20n / 20p / 780 nm')):
 for case,label,color in [('baseline','原参数','#8e8e93'),('align','仅价带匹配','#007aff'),('align_quality','匹配 + 假设提高迁移率/寿命','#b35a00')]:
  r=read(OUT/'grid2000'/f'{design}_{case}.json');ax.plot(r['voltage'],r['current'],label=label,color=color)
 ax.set(xlim=(0,1.4),ylim=(-2,35),xlabel='电压 / V',ylabel='电流密度 / mA/cm²',title=title);ax.grid(alpha=.2);ax.legend(fontsize=8)
figure('JV诊断对比',fig)
fig,axs=plt.subplots(1,2,figsize=(10,3.8))
for ax,case,title in zip(axs,('baseline','align'),('原参数：空穴跨越 0.43 eV 台阶','设计方案：价带连续')):
 p=project('direct',case,2000);x=0
 for a in p['layers']:
  xx=[x,x+a['thickness']];ax.plot(xx,[-a['chi']]*2,color='#007aff');ax.plot(xx,[-a['chi']-a['Eg']]*2,color='#af52de');ax.axvline(x,color='gray',alpha=.25);x=xx[-1]
 ax.set(title=title,xlabel='位置 / nm',ylabel='真空参考能量 / eV',ylim=(-6.5,0));ax.text(450,-1.2,'未加电势弯曲的材料带边\n蓝：导带；紫：价带',fontsize=8)
figure('材料能级台阶',fig)
fig,ax=plt.subplots(figsize=(8,4))
labels=[];photo=[];rec=[];collected=[]
for case,label in [('baseline','原参数'),('align','仅价带匹配'),('align_quality','匹配+质量假设')]:
 r=next(r for r in rows if r['grid']==2000 and r['design']=='direct' and r['case']==case);l=r['loss_mpp'];labels.append(label);photo.append(l['photo']);rec.append(l['direct']+l['bulk']);collected.append(l['collected'])
x=np.arange(3);ax.bar(x-.24,photo,.24,label='原生光生参考');ax.bar(x,rec,.24,label='体SRH+双分子净复合');ax.bar(x+.24,collected,.24,label='输出电流');ax.set(xticks=x,xticklabels=labels,ylabel='最大功率点等效电流 / mA/cm²');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
figure('最大功率点损失',fig)
def table(items):
 s='<table><tr><th>结构/条件</th><th>Jsc / mA/cm²</th><th>Voc / V</th><th>FF / %</th><th>效率 / %</th></tr>'
 for name,m in items:s+=f'<tr><td>{html.escape(name)}</td>'+''.join(f'<td>{m[k]:.4f}</td>' for k in ('Jsc','Voc','FF','PCE'))+'</tr>'
 return s+'</table>'
main=[]
for design in ('direct','graded_np'):
 for case,label in [('baseline','原参数'),('align','仅价带匹配'),('align_quality','匹配+质量假设')]:main.append((design+' / '+label,read(OUT/'grid2000'/f'{design}_{case}.json')['metrics']))
controls=[(r['case'],r['metrics']) for r in rows if r['grid']==600 and r['design']=='direct']
images=''.join('<img alt="'+name+'" src="data:image/png;base64,'+base64.b64encode((figdir/(name+'.png')).read_bytes()).decode()+'">' for name in ('JV诊断对比','材料能级台阶','最大功率点损失'))
body='''<h1>Voc / FF 损失诊断与无互联层优化</h1><p>2026-11-14。保持两种层结构、厚度、带隙、掺杂及300–1100 nm文献光学输入，不新增互联层。原方案冻结保留。</p>
<h2>结论与实现</h2><p>主因是能级选择导致的收集势垒：宽带隙Ec/Ev=-3.80/-5.58 eV，窄带隙Ec/Ev=-3.90/-5.15 eV。窄层空穴向左收集遇到约0.43 eV价带台阶，导致积累、双分子复合及随电压变化的收集损失。未施加电势弯曲的带边示意只用于材料偏移，不是求解后的能带图。</p>
<p>另存“仅匹配”参数：宽带隙χ从3.80改为3.37 eV，使Ev=-5.15 eV；结构二对应n渐变层也同步修改χ。窄层及p层χ保持3.90，所有其余物理参数不变。此为待材料实现和测量验证的设计假设，不能当作原χ参数填错或已证实的材料性质；固定Eg/n,k是电学灵敏度分析，实际配方改变后需重新标定。</p>
<p>另存“质量假设”参数，在匹配基础上将全部钙钛矿μn/μp从2提高至20 cm²/(V·s)，τn/τp从100 μs提高至1 ms。没有改变B=1E-10 cm³/s、缺陷密度、接触选择性、Rs/Rsh或光生率。原Nt/τ映射为俘获系数，τ增加等价于降低俘获系数，并非另改缺陷密度。</p>
<h2>主结果：2000网格，32分段，0.01 V</h2>'''+table(main)+'''
<p>FF已改善，但Voc没有提高：匹配后约0.92 V。原结构仅宽层光生的诊断Voc≈1.304 V，与原完整结构1.305 V很接近；仅窄层光生时Jsc≈0.014 mA/cm²，印证窄层几乎未参与有效收集。光生开关只用于机制诊断，未用于最终参数。</p>
<p>当前是共享外接触的双吸收层异质结，求解器没有把它自动变成两个电压相加的独立子电池。不能以“1.78+1.25 eV”给这个结构设定目标Voc。原较高Voc伴随窄层载流子阻塞，并非已经获得高功率的电压叠加。在本轮保持无互联层的约束和参数扫描范围内，没有得到同时提高原Voc和FF的方案，也没有达到30%；不能保证所有可能材料设计都受此数值上限限制。</p>
<h2>单因素与能级扫描：600网格筛查，非主精度结果</h2>'''+table(controls)+'''
<p>resistance：Rs=0、Rsh=1E9；contacts：功函数左5.1/右4.0 eV；mobility：μ=20；lifetime：τ=1ms；B_control：B降10倍，仅作灵敏度诊断，未选作修复。partial_align：χ=3.60；chi_x：宽层χ扫描。均与同网格baseline比较。原接触已经设置理想少数载流子阻挡、界面Nt=0，不能再将它们当作可消除的主损失。降低B并非无代价的材料修复。</p>
<h2>图与核对</h2>'''+images+'''
<p>1500→2000网格，仅匹配效率变化：结构一约0.0059个百分点、结构二约0.0098个百分点。另有软件页面重新加载并运行四个项目、独立密集电压采样复算Pmax、原生电流守恒和逐字段参数差异核对。3000点被现有软件2000点输入上限拒绝，未作为有效结果。损失取SimSS原生积分：残差含边界和离散项，不将其直接命名为纯接触复合。完整记录见JSON。此次未重新运行EQE，旧EQE不代表优化参数。</p>
<h2>复现与资料</h2><p>parameters中提供direct/graded_np各自的align和align_quality项目，n/k均内嵌，可在器件性能模拟页直接打开。grid目录是原生完整结果，changes列出准确修改字段，run_diagnosis.py可从上一研究的自包含参数重算。软件求解代码未修改，所有改善来自明确记录的器件设计参数。</p>
<p>物理背景：<a href="https://pubs.acs.org/doi/10.1021/acs.jpcc.7b05517">单片钙钛矿叠层研究：复合连接用于子电池电压叠加</a>。引用只解释电压叠加条件，本方案未引入该层。光学数据来源、代理材料限制和NiOx/PTAA映射沿用前一研究，未新增实验标定。</p>'''
(OUT/'Voc_FF诊断与优化报告.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Voc与FF诊断</title><style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1150px;margin:28px auto;padding:0 20px;color:#202124}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}img{width:100%;height:auto}h2{margin-top:32px}</style>'+body,encoding='utf-8')
save(OUT/'来源与指纹.json',dict(source='research/2026-11-13/02_extended_optics/parameters',core={str(p):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [Path('perovskite_studio/performance.py'),Path('perovskite_studio/optics.py'),Path('vendor/simsalabim/simss.exe')]},valid_runs=len(rows)))
cur=ROOT/'research/2026-11-14/01_voc_ff';cur.mkdir(parents=True,exist_ok=True)
for name in ['parameters','changes','figures']:
 shutil.copytree(OUT/name,cur/name,dirs_exist_ok=True)
for name in ['Voc_FF诊断与优化报告.html','指标与工作点损失.json','核对记录.json','软件实算核对.json','来源与指纹.json','direct_软件核对.png','graded_np_软件核对.png','run_diagnosis.py','verify_ui.py','make_report.py']:
 shutil.copy2(OUT/name,cur/name)
readme='# 无互联层的Voc / FF诊断与设计优化\n\n打开 [报告](Voc_FF诊断与优化报告.html)。仅能级匹配将FF改善至约84%、效率约24.35%，Voc下降至约0.92 V；附加迁移率/寿命假设效率约24.88%。未达到30%，未新增互联层。\n\n参数在parameters，所有n/k内嵌。χ=3.37是待材料实现的设计假设，原χ=3.8参数保留。完整原生数据和脚本见 [研究发布](https://github.com/mumium/perovskite-device-studio/releases/tag/research-2026-11-14-voc-ff)。\n'
(OUT/'README.md').write_text(readme,encoding='utf-8');(cur/'README.md').write_text(readme,encoding='utf-8')
for design,label in [('direct','结构一'),('graded_np','结构二')]:
 for case,desc in [('align','价带匹配设计'),('align_quality','价带匹配与质量假设')]:shutil.copy2(OUT/'parameters'/f'{design}_{case}.json',ROOT/'device_structures'/f'2026-11-14_{label}_{desc}.json')
release=ROOT/'build/research-2026-11-14-voc-ff';release.mkdir(parents=True,exist_ok=True)
z=release/'voc-ff-diagnosis-2026-11-14.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
 for p in OUT.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:f.write(p,p.relative_to(OUT))
with zipfile.ZipFile(z) as f:assert f.testzip() is None
(release/'SHA256SUMS.txt').write_text(hashlib.sha256(z.read_bytes()).hexdigest()+'  '+z.name+'\n',encoding='utf-8')
print('REPORT VERIFIED',len(rows),'valid runs','ZIP',z.stat().st_size,flush=True)
