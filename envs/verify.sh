#!/usr/bin/env bash
# envs/verify.sh — M0 스모크 테스트. 각 venv 에서 import + 실제 CUDA 커널 실행까지 확인한다.
#   bash envs/verify.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"; source envs/env.sh
fail=0

echo "=== [1/5] torch / sm_120 ==="
envs/stereo/bin/python - <<'EOF' || exit 1
import torch
cap=torch.cuda.get_device_capability(0)
assert torch.cuda.is_available() and cap==(12,0), f"sm_{cap[0]}{cap[1]} 예상과 다름"
a=torch.randn(2048,2048,device='cuda',dtype=torch.float16)
assert torch.isfinite(a@a).all()
c=torch.nn.Conv2d(3,32,3,padding=1).cuda()(torch.randn(2,3,256,256,device='cuda')); c.sum().backward()
print(f"  torch {torch.__version__} | {torch.cuda.get_device_name(0)} sm_{cap[0]}{cap[1]} | matmul·cudnn·backward OK")
EOF

echo "=== [2/5] nvcc (ws 로컬 CUDA_HOME) ==="
nvcc --version | tail -1 | sed 's/^/  /' || fail=1

echo "=== [3/5] FoundationStereo ==="
envs/stereo/bin/python - <<'EOF' || fail=1
import sys; sys.path.insert(0,'third_party/FoundationStereo')
import torch, open3d, numpy
from core.foundation_stereo import FoundationStereo
print(f"  py{sys.version.split()[0]} numpy{numpy.__version__} open3d{open3d.__version__} | import OK")
EOF

echo "=== [4/5] FoundationPose (pytorch3d + nvdiffrast + mycpp) ==="
envs/pose/bin/python - <<'EOF' || fail=1
import sys, numpy as np, torch
sys.path.insert(0,'third_party/FoundationPose'); sys.path.insert(0,'third_party/FoundationPose/mycpp/build')
import pytorch3d, nvdiffrast.torch as dr, mycpp
glctx=dr.RasterizeCudaContext()
pos=torch.tensor([[[-0.8,-0.8,0.,1.],[0.8,-0.8,0.,1.],[0.,0.8,0.,1.]]],device='cuda')
tri=torch.tensor([[0,1,2]],device='cuda',dtype=torch.int32)
rast,_=dr.rasterize(glctx,pos,tri,resolution=[256,256])
assert int((rast[...,3]>0).sum())>1000
from pytorch3d.transforms import so3_exp_map; assert so3_exp_map(torch.randn(4,3,device='cuda')).shape==(4,3,3)
out=mycpp.cluster_poses(30.,99999.,np.tile(np.eye(4,dtype=np.float32),(8,1,1)),np.eye(4,dtype=np.float32)[None])
import estimater
print(f"  py{sys.version.split()[0]} numpy{np.__version__} pytorch3d{pytorch3d.__version__} | nvdiffrast raster + mycpp + estimater OK")
EOF

echo "=== [5/5] Segmentation (SAM3 / SAM-6D ISM) ==="
envs/seg_sam3/bin/python - <<'EOF' || fail=1
import sys, numpy, torch
from sam3 import build_sam3_image_model, build_sam3_predictor
print(f"  sam3: py{sys.version.split()[0]} numpy{numpy.__version__} | builders OK")
EOF
( cd third_party/SAM-6D/SAM-6D/Instance_Segmentation_Model && "$ROOT/envs/seg_sam6d/bin/python" - <<'EOF' ) || fail=1
import sys; sys.path.insert(0,'.')
import numpy, pytorch_lightning as pl
from model.dinov2 import CustomDINOv2
from model.detector import Instance_Segmentation_Model
from segment_anything.build_sam import sam_model_registry
print(f"  sam6d-ism: py{sys.version.split()[0]} numpy{numpy.__version__} lightning{pl.__version__} | SAM 경로 OK")
EOF

echo
[ "$fail" = 0 ] && echo "✅ M0 런타임 검증 통과" || { echo "❌ 실패 있음"; exit 1; }
