const demoReports = [
  { id: 'session_20260803_143900', mode: '瓶盖检测', time: '2026-08-03 14:39:00', total: 30, passed: 29, failed: 1, yieldRate: '96.7%', verdict: 'FAIL', result: 'FAIL SCRATCH', defects: ['浅划痕'], note: '浅划痕受反光影响，建议固定补光灯亮度后复测。' },
  { id: 'metal_demo_001', mode: '金属件检测', time: '待采样', total: 0, passed: 0, failed: 0, yieldRate: '--', verdict: 'READY', result: '待建立标准样本', defects: [], note: '请固定金属工件和侧向补光灯后保存标准图。' },
  { id: 'pcb_demo_001', mode: 'PCB 检测', time: '待采样', total: 0, passed: 0, failed: 0, yieldRate: '--', verdict: 'READY', result: '待建立标准样本', defects: [], note: '可检测可见布局差异、缺件、污点和板边缺损。' }
]

let runtimeReports = []
try {
  runtimeReports = require('./runtime_reports')
} catch (error) {
  runtimeReports = []
}

module.exports = runtimeReports.length ? runtimeReports : demoReports
