"""Summarize actual Unreal CSV counters, preserving stalls and missing data."""
import argparse,csv,json,math,statistics
from pathlib import Path

def summarize(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    result={'source':'Unreal CSV profiler; screenshot saving may add stalls','counters':{}}
    for name in ('FrameTime','GPUTime','GameThreadTime','GPUMem/LocalUsedMB'):
        values=[]
        for row in rows:
            try:
                v=float(row[name])
                if math.isfinite(v): values.append(v)
            except (ValueError,TypeError,KeyError): pass
        if not values:
            result['counters'][name]=None;continue
        values.sort()
        result['counters'][name]={'samples':len(values),'mean':statistics.mean(values),'p99':values[math.ceil(len(values)*.99)-1],'max':values[-1]}
        if name=='FrameTime': result['frames_above_50ms']=sum(v>50 for v in values)
    if result['counters']['FrameTime'] is None: raise ValueError('No actual FrameTime counter found')
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv',type=Path)
    a=p.parse_args();print(json.dumps(summarize(a.csv),indent=2))
if __name__=='__main__': main()
