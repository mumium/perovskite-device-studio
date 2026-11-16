"""Isolate doping in the conditional reference with fixed virtual contacts."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import study as s

if __name__=='__main__':
    rows=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(s.conditional,'fixed_base',1e16,1e16,1400,24,.01,False),
              pool.submit(s.conditional,'fixed_peak3e17',3e17,3e17,1400,24,.01,False)]
        for f in as_completed(jobs):
            rows.append(f.result());s.save_json(s.HERE/'fixed_contacts_summary.json',rows)
