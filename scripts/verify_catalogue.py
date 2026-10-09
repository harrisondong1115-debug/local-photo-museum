"""Validate an explicitly approved local collection; never scan other folders."""
import argparse, json, re
from pathlib import Path

SAFE_ID=re.compile(r'[A-Za-z0-9_-]{1,128}\Z')

def contained_file(root,relative):
    # Reject drive letters, rooted paths and backslash traversal on all hosts.
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Use a relative forward-slash photo path')
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts: raise ValueError('Photo path escapes source root')
    result=(root/path).resolve()
    if not result.is_relative_to(root.resolve()): raise ValueError('Photo symlink escapes source root')
    if not result.is_file(): raise ValueError('Missing approved photo: '+relative)
    return result

def verify(root):
    root=Path(root).resolve()
    data=json.loads((root/'catalogue.json').read_text(encoding='utf-8'))
    albums=data.get('albums')
    if not isinstance(albums,list) or not albums: raise ValueError('Expected nonempty albums array')
    ids=set(); unique=set(); count=0
    for album in albums:
        aid=album.get('id','')
        if not isinstance(aid,str) or not SAFE_ID.fullmatch(aid) or aid in ids: raise ValueError('Invalid or duplicate album ID')
        ids.add(aid)
        if not isinstance(album.get('title'),str) or not album['title'].strip(): raise ValueError('Missing album title')
        if not isinstance(album.get('photos'),list) or not album['photos']: raise ValueError('Empty album')
        photo_ids=set()
        for photo in album['photos']:
            pid=photo.get('id','')
            if not isinstance(pid,str) or not SAFE_ID.fullmatch(pid) or pid in photo_ids: raise ValueError('Invalid or duplicate photo ID within album')
            photo_ids.add(pid)
            if not isinstance(photo.get('name'),str): raise ValueError('Missing photo name')
            expected='Photos/'+pid+'.jpg'
            if photo.get('hires_file')!=expected: raise ValueError('Runtime expects '+expected)
            image=contained_file(root,expected)
            with image.open('rb') as f:
                if f.read(3)!=b'\xff\xd8\xff': raise ValueError('Runtime expects JPEG input')
            unique.add(pid);count+=1
    return {'albums':len(ids),'photo_entries':count,'unique_jpegs':len(unique),'structural_checks':'passed',
        'full_image_decode_tested':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    args=parser.parse_args();print(json.dumps(verify(args.root),indent=2))
if __name__=='__main__': main()
