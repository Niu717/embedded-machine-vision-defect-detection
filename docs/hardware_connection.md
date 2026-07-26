# 硬件接线（第一版）

## 笔记本与摄像头

- UVC 摄像头直接接笔记本 USB。
- 环形灯使用自带电源，不与 STM32 或舵机共用电源。

## 笔记本与 STM32

使用 USB-TTL：

| USB-TTL | STM32F103C8T6 |
|---|---|
| GND | GND |
| TXD | PA10（USART1_RX） |
| RXD | PA9（USART1_TX） |

USB-TTL 逻辑电平必须为 3.3V。

## SG90 舵机

| SG90 线色 | 连接位置 |
|---|---|
| 红色 | 5V 3A 电源正极 |
| 棕色/黑色 | 5V 3A 电源负极，同时连接 STM32 GND |
| 橙色/黄色 | STM32 PA0（PWM 输出） |

不要把 5V 舵机电源接入 STM32 的 3.3V 引脚。
