const reportService = require('../../services/report_service')
Page({
  data: { report: null, reports: [] },
  onShow() { reportService.listReports().then(reports => this.setData({ report: reports[0], reports })) },
  openReports() { wx.switchTab({ url: '/pages/reports/reports' }) },
  openDetail() { if (this.data.report) wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${this.data.report.id}` }) }
})
