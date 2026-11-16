"""2T multi-domain DD/TMM simulation with an explicit equivalent junction.

No microscopic tunneling, degenerate statistics or luminescent coupling is
implied. Optical generation is calculated independently of the full-stack
electrical equations. All connection parameters are user inputs.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import numpy as np
from scipy.optimize import brentq

from .physics import profile
from .optics import get_optics, integrate
from .performance import (ENGINE_BUILD, SimulationCancelled, validate_device,
                          write_inputs, _rewrite_setup, _run_engine, calculate_metrics)
from .tandem_reference import _inverse_curve

MODEL = 'tandem_2t_multiscale'
DEFAULTS = dict(top_end=3, bottom_start=3, automatic_contacts=True, contact_offset=.15,
                top_work=3.95, bottom_work=5., mode='ohmic', resistance=.1,
                j0=100., ideality=1., junction_collection=1., eqe_voltage=0.)
MODES = {'ideal': '理想连接', 'ohmic': '电阻连接', 'diode': '等效复合结'}


def auto_partition(layers):
    for i in range(len(layers)-1):
        a, b = profile(layers[i], [1.]), profile(layers[i+1], [0.])
        if a['Nd'][0] > a['Na'][0] and b['Na'][0] > b['Nd'][0]:
            return i+1
    active = [i for i,a in enumerate(layers) if a.get('absorber')]
    return active[1] if len(active)>1 else max(1, len(layers)//2)


def parameters(layers, settings, values=None):
    t = dict(DEFAULTS) | dict(values or {})
    for key in ('top_end', 'bottom_start'):
        v = t[key]
        if not np.isfinite(v) or int(v) != v:
            raise ValueError('子电池分界须为整数层号')
        t[key] = int(v)
    a,b = t['top_end'],t['bottom_start']
    if not 0 < a <= b < len(layers):
        raise ValueError('顶电池末层必须位于底电池首层之前；两者之间可留出连接区')
    if t['mode'] not in MODES or t['automatic_contacts'] not in (True,False):
        raise ValueError('未知的叠层连接或内接触模式')
    for key in ('contact_offset','top_work','bottom_work','resistance','j0','ideality','junction_collection','eqe_voltage'):
        if not np.isfinite(t[key]):
            raise ValueError('叠层参数须为有限数值：'+key)
    if t['resistance']<0 or t['j0']<=0 or not .1<=t['ideality']<=10 or not 0<=t['junction_collection']<=1:
        raise ValueError('连接电阻须≥0，J0须>0，理想因子须为0.1–10，连接区收集比例须为0–1')
    if t['contact_offset']<=0:
        raise ValueError('内接触距带边的能量须>0')
    if get_optics(settings)['mode']!='spectrum' or get_optics(settings)['illumination']!='left' or settings['left_anode']!=1:
        raise ValueError('2T 模式要求左侧入射的光谱 TMM，左侧为空穴接触、右侧为电子接触')
    if not any(x.get('absorber') for x in layers[:a]) or not any(x.get('absorber') for x in layers[b:]):
        raise ValueError('两个子电池都须包含产生光载流子的吸收层')
    top, bot = profile(layers[a-1],[1.]),profile(layers[b],[0.])
    if t['automatic_contacts']:
        t['top_work'] = float(top['chi'][0]+min(t['contact_offset'],top['Eg'][0]/4))
        t['bottom_work'] = float(bot['chi'][0]+bot['Eg'][0]-min(t['contact_offset'],bot['Eg'][0]/4))
    for p,key in [(top,'top_work'),(bot,'bottom_work')]:
        if not p['chi'][0] < t[key] < p['chi'][0]+p['Eg'][0]:
            raise ValueError('虚拟内接触功函数须位于对应端点禁带内：'+key)
    # Cross-domain and connector defects are not a second connection model.
    # They do not affect TMM; intracell defects remain active in DD subcells.
    optical_layers = deepcopy(layers)
    for layer in optical_layers:
        layer['interface'] = dict(layer.get('interface', {}), Nt=0.)
    validate_device(optical_layers, settings)
    return t


def _remaining(settings, started, cancel):
    if cancel is not None and cancel.is_set():
        raise SimulationCancelled('叠层模拟已取消')
    left = float(settings['timeout'])-(time.monotonic()-started)
    if left < 1:
        raise RuntimeError('叠层模拟超过总超时设置')
    return dict(settings, timeout=max(1,int(left)))


def _read_optical(data, mesh, layers):
    if len(data)!=mesh['effective_points']+2:
        raise RuntimeError('独立光学网格输出不完整')
    x,g=data['x']*1e9,data['G_ehp']/1e6
    if np.any(g<0) or np.any(np.diff(x)<=0):
        raise RuntimeError('光学输出包含负光生率或非递增位置')
    return x,g


def optical_generation(layers, settings, cancel=None, started=None):
    started=time.monotonic() if started is None else started
    s=_remaining(settings,started,cancel)
    optical_layers=deepcopy(layers)
    for a in optical_layers:a['interface']=dict(a.get('interface',{}),Nt=0.)
    with tempfile.TemporaryDirectory(prefix='pds_tandem_optics_') as folder:
        mesh=write_inputs(folder,optical_layers,s)
        data,log=_run_engine(folder,s,cancel,context='叠层完整光学堆栈',optics_only=True)
    x,g=_read_optical(data,mesh,layers)
    optical=mesh.pop('optical')
    optical.update(x_nm=x.tolist(),G_cm3_s=g.tolist(),layer_index=[mesh['pieces'][int(i)-1]['parent_index'] for i in data['lid']])
    return dict(optics=optical,mesh=mesh,log=log,
                generated_current=float(1.602176634e-19*integrate(g,x*1e-7)*1000))


def crop_generation(x,g,left,right):
    xx=np.asarray(x);gg=np.asarray(g);keep=(xx>left)&(xx<right)
    xp=np.r_[left,xx[keep],right]
    gp=np.interp(xp,xx,gg)
    return xp-left,gp,float(1.602176634e-19*integrate(gp,(xp-left)*1e-7)*1000)


def _cell(layers, settings, x, g, work, top, cancel=None, started=None, voltage=None):
    started=time.monotonic() if started is None else started
    s=_remaining(settings,started,cancel);s=deepcopy(s)
    gap=max(float(np.max(profile(a,[0.,1.])['Eg'])) for a in layers if a.get('absorber'))
    s.update(G=0.,rs=0.,rsh=1e12,vmin=-max(1.6,gap),vmax=max(.1,gap-.02))
    s['optics']['mode']='manual'
    if top:s.update(right=work,sn_right=1e7,sp_right=0.)
    else:s.update(left=work,sn_left=0.,sp_left=1e7)
    with tempfile.TemporaryDirectory(prefix='pds_tandem_cell_') as folder:
        mesh=write_inputs(folder,layers,s)
        np.savetxt(Path(folder)/'generation.txt',np.column_stack([np.asarray(x)*1e-9,np.asarray(g)*1e6]),
                   fmt='%.16e',header='x G_ehp',comments='')
        numerical=dict(genProfile='generation.txt',varFile='none')
        if voltage is not None:numerical.update(Vmin=voltage,Vmax=voltage,outputRatio=1)
        _rewrite_setup(folder,numerical)
        d,log=_run_engine(folder,s,cancel,context='顶电池' if top else '底电池')
    photo=sum(float(d[f'JphotoL{i+1}'][0])/10 for i in range(mesh['sublayers']))
    if voltage is not None:
        return dict(current=float(-d['Jext'][0]/10),error=float(d['errJ'][0]/10),photo=photo)
    v,j,m,w=calculate_metrics(d['Vext'],-d['Jext']/10,settings['pin'])
    if m['Voc'] is None or m['Jsc'] is None:
        raise ValueError('子电池扫描没有覆盖有效开路点或短路点；请核对材料和内接触')
    mask=(d['Vext']>=0)&(d['Vext']<=m['Voc'])
    error=float(np.max(d['errJ'][mask])/max(photo*10,1e-12))
    if error>.005:raise RuntimeError('子电池光伏工作区电流守恒误差超过0.5%，未采用此曲线')
    return dict(voltage=v.tolist(),current=j.tolist(),metrics=m,photo_current=photo,current_error=error,
                layers=deepcopy(layers),settings=s,inner_work_function=work,virtual_inner_contact=True,warnings=w,log=log)


def junction_voltage(current, connection, temperature, photo=0.):
    """J(mA/cm²)=J0 expm1(Vd/nVt)-Jph; Vrj=Vd+J*R/1000.

    The equivalent diode has no breakdown branch. Its valid current domain
    is enforced before interpolation, never filled by extrapolation.
    """
    j=np.asarray(current,dtype=float);mode=connection['mode']
    if mode=='ideal':return np.zeros_like(j)
    r=j*connection['resistance']/1000
    if mode=='ohmic':return r
    z=(j+photo)/connection['j0']
    if np.any(z<=-1):raise ValueError('等效连接进入未建模的反向击穿电流区')
    return r+connection['ideality']*8.617333262e-5*temperature*np.log1p(z)


def compose_tandem(top,bottom,settings,connection,junction_photo=0.):
    a,av,ac=_inverse_curve(top);b,bv,bc=_inverse_curve(bottom)
    lo=max(float(a[0]),float(b[0]),-.5);hi=min(float(a[-1]),float(b[-1]))
    if connection['mode']=='diode':
        bound=-junction_photo-connection['j0']
        lo=max(lo,bound+max(abs(bound)*1e-10,1e-14))
    if not lo<=0<hi:raise ValueError('没有覆盖开路与正输出电流的共同电流区间')
    # Dense logarithmic near-zero points retain a steep, weakly conducting
    # junction's open-circuit neighborhood instead of interpolating across it.
    near=np.geomspace(max(hi*1e-12,1e-14),hi,1500)
    js=np.unique(np.r_[np.linspace(lo,hi,16001),near,0.,a[(a>=lo)&(a<=hi)],b[(b>=lo)&(b<=hi)]])
    vtop=np.interp(js,a,av);vbot=np.interp(js,b,bv)
    drop=junction_voltage(js,connection,settings['T'],junction_photo)
    vi=vtop+vbot-drop
    jext=js-1000*vi/settings['rsh'];ve=vi-jext*settings['rs']/1000
    if np.any(np.diff(ve)>1e-7):raise ValueError('等效连接后出现明显非单调端电压，未采用曲线')
    v,j,m,w=calculate_metrics(ve,jext,settings['pin'])
    if any(m[k] is None for k in ('Voc','Jsc','Vmp')):raise ValueError('叠层曲线未覆盖有效光伏工作区')
    match=dict(series_current=js.tolist(),external_voltage=ve.tolist(),external_current=jext.tolist(),
               top_voltage=vtop.tolist(),bottom_voltage=vbot.tolist(),connection_drop=drop.tolist(),internal_voltage=vi.tolist(),
               monotonic_corrections=[ac,bc])
    return dict(schema=1,model=MODEL,voltage=v.tolist(),current=j.tolist(),metrics=m,warnings=w,
                connection=deepcopy(connection),junction_photo_current=junction_photo,matching=match)


def operating_point(result,voltage):
    z=result['matching'];v=np.asarray(z['external_voltage'])[::-1]
    if not v[0]<=voltage<=v[-1]:raise ValueError('所选工作电压超出已求解范围，不能外推')
    p={k:float(np.interp(voltage,v,np.asarray(z[k])[::-1])) for k in
       ['series_current','external_current','top_voltage','bottom_voltage','connection_drop','internal_voltage']}
    p['external_voltage']=float(voltage)
    j=p['series_current'];je=p['external_current'];vi=p['internal_voltage'];s=result['settings']
    p.update(top_power=j*p['top_voltage'],bottom_power=j*p['bottom_voltage'],
             connection_power=j*p['connection_drop'],series_power=je*je*s['rs']/1000,
             shunt_power=1000*vi*vi/s['rsh'],output_power=je*voltage)
    p['power_residual']=p['top_power']+p['bottom_power']-p['connection_power']-p['series_power']-p['shunt_power']-p['output_power']
    return p


def run_tandem(layers,settings,values=None,cancel=None,progress=None,started=None):
    started=time.monotonic() if started is None else started
    layers=deepcopy(layers);settings=deepcopy(settings);t=parameters(layers,settings,values)
    tell=lambda message:progress(message) if progress else None
    tell('计算完整堆栈的光生分配（不求解整栈电学）…')
    source=optical_generation(layers,settings,cancel,started);o=source['optics']
    a,b=t['top_end'],t['bottom_start'];cut1=sum(z['thickness'] for z in layers[:a]);cut2=sum(z['thickness'] for z in layers[:b]);end=sum(z['thickness'] for z in layers)
    xt,gt,jt=crop_generation(o['x_nm'],o['G_cm3_s'],0.,cut1)
    xb,gb,jb=crop_generation(o['x_nm'],o['G_cm3_s'],cut2,end)
    jr=0. if cut1==cut2 else crop_generation(o['x_nm'],o['G_cm3_s'],cut1,cut2)[2]
    if abs(jt+jb+jr-source['generated_current'])>max(.001,source['generated_current']*1e-5):
        raise RuntimeError('顶/连接/底光生分配不守恒')
    tell('求解顶子电池漂移–扩散 J–V…')
    top=_cell(layers[:a],settings,xt,gt,t['top_work'],True,cancel,started)
    tell('求解底子电池漂移–扩散 J–V…')
    bottom=_cell(layers[b:],settings,xb,gb,t['bottom_work'],False,cancel,started)
    remap=abs(top['photo_current']-jt)+abs(bottom['photo_current']-jb)
    if remap>max(.05,(jt+jb)*.01):raise RuntimeError('子电池光生重映射误差超过1%，请细化网格')
    tell('求解共同电流、连接电压和外部电路…')
    r=compose_tandem(top,bottom,settings,t,jr*t['junction_collection'])
    r.update(layers=layers,settings=settings,tandem=t,subcells=dict(top=top,bottom=bottom),
             optics=o,mesh=source['mesh'],generated_current=source['generated_current'],
             generation_audit=dict(top=jt,bottom=jb,junction=jr,total=source['generated_current'],remap_error=remap),
             elapsed=time.monotonic()-started,engine_build=ENGINE_BUILD,
             relative_current_error=max(top['current_error'],bottom['current_error']),
             scope='2T多尺度：子电池漂移扩散＋等效连接；虚拟选择性内接触，连接参数待标定；非微观隧穿预测。')
    r['workpoints']={key:operating_point(r,v) for key,v in [('SC',0.),('MPP',r['metrics']['Vmp']),('OC',r['metrics']['Voc'])]}
    r['warnings'] += ['两个内接触为选择性边界假设，连接参数须标定；本模型不验证实际材料已形成高效连接。',
                      '不含隧穿、简并统计、发光耦合及全堆栈统一电势求解；连接区光生按所选等效模型处理。']
    return r


def _inverse_slope(cell,current):
    j,v,_=_inverse_curve(cell)
    i=max(0,min(len(j)-2,int(np.searchsorted(j,current))-1))
    return max(0.,float(-(v[i+1]-v[i])/(j[i+1]-j[i])))


def response_weights(result,voltage):
    p=operating_point(result,voltage);j=p['series_current'];t=result['tandem'];s=result['settings']
    rt=_inverse_slope(result['subcells']['top'],j);rb=_inverse_slope(result['subcells']['bottom'],j)
    rd=t['ideality']*8.617333262e-5*s['T']/(t['j0']+j+result['junction_photo_current']) if t['mode']=='diode' else 0.
    rr=rd+(t['resistance']/1000 if t['mode']!='ideal' else 0.)
    denominator=(rt+rb+rr)*(1+s['rs']/s['rsh'])+s['rs']/1000
    if denominator<=0 or not np.isfinite(denominator):raise ValueError('工作点微分电阻无法确定')
    return p,dict(top=rt/denominator,bottom=rb/denominator,junction=-rd*t['junction_collection']/denominator)


def run_tandem_eqe(layers,settings,values=None,cancel=None,progress=None):
    """Bias-dependent, small-signal terminal response under one background.

    Each subcell's optical perturbation is solved with DD at its actual
    operating voltage. The circuit Jacobian couples these responses at fixed
    external voltage. This is not independent bias-light EQE metrology.
    """
    started=time.monotonic();input_settings=deepcopy(settings);settings=deepcopy(settings)
    eqe=dict(step_nm=20.,photon_flux_cm2_s=1e14,background_scale=1.) | settings.get('eqe',{})
    if not all(np.isfinite(v) for v in eqe.values()) or not 1<=eqe['step_nm']<=200 or eqe['photon_flux_cm2_s']<=0 or eqe['background_scale']<=0:
        raise ValueError('叠层工作点EQE：步长1–200nm、探测通量>0、背景比例>0')
    # Spectral background scales optical intensity once. The efficiency
    # denominator is its actual incident power, not two independent suns.
    settings['pin']*=eqe['background_scale']
    r=run_tandem(layers,settings,values,cancel,progress,started)
    t=r['tandem'];p,weights=response_weights(r,t['eqe_voltage']);o=r['optics'];a,b=t['top_end'],t['bottom_start']
    cut1=sum(z['thickness'] for z in layers[:a]);cut2=sum(z['thickness'] for z in layers[:b]);end=sum(z['thickness'] for z in layers)
    xt,gt,_=crop_generation(o['x_nm'],o['G_cm3_s'],0.,cut1);xb,gb,_=crop_generation(o['x_nm'],o['G_cm3_s'],cut2,end)
    base_top=_cell(layers[:a],settings,xt,gt,t['top_work'],True,cancel,started,p['top_voltage'])
    base_bot=_cell(layers[b:],settings,xb,gb,t['bottom_work'],False,cancel,started,p['bottom_voltage'])
    lo,hi=o['settings']['wavelength_min'],o['settings']['wavelength_max']
    waves=np.unique(np.r_[np.arange(lo,hi+1e-9,eqe['step_nm']),hi]);flux=eqe['photon_flux_cm2_s'];denom=1.602176634e-19*flux*1000
    optical_layers=deepcopy(layers)
    for z in optical_layers:z['interface']=dict(z.get('interface',{}),Nt=0.)
    responses=[];noise=[]
    with tempfile.TemporaryDirectory(prefix='pds_tandem_eqe_') as folder:
        mesh=write_inputs(folder,optical_layers,_remaining(settings,started,cancel))
        for i,wave in enumerate(waves):
            _remaining(settings,started,cancel)
            if progress:progress(f'叠层EQE {i+1}/{len(waves)} · {wave:g} nm')
            irradiance=flux*1e4*6.62607015e-34*299792458/(wave*1e-9)/1e-9
            np.savetxt(Path(folder)/'spectrum.txt',[[lo*1e-9,irradiance],[hi*1e-9,irradiance]],header='lambda I',comments='')
            _rewrite_setup(folder,dict(lambda_min=wave*1e-9,lambda_max=wave*1e-9))
            data,_=_run_engine(folder,_remaining(settings,started,cancel),cancel,context=f'叠层EQE光学 {wave:g}nm',optics_only=True)
            xx,gg=_read_optical(data,mesh,layers)
            tx,tg,_=crop_generation(xx,gg,0.,cut1);bx,bg,_=crop_generation(xx,gg,cut2,end)
            rt=_cell(layers[:a],settings,xt,np.asarray(gt)+np.interp(xt,tx,tg),t['top_work'],True,cancel,started,p['top_voltage'])
            rb=_cell(layers[b:],settings,xb,np.asarray(gb)+np.interp(xb,bx,bg),t['bottom_work'],False,cancel,started,p['bottom_voltage'])
            et=(rt['current']-base_top['current'])/denom;eb=(rb['current']-base_bot['current'])/denom
            er=0. if cut1==cut2 else crop_generation(xx,gg,cut1,cut2)[2]/denom
            responses.append([et,eb,er,weights['top']*et+weights['bottom']*eb+weights['junction']*er])
            noise.append((weights['top']*(rt['error']+base_top['error'])+weights['bottom']*(rb['error']+base_bot['error']))/denom)
    response=np.asarray(responses)
    spectrum=np.asarray(o['spectrum_nm_W_m2_nm']);grid=np.arange(lo,hi+1.)
    photons=np.interp(grid,spectrum[:,0],spectrum[:,1])*grid*1e-9/(6.62607015e-34*299792458)
    weighted={key:float(1.602176634e-19*integrate(np.interp(grid,waves,response[:,i])*photons,grid)/10)
              for i,key in [(0,'top'),(1,'bottom'),(3,'terminal')]}
    warnings=['工作点小信号EQE：使用实际子电池偏压与电路线性化；积分响应不保证等于Jsc，未模拟独立偏置光测量。']
    if max(noise)>.01:warnings.append('部分探测点的数值误差估计超过1个百分点，请核对探测通量和网格。')
    return dict(schema=1,model=MODEL+'_eqe',wavelength_nm=waves.tolist(),EQE=response[:,3].tolist(),
                top_EQE=response[:,0].tolist(),bottom_EQE=response[:,1].tolist(),junction_absorptance=response[:,2].tolist(),
                weighted_currents=weighted,weights=weights,operating_point=p,numerical_error_estimate=noise,
                eqe_settings=eqe,layers=deepcopy(layers),settings=input_settings,tandem=t,
                background_result=r,elapsed=time.monotonic()-started,warnings=warnings)
