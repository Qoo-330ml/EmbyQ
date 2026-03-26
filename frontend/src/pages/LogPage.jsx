import { useEffect, useState, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { apiRequest } from '@/types/api'

export default function LogPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const logContainerRef = useRef(null)

  useEffect(() => {
    const loadLogs = async () => {
      try {
        const response = await apiRequest('/admin/logs')
        setLogs(response.logs)
      } catch (e) {
        console.error('加载日志失败:', e)
      } finally {
        setLoading(false)
      }
    }
    loadLogs()
  }, [])

  useEffect(() => {
    // 滚动到最新的日志
    if (!loading && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs, loading])

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl p-4 pb-8 md:p-8">
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">加载中...</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl p-4 pb-8 md:p-8">
      <Card>
        <CardHeader>
          <CardTitle>安全日志</CardTitle>
        </CardHeader>
        <CardContent>
          <div 
            ref={logContainerRef}
            className="max-h-[600px] overflow-y-auto border rounded-md p-4 bg-muted/50"
          >
            {logs.length === 0 ? (
              <p className="text-muted-foreground text-center">暂无日志</p>
            ) : (
              <div className="space-y-2">
                {logs.map((log) => (
                  <div key={log.id} className="p-2 border-b last:border-b-0">
                    <div className="flex flex-col md:flex-row md:items-center gap-2 text-sm">
                      <span className="text-muted-foreground w-32 md:w-48">{log.timestamp}</span>
                      <span className="font-medium w-24 md:w-32">{log.username || log.user_id}</span>
                      <span className="w-24 md:w-32">{log.trigger_ip}</span>
                      <span className="w-16">{log.active_sessions} 会话</span>
                      <span className={`w-16 font-semibold ${log.action === 'DISABLE' ? 'text-red-600' : 'text-green-600'}`}>
                        {log.action === 'DISABLE' ? '封禁' : '启用'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}