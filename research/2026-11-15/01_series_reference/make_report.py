from run_reference import *
import base64,hashlib,shutil,zipfile,html
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False,'svg.fonttype':'none'})
figs=OUT/'figures';figs.mkdir(exist_ok=True)
summary=[];audits=[]
for grid in (1000,2000):
 for case in ('original_nk','aligned_ARC'):
  top=read(OUT/f'grid{grid}'/f'{case}_top.json');bottom=read(OUT/f'grid{grid}'/f'{case}_bottom.json')
  for rc in (0,.1,1,5):
   r=read(OUT/f'grid{grid}'/f'{case}_series_R{rc:g}.json');m=r['metrics'];source=read(OUT/'optical_sources'/f'{case}.json')
   assert abs(r['subcell_source_G_sum']-source['generated_current'])<1e-8
   assert abs(r['native_subcell_photo_sum']-source['generated_current'])/source['generated_current']<.01
   assert m['PCE']<=top['metrics']['PCE']+bottom['metrics']['PCE']+1e-6
   assert abs(m['Voc']-top['metrics']['Voc']-bottom['metrics']['Voc'])<.005
   x=np.unique(np.r_[np.linspace(0,m['Voc'],100001),np.array(r['voltage'])[(np.array(r['voltage'])>=0)&(np.array(r['voltage'])<=m['Voc'])]])
   pmax=float(max(x*np.interp(x,r['voltage'],r['current'])));assert abs(pmax-m['PCE'])<1e-5
   audits.append(dict(grid=grid,case=case,rc=rc,source_G=source['generated_current'],split_G=r['subcell_source_G_sum'],native_G=r['native_subcell_photo_sum'],PCE_recompute_delta=pmax-m['PCE'],top_error=top['current_error'],bottom_error=bottom['current_error']))
   summary.append(dict(grid=grid,case=case,rc=rc,metrics=m,top_metrics=top['metrics'],bottom_metrics=bottom['metrics'],virtual_inner_work_functions=[top['inner_work_function'],bottom['inner_work_function']]))
