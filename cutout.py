"""案内人の原画シート(8ポーズ)から、背景の紙色を抜いて1ポーズずつ透過PNGに切り出す。
使い方: python3 tools/cutout.py   → assets/host/poses/*.png を上書き
原画を描き直したら、これを再実行してから render/ を回す。"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / 'assets/host/master/sake_host_master.png'
OUTDIR = ROOT / 'assets/host/poses'
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi
im=np.asarray(Image.open(MASTER).convert('RGB')).astype(float)
H,W,_=im.shape
# estimate paper color from border
border=np.concatenate([im[:8].reshape(-1,3),im[-8:].reshape(-1,3),im[:,:8].reshape(-1,3),im[:,-8:].reshape(-1,3)])
paper=np.median(border,0); print('paper',paper)
d=np.sqrt(((im-paper)**2).sum(2))
# background candidates: close to paper
bgc=d<54
# keep only bg connected to border
lab,n=ndi.label(bgc)
edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
bg=np.isin(lab,list(edge))
fg=~bg
fg=ndi.binary_opening(fg,iterations=1)
holes=ndi.binary_fill_holes(fg)&~fg
hl,hn=ndi.label(holes)
hs=ndi.sum(np.ones_like(hl),hl,range(1,hn+1))
small=np.isin(hl,[i+1 for i,s in enumerate(hs) if s<400])
fg=fg|small
lab2,n2=ndi.label(ndi.binary_dilation(fg,iterations=6))
sizes=ndi.sum(np.ones_like(lab2),lab2,range(1,n2+1))
print(n2, sorted(sizes)[-10:])
big=[i+1 for i,s in enumerate(sizes) if s>20000]
objs=[]
for i in big:
    m=(lab2==i)&fg
    ys,xs=np.where(m); objs.append((ys.min(),xs.min(),ys.max(),xs.max(),m))
objs.sort(key=lambda o:((o[0]+o[2])/2>H/2, o[1]))
names=['normal','talk','point','surprise','think','tokkuri','book','welcome']
for name,(y0,x0,y1,x1,m) in zip(names,objs):
    pad=12
    y0,x0=max(0,y0-pad),max(0,x0-pad); y1,x1=min(H,y1+pad),min(W,x1+pad)
    a=m[y0:y1,x0:x1].astype(np.uint8)*255
    A=Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8))
    rgb=Image.fromarray(im[y0:y1,x0:x1].astype(np.uint8))
    rgb.putalpha(A); rgb.save(OUTDIR / f'{name}.png'); print(name,rgb.size)
