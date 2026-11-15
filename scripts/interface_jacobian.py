"""Reproduce the PDS steady-state interface-SRH Jacobian correction.

The physical rates are unchanged. An interface has exactly two density
arguments per carrier, so each row has a self and an adjacent derivative.
"""


def correct_interface_jacobian(text):
    marker = 'PDS modification 2026-11-15: exact interface-SRH Jacobian'
    if marker in text:
        raise ValueError('Interface Jacobian correction is already present')
    for carrier, field, density, coeff, emission, opposite, thermal in [
        ('n', 'Rn', 'n', 'ai', 'ci', 'sum_bj', 'sum_cj'),
        ('p', 'Rp', 'p', 'bi', 'di', 'sum_aj', 'sum_dj'),
    ]:
        proc = text.index('PROCEDURE Calc_Recombination_'+carrier+'(')
        start = text.index('{Calculate the partial derivative of recombination', proc)
        end = text.index('END; {steady-state, loop over trap levels}', start)
        old = text[start:end]
        if old.count(field+'.int_cont_') != 12:
            raise ValueError('Unexpected upstream interface Jacobian block')
        other_sum = 'sum_aj + sum_dj' if carrier == 'n' else 'sum_bj + sum_cj'
        terms = []
        for point, emit, diagonal in [('ii', emission+'R', 'up'),
                                      ('ii+1', emission+'L', 'lo')]:
            numerator = f'({coeff}*{density}[{point}]*({opposite} + {thermal}) - {emit}*({other_sum}))'
            terms.append(f'''{{{marker}.
                 No dependence on the point outside the two-point interface.}}
                dum1:=iiw*{coeff}*((({opposite} + {thermal}) - {emit})*f_ti_level_inv_denom - {numerator}*SQR(f_ti_level_inv_denom));
                dum2:=iiw*{coeff}*(-{emit}*f_ti_level_inv_denom - {numerator}*SQR(f_ti_level_inv_denom));
                {field}.int_cont_m[{point}]:={field}.int_cont_m[{point}] + dum1;
                {field}.int_cont_{diagonal}[{point}]:={field}.int_cont_{diagonal}[{point}] + dum2;
''')
        text = text[:start]+'\n'.join(terms)+'\n\t\t\t'+text[end:]
    return text
