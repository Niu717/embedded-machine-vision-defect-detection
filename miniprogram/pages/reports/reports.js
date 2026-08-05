const reportService = require('../../services/report_service')
Page({
  data: { reports: [] },
  onShow() { reportService.listReports().then(reports => this.setData({ reports })) },
  openDetail(e) { wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${e.currentTarget.dataset.id}` }) }
})