save(OUT/'指标与核对.json',dict(summary=summary,audits=audits))
def figsave(fig,name):
 fig.tight_layout()
 for ext in ('png','svg'):fig.savefig(figs/(name+'.'+ext),dpi=170,bbox_inches='tight')
 p=figs/(name+'.svg');p.write_text('\n'.join(s.rstrip() for s in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8');plt.close(fig)
fig,axs=plt.subplots(1,2,figsize=(11,4))
for ax,case,title in zip(axs,('original_nk','aligned_ARC'),('原始能级 + 文献光学','先前能级与减反设计')):
 for part,label in [('top','宽带隙侧子电池'),('bottom','窄带隙侧子电池'),('series_R0','串联参考：零额外连接电阻')]:
  r=read(OUT/'grid2000'/f'{case}_{part}.json');ax.plot(r['voltage'],r['current'],label=label)
 ax.set(xlim=(0,2.35),ylim=(-1,20),xlabel='电压 / V',ylabel='电流密度 / mA/cm²',title=title);ax.legend(fontsize=8);ax.grid(alpha=.2)
figsave(fig,'同电流串联参考')
fig,axs=plt.subplots(1,2,figsize=(10,4))
for ax,case,title in zip(axs,('original_nk','aligned_ARC'),('原始能级参考','能级与减反参考')):
 for rc in (0,.1,1,5):
  r=read(OUT/'grid2000'/f'{case}_series_R{rc:g}.json');ax.plot(r['voltage'],r['current'],label=f'假设 Rc={rc:g} Ω·cm²')
 ax.set(xlim=(0,2.3),ylim=(-1,20),xlabel='电压 / V',ylabel='电流密度 / mA/cm²',title=title);ax.legend(fontsize=8);ax.grid(alpha=.2)
figsave(fig,'连接电阻敏感性')
def table(items):
 s='<div class="table"><table><tr><th>条件</th><th>Jsc / mA/cm²</th><th>Voc / V</th><th>FF / %</th><th>效率 / %</th></tr>'
 for label,m in items:s+='<tr><td>'+html.escape(label)+'</td>'+''.join(f'<td>{m[k]:.4f}</td>' for k in ('Jsc','Voc','FF','PCE'))+'</tr>'
 return s+'</table></div>'
items=[]
for case,label in [('original_nk','原始能级'),('aligned_ARC','先前能级与减反')]:
 for rc in (0,.1,1,5):items.append((f'{label} / 假设Rc={rc:g}',read(OUT/'grid2000'/f'{case}_series_R{rc:g}.json')['metrics']))
images=''.join('<img alt="'+n+'" src="data:image/png;base64,'+base64.b64encode((figs/(n+'.png')).read_bytes()).decode()+'">' for n in ('同电流串联参考','连接电阻敏感性'))
actual=read(OUT/'软件实算_1.4.1.json');reference=read(OUT/'grid2000/aligned_ARC_series_R0.json')
assert all(abs(actual['metrics'][k]-reference['metrics'][k])<1e-8 for k in ('Jsc','Voc','FF','PCE'))
body='''<h1>两子电池串联参考重建</h1><p>2026-11-14开始，2026-11-15完成。软件1.4.1新增独立模式。</p><div class="scope"><strong>本报告为串联参考，不是实际20n/20p连接区已经修复或可制造的证明。</strong><br>保留原物理层，用虚拟选择性内接触建立同电流串联；真实隧穿、跨界面自洽复合及连接损失尚未得到标定。零连接电阻只是一项参考假设。</div>
<h2>串联关系已正确建立</h2><p>原先把两层共同输出的电流近似相加，不能作为两子电池串联。新模式复用完整堆栈的一次G(x)，在n/p分界拆成前后子电池，按相同内部电流相加电压。没有添加独立物理互联材料层，也没有把原Voc手动乘倍数或重复使用两份太阳光。</p>
<p>保持结构NiOx20 / 宽380 / n20 / p20 / 窄780 / C60 40nm。两个案例都使用文献钙钛矿n/k和300–1100nm AM1.5G；原始能级χ宽3.8/窄3.9、原Air光学前膜，与先前χ宽3.42/窄4.0、传输层能级及SiO2 85nm减反设计分开对照。各案例都保留μ=2、τ=100μs、B=1E-10、原掺杂和厚度。未叠加前次μ=20、τ=1ms的材料质量假设。</p>
<h2>2000网格、32分段、子电池电压步长0.005V</h2>'''+table(items)+'''
<p>原始能级的宽/窄子电池Voc约1.325/0.771V，串联参考约2.095V、21.12%；先前能级与减反设计为1.301/0.773V，串联参考约2.074V、29.66%。参考电流回到约15–17mA/cm²的串联量级，未把两侧电流相加。Voc正确回到两子电池之和附近，不等于真实n/p连接已经达到这些数值。</p>
<h2>连接与光生假设</h2><p>虚拟内接触功函数由端点净掺杂的非简并Boltzmann近似推算：n侧χ+kTln(Nc/Nd,net)，p侧χ+Eg−kTln(Nv/Na,net)。它们不是新增真实电极，Rc不是由1E16掺杂计算出来的材料参数。参考结果对这些选择性边界有依赖，因此不能称为对原n/p连接的完整预测。</p>
<p>每个子电池内部Rs=0、Rsh=1E12；合成时全局Rs=0.3、Rsh=40000只计一次。内部电流Js下，Vi=Vtop+Vbottom−JsRc/1000；外部电流Jext=Js−1000Vi/Rsh；外部电压Vext=Vi−JextRs/1000。电流用mA/cm²、电阻用Ω·cm²。总Pin仍100mW/cm²，子电池表中的效率也以同一完整入射功率作分母。</p>
<p>采用源G(x)直接空间裁剪及线性重映射，没有重算两份独立全光谱照明，也没有强制缩放电流到目标值。光生拆分积分守恒，子电池原生光生积分与源G差异低于1%，具体值在指标与核对.json。先前能级与减反案例：源35.6982、重映射原生总35.6202mA/cm²，差约0.22%。</p>'''+images+'''
<h2>软件实算与操作</h2><p>新版本实际文件夹版通过“打开参数”载入独立串联参考项目，再点击“运行串联参考”。软件导出的四指标与上述2000点批量结果差为零，截图如下。原整体异质结J–V结果与参数独立保留。导出的参考JSON可以重开，导入时核验曲线与指标，并始终显示模型适用范围。</p>'''+ '<img alt="实际软件串联参考窗口" src="data:image/png;base64,'+base64.b64encode((OUT/'软件界面_1.4.1.png').read_bytes()).decode()+'">'+'''
<h2>数值校核和剩余工作</h2><p>1000/2000网格复核：两种串联参考的效率变化均小于0.002个百分点，Voc变化小于0.00003V。在相同子电池源曲线下，零连接电阻到1Ω·cm²时，能级与减反案例效率约29.66→29.40%。共同电流反演、功率密集采样复算、子电池Pmax之和上界以及光生分配均检查通过。单元测试验证相同子电池电压加倍而电流不加倍、失配电流限制、连接损失降功率及非单调曲线拒绝；界面测试检查分界、独立保存、重开、指标一致性和关闭取消。</p>
<p>真正证明该n/p材料接触有效，还需建立、标定其自洽载流子连接模型，检查中央Jn/Jp转换、空间准费米能级分裂、连接I–V及电压损失。本版本没有实现非局域带间隧穿或简并统计，也没有重新计算偏置条件下的子电池EQE。普通界面SRH或一个假设Rc不能替代这些验证。不能将参考29.66%当作实物电池效率或宣称结构优越性。</p>
<p>参考物理背景：<a href="https://pubs.rsc.org/en/content/articlehtml/2020/mh/d0mh00990c">复合连接的工作原理</a>；<a href="https://www.nature.com/articles/s41467-024-55654-4">实验全钙叠层2.08V案例</a>。文献只说明串联机制和量级，不是本模型的标定数据。</p>
<h2>文件和复现</h2><p>parameters提供1.4.1独立参考输入；完整包还含光生源、两个子电池原生J–V、串联曲线、连接电阻扫描、图和驱动脚本。解压到源码仓库results/本研究目录，运行run_reference.py 1000或2000，可离线复算，不需要旧大包中的整套输出。软件求解模块为perovskite_studio/tandem_reference.py。</p>'''
(OUT/'串联参考重建报告.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>串联参考重建</title><style>body{font:16px/1.7 "Microsoft YaHei",sans-serif;max-width:1140px;margin:26px auto;padding:0 20px;color:#202124}.scope{padding:16px;background:#fff2d9;border:1px solid #c77700;border-radius:8px}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}.table{overflow:auto}h2{margin-top:30px}</style>'+body,encoding='utf-8')
cur=ROOT/'research/2026-11-15/01_series_reference';cur.mkdir(parents=True,exist_ok=True)
for name in ('parameters','figures'):shutil.copytree(OUT/name,cur/name,dirs_exist_ok=True)
for name in ('串联参考重建报告.html','指标与核对.json','source_manifest.json','软件与打包核对.json','软件界面_1.4.1.png','run_reference.py','make_report.py'):shutil.copy2(OUT/name,cur/name)
readme='# 两子电池串联参考重建\n\n打开[报告](串联参考重建报告.html)。软件1.4.1新增同电流、电压相加的独立参考模式，复用同一完整堆栈G(x)。两种能级/光学案例的零额外连接电阻参考Voc约2.095/2.074V、效率21.12%/29.66%。\n\n**它采用虚拟选择性内接触，不是已验证实际20n/20p连接的自洽隧穿仿真，不预测材料接触是否有效。** 未增加独立物理互联层，也未手动抬高Voc。\n\nparameters需要1.4.1打开。完整数据包在[v1.4.1发布](https://github.com/mumium/perovskite-device-studio/releases/tag/v1.4.1)中的series-reference-2026-11-15.zip。操作和限制见[说明](../../../docs/tandem-reference.md)。\n'
(OUT/'README.md').write_text(readme,encoding='utf-8');(cur/'README.md').write_text(readme,encoding='utf-8')
dest=ROOT/'build/research-2026-11-15-series';dest.mkdir(parents=True,exist_ok=True);z=dest/'series-reference-2026-11-15.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
 for p in OUT.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:f.write(p,p.relative_to(OUT))
with zipfile.ZipFile(z) as f:assert f.testzip() is None
(dest/'SHA256SUMS.txt').write_text(hashlib.sha256(z.read_bytes()).hexdigest()+'  '+z.name+'\n',encoding='utf-8');print('REPORT VERIFIED',z.stat().st_size,flush=True)
