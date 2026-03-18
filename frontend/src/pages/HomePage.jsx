import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import UserIdentity from '@/components/UserIdentity'
import { apiRequest } from '@/types/api'

export default function HomePage() {
  const [username, setUsername] = useState('')
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)
  const fingerprintRef = useRef('')
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    let timer = null

    const load = async (showLoading = false) => {
      if (!active) return
      if (showLoading) setLoading(true)
      try {
        const data = await apiRequest('/public/active-sessions')
        const next = (data.sessions || []).slice().sort((a, b) => String(a.session_id).localeCompare(String(b.session_id)))
        const fingerprint = JSON.stringify(
          next.map((s) => ({
            session_id: s.session_id,
            user_id: s.user_id,
            username: s.username,
            groups: s.groups,
            ip_address: s.ip_address,
            location: s.location,
            device: s.device,
            client: s.client,
            media: s.media,
          }))
        )
        if (active && fingerprint !== fingerprintRef.current) {
          setSessions(next)
          fingerprintRef.current = fingerprint
        }
      } catch (e) {
        // 网络/Emby 抖动时保持现有 UI，避免闪烁
        if (active && showLoading) {
          setSessions([])
          fingerprintRef.current = ''
        }
      } finally {
        if (active && showLoading) setLoading(false)
      }
    }

    load(true)
    timer = setInterval(() => load(false), 5000)

    return () => {
      active = false
      if (timer) clearInterval(timer)
    }
  }, [])

  const onSearch = (e) => {
    e.preventDefault()
    if (!username) return
    navigate(`/search?username=${encodeURIComponent(username)}`)
  }

  return (
    <div className='mx-auto max-w-6xl space-y-6 p-4 pb-8 md:p-8'>
      <div className='flex items-center justify-between'>
        <h1 className='text-2xl font-bold'>Emby 播放记录查询</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>按用户名查询</CardTitle>
        </CardHeader>
        <CardContent>
          <form className='flex gap-2' onSubmit={onSearch}>
            <Input
              placeholder='输入 Emby 用户名'
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <Button type='submit'>
              <Search className='mr-2 h-4 w-4' /> 查询
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>当前正在播放（{sessions.length}）</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className='text-sm text-muted-foreground'>加载中...</p>
          ) : (
            <>
              <div className='space-y-2 md:hidden'>
                {sessions.length ? (
                  sessions.map((s) => (
                    <div key={s.session_id} className='rounded-lg border p-3 text-sm'>
                      <UserIdentity name={s.username} groups={s.groups || []} />
                      <div className='mt-1 text-muted-foreground'>
                        <div>内容：{s.media}</div>
                        <div>设备：{s.device} · {s.client}</div>
                        <div>IP：{s.ip_address}</div>
                        <div>位置：{s.location}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className='text-sm text-muted-foreground'>暂无正在播放</p>
                )}
              </div>

              <div className='hidden md:block'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>用户</TableHead>
                      <TableHead>IP</TableHead>
                      <TableHead>位置</TableHead>
                      <TableHead>设备</TableHead>
                      <TableHead>客户端</TableHead>
                      <TableHead>内容</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sessions.map((s) => (
                      <TableRow key={s.session_id}>
                        <TableCell>
                          <UserIdentity name={s.username} groups={s.groups || []} />
                        </TableCell>
                        <TableCell>{s.ip_address}</TableCell>
                        <TableCell>{s.location}</TableCell>
                        <TableCell>{s.device}</TableCell>
                        <TableCell>{s.client}</TableCell>
                        <TableCell>{s.media}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
