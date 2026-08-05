const reports = require('../../mock/reports')
Page({
  data: { report: reports[0], reports },
  onShow() { this.setData({ report: reports[0], reports }) },
  openReports() { wx.switchTab({ url: '/pages/reports/reports' }) },
  openDetail() { wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${this.data.report.id}` }) }
})
