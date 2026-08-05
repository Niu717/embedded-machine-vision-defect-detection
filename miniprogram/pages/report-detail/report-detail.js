const reportService = require('../../services/report_service')
Page({
  data: { report: null },
  onLoad(query) { reportService.getReport(query.id).then(report => this.setData({ report })) },
  share() { wx.showToast({ title: '接入云端后可分享 PDF 报告', icon: 'none' }) }
})
