from scan import *
import hashlib,base64,html,shutil,zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from perovskite_studio.performance import loss_at_voltage
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False,'svg.fonttype':'none'})
figs=OUT/'figures';figs.mkdir(exist_ok=True)
rows=[];audit=[]
for phase in ('absorber','contacts','fine','gradient','grid1500','grid2000','halfstep','gradient24'):
 for f in sorted((OUT/phase).glob('*.json')):
  if '.error.' in f.name:continue
  r=read(f);m=r['metrics'];v=np.array(r['voltage']);j=np.array(r['current']);x=np.unique(np.r_[np.linspace(0,m['Voc'],100001),v[(v>=0)&(v<=m['Voc'])]])
  delta=float(np.max(x*np.interp(x,v,j))-m['PCE']);assert abs(delta)<2e-5 and r['relative_current_error']<.005
  audit.append(dict(file=str(f.relative_to(OUT)),PCE_delta=delta,current_error=r['relative_current_error']))
  rows.append(dict(phase=phase,case=f.stem,metrics=m,generated_current=r['generated_current']))
save(OUT/'扫描指标.json',rows);save(OUT/'数值核对.json',audit)
def figsave(fig,name):
 fig.tight_layout()
 for ext in ('png','svg'):fig.savefig(figs/(name+'.'+ext),dpi=170,bbox_inches='tight')
 p=figs/(name+'.svg');p.write_text('\n'.join(s.rstrip() for s in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,d,title in zip(axs,('direct','graded_np'),('结构一：400 / 800 nm','结构二：380 / 20n / 20p / 780 nm')):
 for case,label in [('previous','上次价带匹配'),('fine_best','本次联合能级优化'),('fine_best_quality','本次能级 + 沿用质量假设')]:
  r=read(OUT/'grid2000'/f'{d}_{case}.json');ax.plot(r['voltage'],r['current'],label=label)
 ax.set(xlim=(.65,1.02),ylim=(-1,33),xlabel='电压 / V',ylabel='电流密度 / mA/cm²',title=title);ax.grid(alpha=.2);ax.legend(fontsize=8)
figsave(fig,'JV放大对比')
fig,ax=plt.subplots(figsize=(8,4))
configs=read(OUT/'absorber_configs.json')[:-1];data=np.array([read(OUT/'absorber'/f"direct_{c['id']}.json")['metrics']['PCE'] for c in configs]).reshape(7,7)
im=ax.imshow(data,origin='lower',aspect='auto',extent=(-.175,.175,3.55,4.25),cmap='viridis');fig.colorbar(im,ax=ax,label='效率 / %');ax.set(xlabel='宽层价带深度 − 窄层价带深度 / eV',ylabel='窄层电子亲和能 / eV',title='吸收层能级粗扫：500网格、原接触设置')
figsave(fig,'能级扫描')
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,case,title in zip(axs,('previous','fine_best'),('上次方案：材料带边','本次推荐：材料带边')):
 c=next(c for c in read(OUT/'selected_configs.json') if c['id']==case);p=project('direct',c,2000,32,.01);x=0
 for l in p['layers']:
  ax.plot([x,x+l['thickness']],[-l['chi']]*2,color='#007aff');ax.plot([x,x+l['thickness']],[-l['chi']-l['Eg']]*2,color='#af52de');ax.axvline(x,color='gray',alpha=.3);x+=l['thickness']
 ax.set(xlabel='位置 / nm',ylabel='真空参考能量 / eV',ylim=(-6.5,-.8),title=title);ax.text(440,-1.65,'蓝：导带；紫：价带\n未叠加电势弯曲',fontsize=9,va='top')
figsave(fig,'材料能级对比')
best=read(OUT/'selected_configs.json')[0];changes={};losses={}
for d in ('direct','graded_np'):
 p=project(d,best,2000,32,.01);base=project(d,dict(id='previous',nchi=3.9,offset=0),2000,32,.01);diff=[]
 assert len(p['layers'])==len(base['layers'])
 for idx,(a,b) in enumerate(zip(base['layers'],p['layers'])):
  for k in a:
   if a[k]!=b[k]:assert k in ('chi','chi_end');diff.append(dict(layer=idx+1,field=k,before=a[k],after=b[k]))
 for k in base['settings']:
  if base['settings'][k]!=p['settings'][k]:assert k in ('left','right');diff.append(dict(field=k,before=base['settings'][k],after=p['settings'][k]))
 changes[d]=diff
 save(OUT/'parameters'/f'{d}_能级联合优化.json',p)
 cq=dict(best,id='fine_best_quality',quality=True);save(OUT/'parameters'/f'{d}_能级优化_沿用质量假设.json',project(d,cq,2000,32,.01))
 losses[d]={}
 for case in ('previous','fine_best'):
  r=read(OUT/'grid2000'/f'{d}_{case}.json');losses[d][case]=dict(short_circuit=loss_at_voltage(r,0),mpp=loss_at_voltage(r,r['metrics']['Vmp']),voc=loss_at_voltage(r,r['metrics']['Voc']))
save(OUT/'参数差异.json',changes);save(OUT/'工作点损失.json',losses)
save(OUT/'来源与约束.json',dict(input='research/2026-11-13/02_extended_optics/parameters',core={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['perovskite_studio/performance.py','perovskite_studio/optics.py','vendor/simsalabim/simss.exe']},valid_runs=len(rows),constraints='no interconnect; same thickness/Eg/doping/optics; primary comparison fixed mobility=2, lifetime=100us, B=1e-10'))
def table(items):
 s='<div class="table"><table><tr><th>条件</th><th>Jsc / mA/cm²</th><th>Voc / V</th><th>FF / %</th><th>效率 / %</th></tr>'
 for label,m in items:s+='<tr><td>'+html.escape(label)+'</td>'+''.join(f'<td>{m[k]:.5f}</td>' for k in ('Jsc','Voc','FF','PCE'))+'</tr>'
 return s+'</table></div>'
main=[];numerical=[]
for d in ('direct','graded_np'):
 for case,label in [('previous','上次价带匹配'),('fine_best','本次联合能级'),('gradient_best','亲和能渐变参考'),('fine_best_quality','本次+沿用质量假设')]:main.append((d+' / '+label,read(OUT/'grid2000'/f'{d}_{case}.json')['metrics']))
 for phase,case in [('grid1500','fine_best'),('grid2000','fine_best'),('halfstep','fine_best'),('gradient24','gradient_best')]:numerical.append((d+' / '+phase,read(OUT/phase/f'{d}_{case}.json')['metrics']))
images=''.join('<img alt="'+n+'" src="data:image/png;base64,'+base64.b64encode((figs/(n+'.png')).read_bytes()).decode()+'">' for n in ('JV放大对比','能级扫描','材料能级对比'))
body='''<h1>双层钙钛矿能级再优化</h1><p>2026-11-14。保持两种层结构、厚度、Eg、掺杂、AM1.5G与300–1100 nm n/k，未加互联层。主比较μ=2 cm²/(V·s)、τ=100 μs、B=1E-10 cm³/s、Rs=0.3、Rsh=40000均不变。只优化χ与电极功函数，原参数全部保留。</p>
<h2>推荐均匀能级设计</h2><p>宽层χ=3.42 eV（Ec=-3.42、Ev=-5.20）；窄层χ=4.00（Ec=-4.00、Ev=-5.25）。宽层价带比窄层高0.05 eV，避免此前向左收集空穴时的0.43 eV反向台阶。NiOx位置的传输层χ=1.45、Eg=3.8（Ev=-5.25）；C60位置的传输层χ=3.80、Eg=2.1。左电极功函数5.20、右3.85 eV。结构二的n层跟随宽层χ，p层跟随窄层χ，20 nm层的掺杂渐变不变。</p>
<p>这些是理论能级设计目标，不代表原NiOx/C60或钙钛矿样品已经具备这些参数。实现它们需要合适的材料或能级调控，并重新测量确认；本轮没有模拟新增材料层。固定带隙及n/k是隔离能级因素的灵敏度假设，真实材料改变后须复核光学输入。</p>
<h2>主结果：2000网格、32分段、0.01 V</h2>'''+table(main)+'''
<p>本次均匀方案约24.71%、FF约85.45%，比上次仅价带匹配约24.35%增加约0.36个百分点。Voc约0.9196 V，未明显提高。梯度参考的微小优势仅约0.002–0.003个百分点，小于本轮网格/步长变化，不作为已证实的结构优势，优先推荐均匀方案。</p>
<p>“沿用质量假设”单独保持上次μ=20、τ=1ms的假设，再应用本次能级；约24.93%，对照上次同质量条件约24.88%，改善约0.05个百分点。该行不与μ=2的主结果混作同条件提升，不额外降低B、Nt或界面缺陷。</p>
<h2>扫描范围与证据</h2><p>吸收层扫描窄层χ=3.6–4.2 eV（0.1步长）、宽/窄价带深度差-0.15至+0.15 eV（0.05步长），50组含上次方案；传输层/接触联合扫描40组；局部能级细扫36组；线性亲和能渐变16组。粗扫500网格、16分段、0.02V，渐变筛查700网格、12分段；跨网格不能直接比较小幅差异，最终候选同2000/32/0.01核验。完整指标与配置JSON保留。</p>
<p>升高部分势垒可以抬高Voc，但牺牲FF与输出功率；本次按效率并兼顾FF选取。当前共享外接触的双吸收层模型没有产生两个独立子电池的有效电压叠加。本轮仍未达30%，不以手动设置更高Voc或不受约束改变复合常数来报告目标效率。</p>'''+images+'''
<h2>数值与软件核对</h2>'''+table(numerical)+'''
<p>grid1500/grid2000使用0.01V；halfstep为2000/32/0.005V；gradient24为2000/24/0.01V的渐变参考检查。均匀方案1500→2000效率变化低于0.010个百分点，减半电压步长变化约0.010个百分点，故报告约24.71%。各有效结果独立复算Pmax并检查电流守恒；主推荐两个项目在实际软件页面重载运行，核对四指标。光生积分应与原光学输入一致，能级变化没有提高入射功率或光生率。G与复合损失见原生输出及工作点损失JSON。</p>
<h2>使用与复现</h2><p>parameters含两种结构的均匀能级项目，以及单独注明“沿用质量假设”的版本。直接在器件性能页打开。scan.py为扫描驱动，check.py为核验，report.py生成报告；完整发布包解压到源码仓库results/本研究目录后可复现。本研究不修改软件求解代码，未重新计算EQE。上次文献n/k的代理材料及NiOx/PTAA光学映射限制依然成立。来源为本仓库前两次研究的自包含参数与SimSS原生求解结果。</p>'''
(OUT/'能级再优化报告.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>能级再优化</title><style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1140px;margin:26px auto;padding:0 20px;color:#202124}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}.table{overflow:auto}h2{margin-top:32px}</style>'+body,encoding='utf-8')
cur=ROOT/'research/2026-11-14/02_band_alignment';cur.mkdir(parents=True,exist_ok=True)
for name in ('parameters','figures'):shutil.copytree(OUT/name,cur/name,dirs_exist_ok=True)
for name in ['能级再优化报告.html','扫描指标.json','数值核对.json','参数差异.json','工作点损失.json','来源与约束.json','软件实算核对.json','scan.py','check.py','report.py','direct_软件核对.png','graded_np_软件核对.png']+[p.name for p in OUT.glob('*_configs.json')]:shutil.copy2(OUT/name,cur/name)
readme='# 能级再优化（无互联层）\n\n打开 [完整报告](能级再优化报告.html)。主方案保留μ=2、τ=100μs及原复合常数，推荐均匀χ设计：宽3.42、窄4.00、HTL1.45、ETL3.80、左右功函数5.20/3.85 eV。效率约24.71%、FF约85.45%，Voc约0.92 V。未达30%。这些是待材料验证的设计目标。\n\n参数在parameters；“沿用质量假设”文件另保留上次μ=20、τ=1ms条件，效率约24.93%，不可与主方案混作同条件比较。完整源数据见 [研究发布](https://github.com/mumium/perovskite-device-studio/releases/tag/research-2026-11-14-energy)。\n'
(OUT/'README.md').write_text(readme,encoding='utf-8');(cur/'README.md').write_text(readme,encoding='utf-8')
for d,label in [('direct','结构一'),('graded_np','结构二')]:shutil.copy2(OUT/'parameters'/f'{d}_能级联合优化.json',ROOT/'device_structures'/f'2026-11-14_{label}_能级联合优化.json')
release=ROOT/'build/research-2026-11-14-energy';release.mkdir(parents=True,exist_ok=True);z=release/'band-alignment-2026-11-14.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
 for p in OUT.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:f.write(p,p.relative_to(OUT))
with zipfile.ZipFile(z) as f:assert f.testzip() is None
(release/'SHA256SUMS.txt').write_text(hashlib.sha256(z.read_bytes()).hexdigest()+'  '+z.name+'\n',encoding='utf-8')
print('REPORT VERIFIED',len(rows),'valid runs','ZIP',z.stat().st_size,flush=True)
