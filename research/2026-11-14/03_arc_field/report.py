from run import *
import base64,hashlib,shutil,zipfile,html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from perovskite_studio.performance import loss_at_voltage
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False,'svg.fonttype':'none'})
excluded=[f'peak/graded_np_peak_{i}.json' for i in range(5)]
save(OUT/'排除记录.json',dict(files=excluded,reason='早期驱动按无空格层名匹配，未实际改变peak；五组是重复基线，未用于峰值浓度结论。已按层厚度和带隙识别，validated_peak五组重新计算并核对实际端点。'))
configs={phase:read(OUT/f'{phase}_configs.json') for phase in ['doping','peak','energy','arc','index','refine','thickness','thin_arc']}
rows=[];checks=[]
for phase in list(configs)+['grid2000','grid1500','halfstep']:
 for f in sorted((OUT/phase).glob('*.json')):
  if '.error.' in f.name or str(f.relative_to(OUT)).replace('\\','/') in excluded:continue
  r=read(f);m=r['metrics'];v=np.array(r['voltage']);j=np.array(r['current']);xx=np.unique(np.r_[np.linspace(0,m['Voc'],100001),v[(v>=0)&(v<=m['Voc'])]])
  pd=float(max(xx*np.interp(xx,v,j))-m['PCE']);assert abs(pd)<2e-5 and r['relative_current_error']<.005
  x=np.array(r['optics']['x_nm']);g=np.array(r['optics']['G_cm3_s']);gg=float(1.602176634e-19*np.trapezoid(g,x*1e-7)*1000);assert abs(gg-r['generated_current'])<1e-9
  if phase=='peak':
   ix=int(f.stem.rsplit('_',1)[1]);n=configs['peak'][ix]['peak'];assert r['layers'][2]['Nd_end']==n and r['layers'][3]['Na']==n
  rows.append(dict(phase=phase,case=f.stem,metrics=m,generated_current=gg));checks.append(dict(file=str(f.relative_to(OUT)),dense_PCE_delta=pd,current_error=r['relative_current_error'],G_integral_delta=gg-r['generated_current']))
save(OUT/'扫描指标.json',rows);save(OUT/'独立数值核对.json',checks)
changes={};loss={}
for d in ('direct','graded_np'):
 base=project(d,dict(id='base'),2000,.01);arc=project(d,dict(id='arc85',arc_nm=85.),2000,.01)
 assert base['layers']==arc['layers']
 assert {k:v for k,v in base['settings'].items() if k!='optics'}=={k:v for k,v in arc['settings'].items() if k!='optics'}
 assert {k:v for k,v in base['settings']['optics'].items() if k not in ('tco','tco_thickness')}=={k:v for k,v in arc['settings']['optics'].items() if k not in ('tco','tco_thickness')}
 changes[d]=dict(only_ARC_changed=True,front_before='Air, 200nm',front_after='SiO2, 85nm',electrical_layers_unchanged=True,interconnect_added=False)
 loss[d]={}
 for case in ('base','arc85','thin50','thin50_quality_rs01'):
  r=read(OUT/'grid2000'/f'{d}_{case}.json');loss[d][case]=dict(sc=loss_at_voltage(r,0),mpp=loss_at_voltage(r,r['metrics']['Vmp']),voc=loss_at_voltage(r,r['metrics']['Voc']))
