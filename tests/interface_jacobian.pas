program CheckInterfaceJacobian;
{$mode delphi}
{$unitpath Units/}
uses SysUtils, Math, TypesAndConstants, DDTypesAndConstants, DDRoutines;
var par:TInputParameters; stv:TStaticVars; log:Text; msg:AnsiString;
    state:TState; base,plusRec,minusRec:TRec;
    n,p,zero:vector; i,j,k,ii,c,test,failures,checks:Integer;
    original,h,finite,analytic,scale,err,maxerr:myReal;

procedure Evaluate(var rec:TRec);
begin
  if c=0 then Calc_Recombination_n(rec,0,n,p,zero,zero,state.f_tb,state.f_ti,stv,par)
         else Calc_Recombination_p(rec,0,n,p,zero,zero,state.f_tb,state.f_ti,stv,par);
end;

begin
  Read_Parameters('simulation_setup.txt',msg,par,stv,SimSS);
  Prepare_Log_File(log,msg,par,'5.36');
  Check_Parameters(log,stv,par,SimSS);
  Make_Grid(stv,par);Define_Layers(stv,par);Init_Trapping(log,stv,par);
  Init_Pot_Dens_Ions_Traps(state.V,state.Vgn,state.Vgp,state.n,state.p,state.nion,state.pion,
    state.f_tb,state.f_ti,state.f_ti_numer,state.f_ti_inv_denom,0,stv,par);
  for j:=1 to stv.NLayers do stv.Ntb[j].NLevels:=0;
  FillChar(zero,SizeOf(zero),0); failures:=0; checks:=0; maxerr:=0;
  for test:=0 to 3 do begin
    for i:=0 to par.NP+1 do begin
      n[i]:=1e21*Power(10,0.2*(i mod 5)+0.3*test);
      p[i]:=3e20*Power(10,0.15*(i mod 7)-0.2*test);
    end;
    for c:=0 to 1 do begin
      Evaluate(base);
      for j:=1 to stv.NLayers-1 do if stv.Nti[j].NLevels>0 then begin
        ii:=stv.i1[j];
        for k:=ii-1 to ii+2 do begin
          if c=0 then original:=n[k] else original:=p[k];
          h:=original*1e-4;
          if c=0 then n[k]:=original+h else p[k]:=original+h; Evaluate(plusRec);
          if c=0 then n[k]:=original-h else p[k]:=original-h; Evaluate(minusRec);
          if c=0 then n[k]:=original else p[k]:=original;
          for i:=ii to ii+1 do begin
            finite:=(plusRec.int[i]-minusRec.int[i])/(2*h);analytic:=0;
            if k=i-1 then analytic:=base.int_cont_lo[i];
            if k=i then analytic:=base.int_cont_m[i];
            if k=i+1 then analytic:=base.int_cont_up[i];
            scale:=Max(Max(Abs(finite),Abs(analytic)),1e-30);
            err:=Abs(finite-analytic)/scale;maxerr:=Max(maxerr,err);Inc(checks);
            if err>1e-5 then begin Inc(failures); Writeln('FAIL ',c,' row ',i,' col ',k,' error ',err);end;
          end;
        end;
      end;
    end;
  end;
  Close(log);Writeln('checks=',checks,' failures=',failures,' max_relative_error=',maxerr);
  if failures>0 then Halt(1);
end.
