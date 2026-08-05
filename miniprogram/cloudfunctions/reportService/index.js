const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const collection = db.collection('inspection_reports')

exports.main = async (event) => {
  const action = event.action || 'list'
  if (action === 'list') {
    const result = await collection.orderBy('time', 'desc').limit(100).get()
    return { reports: result.data }
  }
  if (action === 'detail') {
    const result = await collection.where({ id: event.id }).limit(1).get()
    return { report: result.data[0] || null }
  }
  if (action === 'upsert') {
    if (!event.report || !event.report.id) throw new Error('report.id is required')
    const previous = await collection.where({ id: event.report.id }).limit(1).get()
    if (previous.data.length) {
      await collection.doc(previous.data[0]._id).set({ data: event.report })
    } else {
      await collection.add({ data: event.report })
    }
    return { ok: true }
  }
  throw new Error(`Unsupported action: ${action}`)
}
