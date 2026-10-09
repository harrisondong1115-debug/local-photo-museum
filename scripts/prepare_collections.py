"""Copy only a user-approved manifest into a fresh Unreal Collections folder."""
import argparse, hashlib, json, shutil
from pathlib import Path
from verify_catalogue import SAFE_ID, contained_file, verify

def prepare(manifest,source_root,output):
    source_root=Path(source_root).resolve();output=Path(output).resolve()
    if output.exists(): raise ValueError('Output already exists; choose a fresh directory')
    if output.is_relative_to(source_root): raise ValueError('Keep generated output outside source photos')
    source=json.loads(Path(manifest).read_text(encoding='utf-8'))
    planned={};albums=[];album_ids=set()
    for album in source.get('albums',[]):
        aid=album.get('id','')
        if not isinstance(aid,str) or not SAFE_ID.fullmatch(aid) or aid in album_ids: raise ValueError('Invalid or duplicate album ID')
        album_ids.add(aid);photos=[];photo_ids=set()
        if not isinstance(album.get('title'),str) or not album['title'].strip(): raise ValueError('Missing album title')
        for photo in album.get('photos',[]):
            pid=photo.get('id','')
            if not isinstance(pid,str) or not SAFE_ID.fullmatch(pid) or pid in photo_ids: raise ValueError('Invalid or duplicate photo ID')
            photo_ids.add(pid)
            if not isinstance(photo.get('name'),str): raise ValueError('Missing photo name')
            file=contained_file(source_root,photo.get('hires_file'))
            with file.open('rb') as f:
                if f.read(3)!=b'\xff\xd8\xff': raise ValueError('Only JPEG files supported')
            if pid in planned and planned[pid]!=file: raise ValueError('One photo ID refers to different source files')
            planned[pid]=file
            photos.append({'id':pid,'name':photo['name'],'hires_file':'Photos/'+pid+'.jpg'})
        if not photos: raise ValueError('Empty approved album')
        albums.append({'id':aid,'title':album['title'],'photos':photos})
    if not albums: raise ValueError('No approved albums')
    (output/'Photos').mkdir(parents=True)
    for pid,file in planned.items():
        target=output/'Photos'/(pid+'.jpg');shutil.copy2(file,target)
        if hashlib.sha256(file.read_bytes()).digest()!=hashlib.sha256(target.read_bytes()).digest():
            raise RuntimeError('Copied bytes differ: '+pid)
    (output/'catalogue.json').write_text(json.dumps({'version':5,'albums':albums},ensure_ascii=False,indent=2),encoding='utf-8')
    return verify(output)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.manifest,a.source_root,a.output),indent=2))
if __name__=='__main__': main()
