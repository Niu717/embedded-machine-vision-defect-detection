# 云端报告同步准备

当前小程序默认读取电脑端生成的本地汇总数据，方便在微信开发者工具中演示。要在真实手机微信上查看报告，需要完成以下一次性配置：

1. 注册或使用已有微信小程序 AppID，并在微信开发者工具中导入 `miniprogram` 文件夹。
2. 在工具内开通“云开发”，创建环境。
3. 右键 `cloudfunctions/reportService`，选择“上传并部署：云端安装依赖”。
4. 创建云数据库集合 `inspection_reports`；开发阶段可设置为仅创建者可读写。
5. 在 `app.js` 的 `globalData` 中将 `useCloudReports` 改为 `true`，并在 `wx.cloud.init` 中填写环境 ID。

云函数已提供 `list`、`detail` 和 `upsert` 三种动作。电脑端 `report.json` 的字段格式与小程序报告对象保持一致；以后只需安全地把报告上传到云函数或后台 API，即可在手机端显示。
