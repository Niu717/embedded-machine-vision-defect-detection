const reportService = require('../../services/report_service')
Page({
  data: { report: null },
  onLoad(query) { reportService.getReport(query.id).then(report => this.setData({ report })) },
  share() {
    const report = this.data.report
    if (!report) return
    wx.showLoading({ title: '生成 PDF 中' })
    wx.cloud.callFunction({
      name: 'reportService',
      data: { action: 'generatePdf', id: report.id, report },
    }).then(response => wx.cloud.downloadFile({ fileID: response.result.fileID }))
      .then(download => new Promise((resolve, reject) => wx.openDocument({
        filePath: download.tempFilePath,
        fileType: 'pdf',
        showMenu: true,
        success: resolve,
        fail: reject,
      })))
      .catch(() => wx.showToast({ title: '生成失败，请稍后重试', icon: 'none' }))
      .finally(() => wx.hideLoading())
  }
})
