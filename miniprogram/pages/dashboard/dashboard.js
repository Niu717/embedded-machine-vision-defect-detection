const reportService = require('../../services/report_service')
Page({
  data: { report: null, reports: [], cloudEnabled: getApp().globalData.useCloudReports },
  onShow() { reportService.listReports().then(reports => this.setData({ report: reports[0], reports })) },
  openReports() { wx.switchTab({ url: '/pages/reports/reports' }) },
  openDetail() { if (this.data.report) wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${this.data.report.id}` }) },
  seedCloudReports() {
    wx.showLoading({ title: '同步报告中' })
    reportService.seedLocalReports()
      .then(reports => {
        this.setData({ report: reports[0] || null, reports })
        wx.showToast({ title: '报告已同步云端', icon: 'success' })
      })
      .catch(() => wx.showToast({ title: '同步失败，请检查云函数', icon: 'none' }))
      .finally(() => wx.hideLoading())
  },
})
