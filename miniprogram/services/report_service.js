const localReports = require('../mock/reports')

function canUseCloud() {
  return getApp().globalData.useCloudReports && !!wx.cloud
}

function listReports() {
  if (!canUseCloud()) return Promise.resolve(localReports)
  return wx.cloud.callFunction({ name: 'reportService', data: { action: 'list' } })
    .then(response => response.result.reports || localReports)
    .catch(() => localReports)
}

function getReport(id) {
  return listReports().then(reports => reports.find(item => item.id === id) || reports[0])
}

module.exports = { listReports, getReport }
