import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import UserIdentity from '@/components/UserIdentity'
import { apiRequest } from '@/types/api'

export default function SearchPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const username = params.get('username') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!username) return
    const load = async () => {
      try {
        const res = await apiRequest(`/public/search?username=${encodeURIComponent(username)}`)
        setData(res)
      } catch (err) {
        setError(err.message)
      }
    }
    load()
  }, [username])

  if (!username) {
    return <div className='p-8 text-center text-muted-foreground'>缺少用户名参数</div>
  }

  if (error) {
    return <div className='p-8 text-center text-destructive'>{error}</div>
  }

  if (!data) {
    return <div className='p-8 text-center text-muted-foreground'>加载中...</div>
  }

  const { user_info, playback_records, ban_info, active_sessions, user_groups } = data

  return (
    <div className='mx-auto max-w-6xl space-y-6 p-4 pb-8 md:p-8'>
      <div className='flex items-center justify-between'>
        <h1 className='text-2xl font-bold'>用户详情</h1>
        <Button variant='outline' onClick={() => navigate('/')}>
          返回首页
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>用户状态</CardTitle>
        </CardHeader>
        <CardContent className='flex flex-wrap items-center gap-4'>
          <UserIdentity name={username} groups={user_groups || []} />
          <div className='text-sm text-muted-foreground'>用户ID: {user_info?.Id || '-'}</div>
          <Badge variant={user_info?.Policy?.IsDisabled ? 'destructive' : 'default'}>
            {user_info?.Policy?.IsDisabled ? '已禁用' : '正常'}
          </Badge>
        </CardContent>
      </Card>

      {active_sessions?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>正在播放</CardTitle>
          </CardHeader>
          <CardContent>
            <div className='space-y-2'>
              {active_sessions.map((s) => (
                <div key={s.session_id} className='rounded-lg border p-3 text-sm'>
                  <div className='font-medium'>{s.media}</div>
                  <div className='mt-1 text-muted-foreground'>
                    <div>设备：{s.device} · {s.client}</div>
                    <div>IP：{s.ip_address}</div>
                    <div>位置：{s.location}</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {ban_info ? (
        <Card>
          <CardHeader>
            <CardTitle>封禁信息</CardTitle>
          </CardHeader>
          <CardContent className='space-y-1 text-sm'>
            <p>时间：{ban_info.timestamp}</p>
            <p>触发IP：{ban_info.trigger_ip}</p>
            <p>并发会话：{ban_info.active_sessions}</p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>最近播放记录</CardTitle>
        </CardHeader>
        <CardContent>
          <div className='space-y-2 md:hidden'>
            {playback_records?.length ? (
              playback_records.map((r) => (
                <div key={`${r.session_id}-${r.start_time}`} className='rounded-lg border p-3 text-sm'>
                  <div className='font-medium'>{r.media_name}</div>
                  <div className='mt-1 text-muted-foreground'>
                    <div>设备：{r.device_name} · {r.client_type}</div>
                    <div>IP：{r.ip_address}</div>
                    <div>位置：{r.location}</div>
                    <div>开始：{r.start_time}</div>
                    <div>结束：{r.end_time || '播放中'}</div>
                    <div>时长：{r.duration ?? '-'} 秒</div>
                  </div>
                </div>
              ))
            ) : (
              <p className='text-sm text-muted-foreground'>暂无播放记录</p>
            )}
          </div>

          <div className='hidden md:block'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>IP</TableHead>
                  <TableHead>位置</TableHead>
                  <TableHead>设备</TableHead>
                  <TableHead>客户端</TableHead>
                  <TableHead>内容</TableHead>
                  <TableHead>开始</TableHead>
                  <TableHead>结束</TableHead>
                  <TableHead>时长</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {playback_records?.map((r) => (
                  <TableRow key={`${r.session_id}-${r.start_time}`}>
                    <TableCell>{r.ip_address}</TableCell>
                    <TableCell>{r.location}</TableCell>
                    <TableCell>{r.device_name}</TableCell>
                    <TableCell>{r.client_type}</TableCell>
                    <TableCell>{r.media_name}</TableCell>
                    <TableCell>{r.start_time}</TableCell>
                    <TableCell>{r.end_time || '播放中'}</TableCell>
                    <TableCell>{r.duration ?? '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
