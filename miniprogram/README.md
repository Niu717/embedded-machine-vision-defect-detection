# 微信小程序：检测报告中心

直接导入微信开发者工具，可使用 `touristappid` 体验报告概览、报告列表和报告详情。

电脑端每次检测会话会自动生成 `results/session_xxx/report.json` 和 `report.html`。当前小程序使用 `mock/reports.js` 演示数据；正式同步将通过微信云开发或后端 API 上传 `report.json`，手机不能直接读取笔记本电脑磁盘。