save(OUT/'修改范围核对.json',changes);save(OUT/'工作点损失.json',loss)
wl=np.array(arc['settings']['optics']['tco']['values']);assert wl[0,0]==300 and wl[-1,0]==1100 and np.all(wl[:,1]>1) and np.all(wl[:,2]==0)
u=.6328;n=np.sqrt(1+.6961663*u*u/(u*u-.0684043**2)+.4079426*u*u/(u*u-.1162414**2)+.8974794*u*u/(u*u-9.896161**2));assert abs(n-1.457018)<1e-6
save(OUT/'来源与指纹.json',dict(valid_runs=len(rows),SiO2=dict(url='https://opg.optica.org/josa/abstract.cfm?URI=josa-55-10-1205',doi='10.1364/JOSA.55.001205',range_um=[.21,3.71],used_nm=[300,1100],n_632_8nm=float(n),k='assumed zero, not measured k; transparent-film approximation',bulk_vs_film='bulk fused silica proxy; deposited film must be calibrated'),core={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['perovskite_studio/performance.py','perovskite_studio/optics.py','vendor/simsalabim/simss.exe']}))
figs=OUT/'figures';figs.mkdir(exist_ok=True)
def figsave(fig,name):
 fig.tight_layout()
 for ext in ('png','svg'):fig.savefig(figs/(name+'.'+ext),dpi=170,bbox_inches='tight')
 p=figs/(name+'.svg');p.write_text('\n'.join(s.rstrip() for s in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,d,title in zip(axs,('direct','graded_np'),('结构一','结构二')):
 for case,label in [('base','上次能级优化'),('arc85','原电学结构 + 减反膜'),('thin50','总厚度不变 + 宽侧50nm'),('thin50_quality_rs01','另加质量及Rs假设')]:
  r=read(OUT/'grid2000'/f'{d}_{case}.json');ax.plot(r['voltage'],r['current'],label=label)
 ax.set(xlim=(0,1.02),ylim=(-2,40),xlabel='电压 / V',ylabel='电流密度 / mA/cm²',title=title);ax.grid(alpha=.2);ax.legend(fontsize=8)
figsave(fig,'JV对比')
fig,axs=plt.subplots(1,2,figsize=(10,4))
cs=configs['arc'][1:];vals=[read(OUT/'arc'/f"direct_{c['id']}.json")['metrics']['PCE'] for c in cs];axs[0].plot([c['arc_nm'] for c in cs],vals,'o-');axs[0].set(xlabel='SiO2厚度 / nm',ylabel='效率 / %',title='固定400/800：减反膜粗扫（600点）')
for d,label in [('direct','直接接触'),('graded_np','保留20n/20p')]:axs[1].plot([c['wide_total'] for c in configs['thickness']],[read(OUT/'thickness'/f"{d}_{c['id']}.json")['metrics']['PCE'] for c in configs['thickness']],'o-',label=label)
axs[1].set(xlabel='宽带隙部分总厚度 / nm',ylabel='效率 / %',title='钙钛矿总厚度1200nm，ARC85nm（600点）');axs[1].legend()
for ax in axs:ax.grid(alpha=.2)
figsave(fig,'减反和厚度扫描')
fig,ax=plt.subplots(figsize=(8,4))
for case,label in [('base','原入光面'),('arc85','SiO2 85nm')]:
 r=read(OUT/'grid2000'/f'direct_{case}.json');ax.plot(r['optics']['x_nm'],np.array(r['optics']['G_cm3_s'])/1e21,label=label)
ax.set(xlabel='器件内位置 / nm',ylabel='G / $10^{21}$ cm$^{-3}$ s$^{-1}$',title='原400/800结构的光生分布');ax.legend();ax.grid(alpha=.2);figsave(fig,'光生分布')
def table(items):
 s='<div class="table"><table><tr><th>条件</th><th>Jsc / mA/cm²</th><th>Voc / V</th><th>FF / %</th><th>效率 / %</th></tr>'
 for label,m in items:s+='<tr><td>'+html.escape(label)+'</td>'+''.join(f'<td>{m[k]:.4f}</td>' for k in ('Jsc','Voc','FF','PCE'))+'</tr>'
 return s+'</table></div>'
main=[];nums=[]
for d in ('direct','graded_np'):
 for case,label in [('base','A 上次能级优化'),('arc85','B 原厚度+减反'),('arc85_quality','B+沿用质量假设'),('thin50','C 薄宽层+减反'),('thin50_quality','C+沿用质量假设'),('thin50_quality_rs01','D 再降低Rs')]:main.append((d+' / '+label,read(OUT/'grid2000'/f'{d}_{case}.json')['metrics']))
 for phase in ('grid1500','grid2000','halfstep'):
  for case in ('arc85','thin50','thin50_quality_rs01'):nums.append((d+'/'+case+'/'+phase,read(OUT/phase/f'{d}_{case}.json')['metrics']))
images=''.join('<img alt="'+s+'" src="data:image/png;base64,'+base64.b64encode((figs/(s+'.png')).read_bytes()).decode()+'">' for s in ('JV对比','减反和厚度扫描','光生分布'))
body='''<h1>无互联层：电场、减反与厚度优化</h1><p>2026-11-14。继能级优化后，继续检查掺杂和更大能级范围，并独立考察入光面减反膜与厚度分配。所有方案保持原带隙、钙钛矿光学常数和100mW/cm² AM1.5G，不添加电学互联层。</p>
<h2>结果分档：2000网格、32分段、0.01V</h2>'''+table(main)+'''
<p>A是上次χ优化参数；B只把原前侧Air 200nm光学占位替换为SiO2 85nm，电学层、厚度、能级、掺杂、μ=2、τ=100μs、B=1E-10、Rs=0.3、Rsh=40000全部不变。结构一400/800、结构二380/20n/20p/780保留。效率约24.71→28.11%，主要提升来自光生参考31.44→35.70mA/cm²，而非人为改变入射功率或复合系数。</p>
<p>C另外改变厚度分配，总钙钛矿仍1200nm：结构一宽50/窄1150nm；结构二宽30/n20/p20/窄1130nm。原两层过渡区掺杂不变，宽带隙部分合计50nm、窄带隙合计1150nm。此为扫描下界候选，尚未证明全局最佳；50nm宽层的成膜、均匀覆盖和实物可制造性未建模。结果约28.44%，不是原400/800结构同条件结果。</p>
<p>质量假设单独沿用前次钙钛矿μn/μp=20cm²/(V·s)、τn/τp=1ms；D在C及质量假设上再令Rs=0.1Ω·cm²，约28.97%。Rs从0.3降至0.1是新增电阻设计目标，不是已测量实现。所有档均保持原B及Nt，不将改善功劳归到单一因素。尚未达到30%。</p>
<h2>减反膜如何建模</h2><p>利用软件“前透明电极”光学字段表示入光面薄膜，材料设自定义SiO2 n/k、厚度85nm。该字段在求解器中用于光学薄膜，不自动建立其电学输运：这里是外表面介质减反层，不处于两层钙钛矿之间。电极接触仍为原理想接触；模型未包含透明电极实际走线、绝缘膜与取电结构的兼容性或完整封装。不可将这一光学输入直接视作已完成的真实电极设计。</p>
<p>n来自<a href="https://opg.optica.org/josa/abstract.cfm?URI=josa-55-10-1205">Malitson 1965熔融石英Sellmeier公式</a>，原文范围0.21–3.71μm，本次只用0.30–1.10μm；632.8nm独立核对n≈1.457018。k=0是透明近似，不是作者提供的实测k。实物沉积SiO2膜须重新标定；前次NiOx/PTAA代理光学映射及钙钛矿按带隙选取代理组成的限制仍成立。85nm是80–90nm较宽平台中的圆整设计值，不声称亚纳米精确最优。</p>
<h2>电学探索为什么收益小</h2><p>扩大能级范围的25组、均匀区域掺杂极性/浓度对照42组以及原n/p峰值扫描5组，没有在同网格上找到显著超过原电学最优的方案。掺杂极性对照会把所有同带隙吸收区域设为统一p或n型、取消该对照中的原梯度，仅用于机制探索，不作为最终推荐。峰值扫描保留20n/20p角色及渐变，仅变中间浓度1E14–1E18，已逐个核对实际端点。早期五组未实际改动参数的重复基线列入排除记录，不计有效浓度扫描。</p>
<p>原最优器件开路时双分子净复合约31.11mA/cm²，远大于SRH约0.30；最大功率点双分子约0.91、SRH约0.05。继续仅延长SRH寿命收益有限。掺杂可同时影响电场、载流子浓度及复合，不能靠无限增大掺杂抬高效率；相关机制见<a href="https://pubs.rsc.org/en/content/articlehtml/2022/mh/d2mh00008c">锡钙钛矿掺杂与复合实验研究</a>。这里引用机制，不把文献中的不同材料数值当作本器件标定。</p>
<p>恒定n、k=0的25组折射率扫描只是理想诊断，没有把其中的虚拟材料当作实测材料。总厚度保持1200nm的18组厚度扫描偏向更薄宽层，说明当前无有效电压叠加的模型更接近双吸收层单结；不能以本轮结果证明成熟全钙叠层的优势，也不能直接把两个带隙相加作为Voc目标。</p>'''+images+'''
<h2>网格、步长和实算核对</h2>'''+table(nums)+'''
<p>grid1500/grid2000使用0.01V；halfstep为2000网格、0.005V。以相同物理参数比较，差异见表，不能跨网格直接比较粗扫的小收益。主推荐B/C/D的六个自包含参数已在真实软件页面分别重载运行并核对Jsc/Voc/FF/PCE。每组有效结果独立密集采样复算Pmax、检查电流守恒，并独立积分原生G(x)。源数据保留每次J–V、G(x)及工作点损失；排除的无变化试算不进入图表。此次未重新运行EQE，旧EQE不能用作新减反结构EQE。</p>
<h2>复现与文件</h2><p>parameters内arc85保留原厚度、thin50改变宽窄厚度、thin50_quality_rs01另加材料质量及电阻假设。均可在器件性能页直接打开；n/k内嵌。将完整包解压到软件源码仓库results/本研究目录，run.py可按阶段重算，verify.py核验，report.py生成报告。所有原参数保留；软件求解代码未修改。</p>'''
(OUT/'进一步优化报告.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>进一步优化</title><style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1140px;margin:26px auto;padding:0 20px;color:#202124}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}.table{overflow:auto}h2{margin-top:32px}</style>'+body,encoding='utf-8')
cur=ROOT/'research/2026-11-14/03_arc_field';cur.mkdir(parents=True,exist_ok=True)
for name in ('parameters','figures'):shutil.copytree(OUT/name,cur/name,dirs_exist_ok=True)
for name in ['进一步优化报告.html','扫描指标.json','独立数值核对.json','修改范围核对.json','来源与指纹.json','工作点损失.json','排除记录.json','软件核对.json','run.py','verify.py','report.py','direct_软件实算.png','graded_np_软件实算.png']+[p.name for p in OUT.glob('*_configs.json')]:shutil.copy2(OUT/name,cur/name)
readme='# 电场、入光面减反与厚度优化（无互联层）\n\n打开 [报告](进一步优化报告.html)。保留原电学结构，加85nm SiO2光学减反层后效率约28.11%；总1200nm下宽侧改50nm约28.44%；再沿用μ=20/τ=1ms并令Rs=0.1的额外假设约28.97%。各档分开比较，尚未达到30%。\n\n参数分别为arc85、thin50和thin50_quality_rs01。SiO2为Malitson1965熔融石英n色散、k=0近似，实物膜及电极取电方式未校准。完整源数据见 [研究发布](https://github.com/mumium/perovskite-device-studio/releases/tag/research-2026-11-14-arc)。\n'
(OUT/'README.md').write_text(readme,encoding='utf-8');(cur/'README.md').write_text(readme,encoding='utf-8')
for d,label in [('direct','结构一'),('graded_np','结构二')]:shutil.copy2(OUT/'parameters'/f'{d}_arc85.json',ROOT/'device_structures'/f'2026-11-14_{label}_原厚度_85nm减反.json')
release=ROOT/'build/research-2026-11-14-arc';release.mkdir(parents=True,exist_ok=True);z=release/'arc-field-optimization-2026-11-14.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
 for p in OUT.rglob('*'):
  rel=str(p.relative_to(OUT)).replace('\\','/')
  if p.is_file() and '__pycache__' not in p.parts and rel not in excluded:f.write(p,p.relative_to(OUT))
with zipfile.ZipFile(z) as f:assert f.testzip() is None
(release/'SHA256SUMS.txt').write_text(hashlib.sha256(z.read_bytes()).hexdigest()+'  '+z.name+'\n',encoding='utf-8')
print('REPORT VERIFIED',len(rows),'valid runs','ZIP',z.stat().st_size,flush=True)
