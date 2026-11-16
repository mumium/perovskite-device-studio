"""Additional resolution check; preserve unsuccessful attempts explicitly."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import study as s

if __name__=='__main__':
    s.perf._run_engine=s.observed_engine
    rows=[]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(s.physical,'dense_base',1e16,1e16,0.,2000,40,.005),
                  pool.submit(s.physical,'dense_peak3e17',3e17,3e17,0.,2000,40,.005),
                  pool.submit(s.physical,'dense_peak3e17_Nt1e11',3e17,3e17,1e11,2000,40,.005),
                  pool.submit(s.conditional,'dense_base',1e16,1e16,2000,40,.005),
                  pool.submit(s.conditional,'dense_peak3e17',3e17,3e17,2000,40,.005)]
            for f in as_completed(jobs):
                rows.append(f.result());s.save_json(s.HERE/'convergence_summary.json',rows)
    finally:s.perf._run_engine=s.original_engine
    if all(r['success'] for r in rows):
        from refine import states
        print('STATES',states('dense_peak3e17_Nt1e11'),flush=True)
