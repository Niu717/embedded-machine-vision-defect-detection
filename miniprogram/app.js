App({
  onLaunch() {
    if (wx.cloud) {
      wx.cloud.init({ traceUser: true })
    }
  },
  globalData: {
    projectName: '机器视觉缺陷检测系统',
    useCloudReports: false
  }
})
