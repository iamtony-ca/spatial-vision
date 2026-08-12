"""envs/blenderproc_smoke.py — BlenderProc 부트스트랩 스모크.

    envs/seg_sam6d/bin/blenderproc run --blender-install-path envs/blender envs/blenderproc_smoke.py

`blenderproc run` 은 첫 실행에서 Blender(~1GB)를 내려받아 압축을 풀고, 필요한 pip 패키지를
Blender 번들 python 에 설치한다. 이 스크립트의 목적은 그 부트스트랩을 **한 번 강제로 돌려서**
M4 템플릿 렌더 전에 실패를 미리 드러내는 것이다(렌더 도중 처음 받으면 원인 진단이 섞인다).

렌더는 하지 않는다 — bproc 이 import 되고 씬을 초기화할 수 있으면 충분하다.
"""

import blenderproc as bproc

bproc.init()
print("  blenderproc 부트스트랩 OK (Blender 실행 + bproc.init 성공)")
