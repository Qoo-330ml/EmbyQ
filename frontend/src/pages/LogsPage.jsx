import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertCircle, RefreshCw, WrapText } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { apiRequest } from '@/lib/api'

const MAX_VISIBLE_LINES = 500

function getLineTone(line) {
  if (/\b(ERROR|CRITICAL|Traceback|Exception)\b/i.test(line)) return 'text-red-300'
  if (/\b(WARNING|WARN)\b/i.test(line)) return 'text-amber-300'
  if (/\b(INFO)\b/i.test(line)) return 'text-sky-300'
  if (/\b(DEBUG)\b/i.test(line)) return 'text-slate-400'
  if (/\b(成功|已启用|已启动|完成)\b/.test(line)) return 'text-emerald-300'
  return 'text-green-100'
}

export default function LogsPage() {
  const [logs, setLogs] = useState('')
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [wrapLines, setWrapLines] = useState(false)
  const [error, setError] = useState('')
  const logContainerRef = useRef(null)
  const latestLogsRef = useRef('')
  const shouldStickToBottomRef = useRef(true)

  const scrollToBottom = () => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }

  const updateStickiness = () => {
    const el = logContainerRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    shouldStickToBottomRef.current = distanceFromBottom < 48
  }

  const loadLogs = async ({ forceScroll = false } = {}) => {
    try {
      const data = await apiRequest('/admin/logs')
      const nextLogs = data.logs || ''
      setError('')

      if (nextLogs !== latestLogsRef.current) {
        latestLogsRef.current = nextLogs
        setLogs(nextLogs)
        if (forceScroll || shouldStickToBottomRef.current) {
          requestAnimationFrame(() => scrollToBottom())
        }
      }
    } catch (err) {
      setError(err.message || '加载日志失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLogs({ forceScroll: true })
  }, [])

  useEffect(() => {
    if (!autoRefresh) return undefined
    const timer = window.setInterval(() => {
      loadLogs()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [autoRefresh])

  const allLines = useMemo(() => (logs ? logs.split('\n') : []), [logs])
  const visibleLines = useMemo(() => allLines.slice(-MAX_VISIBLE_LINES), [allLines])
  const hiddenLineCount = Math.max(allLines.length - visibleLines.length, 0)
  const lastUpdatedText = useMemo(() => {
    if (!allLines.length) return '暂无日志'
    const lastNonEmpty = [...allLines].reverse().find((line) => line.trim())
    return lastNonEmpty ? `最新一行：${lastNonEmpty.slice(0, 120)}` : '暂无日志'
  }, [allLines])

  return (
    <div className='space-y-6'>
      <div className='flex flex-col gap-3 md:flex-row md:items-center md:justify-between'>
        <div>
          <h1 className='text-3xl font-bold tracking-tight'>运行日志</h1>
          <p className='text-muted-foreground'>更适合阅读和排查的实时日志视图。</p>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <Badge variant='outline'>总行数 {allLines.length}</Badge>
          <Badge variant='secondary'>展示最近 {visibleLines.length} 行</Badge>
          <Button variant='outline' onClick={() => loadLogs({ forceScroll: true })} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant='destructive'>
          <AlertCircle className='h-4 w-4' />
          <AlertTitle>加载失败</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className='gap-3'>
          <div className='flex flex-col gap-3 md:flex-row md:items-center md:justify-between'>
            <div>
              <CardTitle>日志阅读器</CardTitle>
              <CardDescription>{lastUpdatedText}</CardDescription>
            </div>
            <div className='flex flex-wrap items-center gap-4 text-sm'>
              <label className='flex items-center gap-2'>
                <Switch checked={autoRefresh} onCheckedChange={setAutoRefresh} />
                <span>自动刷新</span>
              </label>
              <label className='flex items-center gap-2'>
                <Switch checked={wrapLines} onCheckedChange={setWrapLines} />
                <WrapText className='h-4 w-4' />
                <span>自动换行</span>
              </label>
            </div>
          </div>

          <div className='flex flex-wrap gap-2 text-xs'>
            <Badge className='bg-sky-500/15 text-sky-300 hover:bg-sky-500/15'>INFO</Badge>
            <Badge className='bg-amber-500/15 text-amber-300 hover:bg-amber-500/15'>WARNING</Badge>
            <Badge className='bg-red-500/15 text-red-300 hover:bg-red-500/15'>ERROR</Badge>
            <Badge className='bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/15'>成功/完成</Badge>
          </div>

          {hiddenLineCount > 0 && (
            <p className='text-xs text-muted-foreground'>
              为了流畅性，前面 {hiddenLineCount} 行已折叠，仅展示最近 {MAX_VISIBLE_LINES} 行。
            </p>
          )}
        </CardHeader>

        <CardContent>
          <div
            ref={logContainerRef}
            onScroll={updateStickiness}
            className='h-[70vh] overflow-auto rounded-md border bg-[#0b1020] p-0 font-mono text-sm will-change-scroll'
          >
            {visibleLines.length ? (
              <div className='min-w-full'>
                {visibleLines.map((line, index) => {
                  const lineNumber = hiddenLineCount + index + 1
                  return (
                    <div
                      key={`${lineNumber}-${line}`}
                      className={`grid grid-cols-[72px_1fr] gap-3 border-b border-white/5 px-3 py-1.5 transition-colors ${
                        index % 2 === 0 ? 'bg-white/[0.03]' : 'bg-slate-400/[0.12]'
                      } hover:bg-sky-400/[0.08] ${wrapLines ? 'items-start' : 'items-center'}`}
                    >
                      <span className='select-none text-right text-[11px] text-slate-500'>{lineNumber}</span>
                      <span
                        className={`${getLineTone(line)} ${
                          wrapLines ? 'whitespace-pre-wrap break-words' : 'truncate whitespace-pre'
                        }`}
                        title={line}
                      >
                        {line || ' '}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className='p-4 text-sm text-slate-400'>暂无日志</div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
