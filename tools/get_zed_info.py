import pyzed.sl as sl

z = sl.Camera()
p = sl.InitParameters()
p.camera_resolution = sl.RESOLUTION.HD1200      # 1920x1200 @60
p.camera_fps = 60
p.depth_mode = sl.DEPTH_MODE.NONE               # SDK depth 안 쓴다 (Jetson 부담 제거)
z.open(p)

cc = z.get_camera_information().camera_configuration
c  = cc.calibration_parameters                  # ★ rectified
print("res  ", cc.resolution.width, cc.resolution.height)
print("left ", c.left_cam.fx, c.left_cam.fy, c.left_cam.cx, c.left_cam.cy, c.left_cam.disto)
print("right", c.right_cam.fx, c.right_cam.fy, c.right_cam.cx, c.right_cam.cy)
print("basel", c.get_camera_baseline())         # mm
print("raw  ", cc.calibration_parameters_raw.left_cam.disto)   # 왜곡 원본(참고용)