import sys, json, cv2, numpy as np, torch
from pathlib import Path
sys.path.insert(0, "/isaac-sim/volume/spatial_manipulation_ws/src/vision")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image
from spatial_vision.stages.segment_sam3 import build
from spatial_vision.contracts import select_index

CAP=Path("runs/S44L_030"); FR="frame_0013"; PROMPT="cube shaped sealed plastic wafer pod"
proc,_=build(Path("weights/sam3/sam3.pt"), 0.05)
img=Image.open(CAP/FR/"left.png").convert("RGB")
with torch.autocast("cuda", dtype=torch.bfloat16):
    st=proc.set_image(img); o=proc.set_text_prompt(state=st, prompt=PROMPT)
npf=lambda x: np.asarray(x.detach().float().cpu())
m,s=npf(o["masks"]),npf(o["scores"]).reshape(-1)
m=m.squeeze(1) if m.ndim==4 else m; m=m>0.5 if m.dtype!=bool else m
gt=cv2.imread(str(CAP/FR/"mask_full.png"),0)>127
iou=np.array([(x&gt).sum()/max((x|gt).sum(),1) for x in m])
i9 =select_index(m,s,"center",0.3,0.9); i3=select_index(m,s,"center",0.3,0.3); it=int(iou.argmax())
print(f"후보 {len(m)} · 정답 idx {it}(score {s[it]:.3f}, IoU {iou[it]:.3f}) · "
      f"0.9 선택 {i9}(score {s[i9]:.3f}, IoU {iou[i9]:.3f}) · 0.3 선택 {i3}(IoU {iou[i3]:.3f})")

fig=plt.figure(figsize=(13.2,5.0),dpi=150)
ax=fig.add_axes([0.005,0.02,0.575,0.88])
im=cv2.cvtColor(np.array(img),cv2.COLOR_RGB2BGR).copy()
im[m[i9]]=(0.45*im[m[i9]]+0.55*np.array([60,60,235])).astype(np.uint8)
for mk,c,t in ((gt,(80,220,80),5),(m[i3],(235,180,60),2)):
    cs,_=cv2.findContours(mk.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(im,cs,-1,c,t)
ax.imshow(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)); ax.axis("off")
ax.set_title("What the pipeline picked  (sim, 0.29 m, 2 FOUPs in scene)",fontsize=11.5,pad=8)
for txt,col,dy in (("GREEN  = true target (GT)","#2ca02c",0),
                   ("RED fill = picked at score_frac 0.9  ← WRONG","#c0392b",1),
                   ("BLUE   = picked at score_frac 0.3  (hidden under green = correct)","#1f77b4",2)):
    ax.text(0.012,0.965-0.055*dy,txt,transform=ax.transAxes,fontsize=10,color=col,
            weight="bold",va="top",bbox=dict(fc="white",ec="none",alpha=.82,pad=2))

bx=fig.add_axes([0.645,0.13,0.335,0.74])
order=np.argsort(-s); y=np.arange(len(s))
cols=["#bdbdbd"]*len(s)
cols[list(order).index(it)]="#2ca02c"; cols[list(order).index(i9)]="#c0392b"
bx.barh(y,s[order],color=cols,height=.68)
bx.axvline(0.9*s.max(),color="#c0392b",ls="--",lw=2)
bx.axvline(0.3*s.max(),color="#1f77b4",ls="--",lw=2)
bx.text(0.9*s.max()-0.012,len(s)-0.3,"gate 0.9",color="#c0392b",fontsize=9.5,ha="right",weight="bold")
bx.text(0.3*s.max()+0.012,len(s)-0.3,"gate 0.3",color="#1f77b4",fontsize=9.5,weight="bold")
bx.text(s[it]+0.012,list(order).index(it),f"true target  {s[it]:.3f}  ← below the 0.9 gate",
        color="#2ca02c",fontsize=10,va="center",weight="bold")
bx.text(s[i9]+0.012,list(order).index(i9),f"distractor FOUP  {s[i9]:.3f}",
        color="#c0392b",fontsize=10,va="center",weight="bold")
bx.invert_yaxis(); bx.set_yticks([]); bx.set_xlim(0,1.34); bx.set_xlabel("SAM3 instance score")
bx.set_title("Why: the 0.9 gate deletes the true target\nbefore the centre rule ever runs",fontsize=11.5,pad=8)
bx.grid(axis="x",alpha=.25); [bx.spines[k].set_visible(False) for k in ("top","right","left")]
fig.savefig("docs/figs/fig2_misselection.png",bbox_inches="tight"); print("fig2 ok")
