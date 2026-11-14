"""Two-terminal series REFERENCE, not a microscopic n/p tunnel-junction model.

Reuse the generation from one complete optical stack. Subcell inner contacts
are virtual selective reservoirs, never additional material layers. Global
Rs/Rsh are applied once. The connection loss is an explicitly assumed area
resistance; zero means an ideal-connection benchmark, not a measured junction.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import numpy as np
from .performance import write_inputs, _rewrite_setup, _run_engine, calculate_metrics, run_simulation
from .physics import profile
from .optics import get_optics


def solve_subcell(layers, settings, source_x_nm, source_g, offset_nm, inner_work_function, top=True,cancel=None):
    layers=deepcopy(layers);s=deepcopy(settings)
    s.update(G=0.,rs=0.,rsh=1e12,vmin=-1.6,vmax=1.65 if top else 1.25)
    s['optics']['mode']='manual'
    if top:s.update(right=inner_work_function,sn_right=1e7,sp_right=0.)
    else:s.update(left=inner_work_function,sn_left=0.,sp_left=1e7)
    length=sum(l['thickness'] for l in layers)
    xx=np.asarray(source_x_nm);gg=np.asarray(source_g)
    mask=(xx>offset_nm)&(xx<offset_nm+length)
    x=np.r_[offset_nm,xx[mask],offset_nm+length]
    g=np.interp(x,xx,gg)
    with tempfile.TemporaryDirectory(prefix='pds_series_reference_') as folder:
        mesh=write_inputs(folder,layers,s)
        np.savetxt(Path(folder)/'generation.txt',np.column_stack([(x-offset_nm)*1e-9,g*1e6]),
                   fmt='%.16e',header='x G_ehp',comments='')
        _rewrite_setup(folder,dict(genProfile='generation.txt',varFile='none'))
        data,log=_run_engine(folder,s,cancel)
    v,j,m,w=calculate_metrics(data['Vext'],-data['Jext']/10,settings['pin'])
    if m['Voc'] is None:raise ValueError('Subcell scan did not cover Voc')
    photo=sum(float(data[f'JphotoL{i+1}'][0])/10 for i in range(mesh['sublayers']))
    error=float(np.max(data['errJ'])/max(photo*10,1e-9))
    if error>.005:raise ValueError('Subcell current continuity failed')
    return dict(voltage=v.tolist(),current=j.tolist(),metrics=m,layers=layers,
                settings=s,inner_work_function=inner_work_function,
                virtual_inner_contact=True,source_offset_nm=offset_nm,
                source_G_current=float(1.602176634e-19*np.trapezoid(g,(x-offset_nm)*1e-7)*1000),
                native_photo_current=photo,current_error=error,warnings=w,log=log)


def _inverse_curve(cell):
    v=np.asarray(cell['voltage']);j=np.asarray(cell['current'])
    # Current at deep reverse-bias saturation can have tiny solver ripples.
    envelope=np.minimum.accumulate(j)
    correction=float(np.max(np.abs(j-envelope)))
    if correction>max(1e-4,cell['metrics']['Jsc']*1e-4):
        raise ValueError('Non-monotonic subcell current; cannot safely invert')
    jj,ix=np.unique(envelope[::-1],return_index=True)
    vv=v[::-1][ix]
    return jj,vv,correction


def compose_series(top,bottom,pin,rs=0.,rsh=1e12,connection_resistance=0.):
    if not np.all(np.isfinite([pin,rs,rsh,connection_resistance])) or pin<=0 or min(rs,connection_resistance)<0 or rsh<=0:raise ValueError('Invalid circuit values')
    a,av,ac=_inverse_curve(top);b,bv,bc=_inverse_curve(bottom)
    lo=max(a[0],b[0],-.5);hi=min(a[-1],b[-1])
    if hi<=lo:raise ValueError('No common-current range')
    current=np.unique(np.r_[np.linspace(lo,hi,20001),a[(a>=lo)&(a<=hi)],b[(b>=lo)&(b<=hi)],0.])
    vt=np.interp(current,a,av);vb=np.interp(current,b,bv)
    junction_drop=current*connection_resistance/1000
    vi=vt+vb-junction_drop
    je=current-vi/rsh*1000
    ve=vi-je*rs/1000
    v,j,m,w=calculate_metrics(ve,je,pin)
    if m['Voc'] is None or m['Jsc'] is None:raise ValueError('Common-current coverage insufficient')
    return dict(voltage=v.tolist(),current=j.tolist(),metrics=m,warnings=w,
                schema=1,model='tandem_series_reference',
                model_description='two-subcell same-current series REFERENCE; virtual internal selective contacts',
                connection=dict(mode='ideal' if connection_resistance==0 else 'assumed Ohmic loss',resistance_ohm_cm2=connection_resistance),
                circuit=dict(rs=rs,rsh=rsh,pin=pin,shunt_topology='one shunt across the ideal series stack, upstream of one global Rs'),
                matching=dict(series_current=current.tolist(),top_voltage=vt.tolist(),bottom_voltage=vb.tolist(),connection_drop=junction_drop.tolist(),
                              maximum_monotonic_corrections=[ac,bc]),
                limitation='Not a self-consistent spatial tunnel/recombination junction; does not predict whether the physical 20n/20p contact works.')


def run_tandem_reference(layers,settings,split_after,connection_resistance=0.,cancel=None,progress=None):
    """Solve one full optical stack, then split it without duplicating photons."""
    layers=deepcopy(layers);settings=deepcopy(settings)
    if not np.isfinite(connection_resistance) or connection_resistance<0:raise ValueError('连接电阻须为有限非负数')
    if get_optics(settings)['mode']!='spectrum' or get_optics(settings)['illumination']!='left':
        raise ValueError('串联参考目前要求左侧入射的光谱模式')
    if settings['left_anode']!=1:raise ValueError('当前串联参考要求左侧为空穴接触、右侧为电子接触')
    if not 0<split_after<len(layers):raise ValueError('分界必须位于两个材料层之间')
    a=profile(layers[split_after-1],[1.]);b=profile(layers[split_after],[0.])
    nd=float(a['Nd'][0]-a['Na'][0]);na=float(b['Na'][0]-b['Nd'][0])
    nc=float(a['Nc'][0]);nv=float(b['Nv'][0])
    if not 0<nd<nc or not 0<na<nv:
        raise ValueError('分界左侧须为非简并n型、右侧须为非简并p型；本参考不支持重掺杂隧穿结预测')
    vt=8.617333262e-5*settings['T']
    wn=float(a['chi'][0])+vt*np.log(nc/nd)
    wp=float(b['chi'][0]+b['Eg'][0])-vt*np.log(nv/na)
    if not float(a['chi'][0])<=wn<=float(a['chi'][0]+a['Eg'][0]) or not float(b['chi'][0])<=wp<=float(b['chi'][0]+b['Eg'][0]):
        raise ValueError('由掺杂推算的虚拟内接触能级超出禁带，不能采用此参考边界')
    if progress:progress('正在计算完整结构的光生分布…')
    # The optical generation is bias-independent. A single native operating
    # point obtains it; the discarded full-stack electrical metrics are never
    # used as tandem predictions.
    source_settings=deepcopy(settings);source_settings.update(vmin=-.01,vmax=.01,vstep=.01)
    source=run_simulation(layers,source_settings,cancel)
    o=source['optics'];cut=sum(l['thickness'] for l in layers[:split_after])
    if progress:progress('正在求解宽带隙侧子电池…')
    top=solve_subcell(layers[:split_after],settings,o['x_nm'],o['G_cm3_s'],0.,float(wn),True,cancel)
    if progress:progress('正在求解窄带隙侧子电池…')
    bottom=solve_subcell(layers[split_after:],settings,o['x_nm'],o['G_cm3_s'],cut,float(wp),False,cancel)
    result=compose_series(top,bottom,settings['pin'],settings['rs'],settings['rsh'],connection_resistance)
    result.update(layers=layers,settings=settings,split_after_layer=split_after,subcells=dict(top=top,bottom=bottom),
                  source_generation=dict(x_nm=o['x_nm'],G_cm3_s=o['G_cm3_s'],generated_current=source['generated_current']),
                  scope='串联参考：虚拟选择性内接触；未建模真实n/p界面隧穿或跨界面自洽复合')
    balance=top['source_G_current']+bottom['source_G_current']
    if abs(balance-source['generated_current'])>max(.01,source['generated_current']*.001):raise ValueError('光生分配不守恒，未采用参考结果')
    remap=top['native_photo_current']+bottom['native_photo_current']-source['generated_current']
    if abs(remap)>max(.05,source['generated_current']*.01):raise ValueError('子电池光生重映射误差超过1%，请增加网格')
    result['generation_audit']=dict(split_integral_sum=balance,native_photo_sum=top['native_photo_current']+bottom['native_photo_current'],remap_delta=remap)
    return result
