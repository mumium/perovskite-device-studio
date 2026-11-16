"""Add an opt-in native TMM-only exit without changing physical equations."""


def patch_optics_only(text):
    if 'PDS_OPTICS_ONLY' in text:
        raise ValueError('Optics-only branch already present')
    anchor = '\tuitv , log : TEXT; {the output files}'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected SimSS output declarations')
    text = text.replace(anchor, anchor+'\n    PDSOpticalFile : TEXT;\n    PDSOpticalIndex : INTEGER;')
    anchor = '    Init_Generation_Profile(stv, log, par); {init. the stv.orgGm array. This is the SHAPE of the profile}'
    if text.count(anchor) != 1:
        raise ValueError('Unexpected generation initialization')
    branch = '''
    {PDS modification 2026-11-16: opt-in optical-only run. Uses the exact
     upstream TMM and grid; no electrical state is solved or reported.}
    IF GetEnvironmentVariable('PDS_OPTICS_ONLY') = '1' THEN
    BEGIN
        Assign(PDSOpticalFile, 'OpticsOnly.dat');
        Rewrite(PDSOpticalFile);
        WriteLn(PDSOpticalFile, 'x G_ehp lid');
        FOR PDSOpticalIndex:=0 TO par.NP+1 DO
            WriteLn(PDSOpticalFile, stv.x[PDSOpticalIndex]:29, ' ',
                (stv.orgGm[PDSOpticalIndex]*par.G_frac):29, ' ', stv.lid[PDSOpticalIndex]);
        Close(PDSOpticalFile);
        Finalize_Log_File(log, 'PDS optical-only: no electrical solution or J-V metrics.');
        Halt(0);
    END;
'''
    return text.replace(anchor, anchor+'\n'+branch)
