"""Invert the museum shader's panorama lookup. Pure Python; no image upload."""
import argparse, json, math
from pathlib import Path

def checked_basis(basis):
    if len(basis)!=3 or any(len(row)!=3 for row in basis):
        raise ValueError('Expected three FBX basis columns in centimetres')
    columns=[[float(v)/100 for v in row] for row in basis]
    if any(not math.isfinite(v) for row in columns for v in row):
        raise ValueError('Basis must contain finite numbers')
    for i in range(3):
        for j in range(3):
            dot=sum(columns[i][k]*columns[j][k] for k in range(3))
            if abs(dot-(1 if i==j else 0))>1e-4:
                raise ValueError('Basis must be orthogonal at 100 cm per metre')
    return columns

def sun_direction(basis, uv, lookup_yaw_degrees):
    columns=checked_basis(basis)
    if len(uv)!=2 or any(not math.isfinite(float(v)) or not 0<=float(v)<=1 for v in uv):
        raise ValueError('UV must be two finite numbers from 0 to 1')
    if not math.isfinite(float(lookup_yaw_degrees)):
        raise ValueError('Yaw must be finite')
    phi=(uv[0]-.5)*2*math.pi; theta=uv[1]*math.pi
    x=math.sin(theta)*math.cos(phi); y=math.sin(theta)*math.sin(phi); z=math.cos(theta)
    a=math.radians(-lookup_yaw_degrees)
    source=(math.cos(a)*x-math.sin(a)*y,math.sin(a)*x+math.cos(a)*y,z)
    world=[sum(columns[j][i]*source[j] for j in range(3)) for i in range(3)]
    length=math.sqrt(sum(v*v for v in world))
    return tuple(v/length for v in world)

def panorama_uv(direction,basis,lookup_yaw_degrees):
    columns=checked_basis(basis)
    length=math.sqrt(sum(v*v for v in direction))
    if length==0: raise ValueError('Direction cannot be zero')
    b=[sum(direction[i]/length*columns[j][i] for i in range(3)) for j in range(3)]
    a=math.radians(lookup_yaw_degrees)
    x=math.cos(a)*b[0]-math.sin(a)*b[1]; y=math.sin(a)*b[0]+math.cos(a)*b[1]
    return (.5+math.atan2(y,x)/(2*math.pi),math.acos(max(-1,min(1,b[2])))/math.pi)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uv',type=float,nargs=2,required=True)
    parser.add_argument('--yaw',type=float,required=True,help='Lookup rotation in shader, not visual object rotation')
    parser.add_argument('--basis',type=Path,required=True,help='ImportReport.json containing fbx_basis_cm')
    args=parser.parse_args()
    basis=json.loads(args.basis.read_text(encoding='utf-8'))['fbx_basis_cm']
    direction=sun_direction(basis,args.uv,args.yaw)
    print(json.dumps({'to_sun':direction,'directional_light_forward':[-v for v in direction],
        'sun_elevation_degrees':math.degrees(math.asin(direction[2])),
        'sun_azimuth_world_degrees':math.degrees(math.atan2(direction[1],direction[0])),
        'roundtrip_uv':panorama_uv(direction,basis,args.yaw)},indent=2))

if __name__=='__main__': main()
