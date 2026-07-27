# 嵌入式机器视觉工件缺陷检测系统

上位机使用 Python、OpenCV 和串口通信；STM32 负责指示、报警和分拣执行。

## 当前里程碑

1. 摄像头实时预览与图像采集
2. 瓶盖定位及基础缺陷判定
3. 串口输出 `OK` / `NG`
4. STM32 声光提示与舵机分拣

## 目录

- `pc_app/`：笔记本上位机程序
- `stm32/`：STM32 工程与说明
- `docs/`：接线、测试记录与论文素材
- `samples/`：采集的正常/缺陷样本（不提交大文件）

## 运行上位机

摄像头接入笔记本后，双击 `run_camera.bat`。当前电脑默认使用编号为 1 的
`ML Camera` 外接工业摄像头。如没有画面，用命令提示符在 `pc_app` 目录切换编号：

```bat
C:\Users\nzr\AppData\Local\Programs\Python\Python313\python.exe main.py --camera 0
```

按键：`空格` 开始/停止检测，`S` 保存当前画面，`Q` 退出。
