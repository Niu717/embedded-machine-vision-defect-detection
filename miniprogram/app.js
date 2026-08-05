const USE_CLOUD_REPORTS = false

App({
  onLaunch() {
    if (USE_CLOUD_REPORTS && wx.cloud) {
      wx.cloud.init({ traceUser: true })
    }
  },
  globalData: {
    projectName: '机器视觉缺陷检测系统',
    useCloudReports: USE_CLOUD_REPORTS
  }
})
