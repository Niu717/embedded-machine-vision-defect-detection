// The current formal mini-program AppID is bound to its free CloudBase environment.
// Keep the environment dynamic so a later environment rename does not require code changes.
const USE_CLOUD_REPORTS = true

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
