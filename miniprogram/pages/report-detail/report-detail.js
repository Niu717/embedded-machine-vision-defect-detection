const reports = require('../../mock/reports')
Page({
  data: { report: null },
  onLoad(query) { this.setData({ report: reports.find(item => item.id === query.id) || reports[0] }) },
  share() { wx.showToast({ title: '接入云端后可分享 PDF 报告', icon: 'none' }) }
})
