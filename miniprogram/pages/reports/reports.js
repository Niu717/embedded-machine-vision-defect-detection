const reports = require('../../mock/reports')
Page({ data: { reports }, openDetail(e) { wx.navigateTo({ url: `/pages/report-detail/report-detail?id=${e.currentTarget.dataset.id}` }) } })
