import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { apiRequest } from '@/types/api'

const STATUS_ACTIONS = [
  { value: 'pending', label: '待处理' },
  { value: 'approved', label: '已采纳' },
  { value: 'rejected', label: '已拒绝' },
]

function getStatusMeta(status) {
  switch (status) {
    case 'approved':
      return { label: '已采纳', variant: 'default' }
    case 'rejected':
      return { label: '已拒绝', variant: 'destructive' }
    default:
      return { label: '待处理', variant: 'outline' }
  }
}

export default function AdminWishesPage() {
  const navigate = useNavigate()
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [actingId, setActingId] = useState('')

  const loadRequests = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest('/admin/wishes')
      setRequests(data.requests || [])
    } catch (err) {
      setError(err.message)
      if (String(err.message || '').includes('未登录')) {
        navigate('/login')
      }
    } finally {
      setLoading(false)
    }
  }, [navigate])

  useEffect(() => {
    loadRequests()
  }, [loadRequests])

  const updateStatus = async (requestId, nextStatus) => {
    setActingId(`status-${requestId}-${nextStatus}`)
    setError('')
    setNotice('')
    try {
      await apiRequest(`/admin/wishes/${requestId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setNotice('求片状态已更新')
      await loadRequests()
    } catch (err) {
      setError(err.message)
    } finally {
      setActingId('')
    }
  }

  return (
    <div className='mx-auto max-w-7xl space-y-6 p-4 pb-8 md:p-8'>
      <div>
        <h1 className='text-2xl font-bold'>求片管理</h1>
        <p className='mt-1 text-sm text-muted-foreground'>查看游客提交的想看内容，并将状态调整为待处理、已采纳或已拒绝。</p>
      </div>

      {error ? <p className='text-sm text-destructive'>{error}</p> : null}
      {notice ? <p className='text-sm text-primary'>{notice}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>求片列表</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? <p className='text-sm text-muted-foreground'>加载中...</p> : null}
          {!loading && !requests.length ? <p className='text-sm text-muted-foreground'>当前没有求片记录</p> : null}

          {!loading ? (
            <>
              <div className='space-y-3 md:hidden'>
                {requests.map((item) => {
                  const statusMeta = getStatusMeta(item.status)
                  return (
                    <Card key={item.id}>
                      <CardContent className='space-y-3 p-4'>
                        <div className='flex gap-3'>
                          <div className='w-20 shrink-0 overflow-hidden rounded-md bg-muted aspect-[3/4]'>
                            {item.poster_url ? <img src={item.poster_url} alt={item.title} className='h-full w-full object-cover' /> : null}
                          </div>
                          <div className='min-w-0 flex-1 space-y-2'>
                            <div className='flex items-start justify-between gap-2'>
                              <div>
                                <div className='font-medium'>{item.title}</div>
                                <div className='text-xs text-muted-foreground'>
                                  {item.media_type === 'movie' ? '电影' : '剧集'} · {item.year || '未知年份'}
                                </div>
                              </div>
                              <Badge variant={statusMeta.variant}>{statusMeta.label}</Badge>
                            </div>
                            <div className='text-xs text-muted-foreground'>提交时间 {item.created_at}</div>
                            <p className='line-clamp-3 text-sm text-muted-foreground'>{item.overview || '暂无简介'}</p>
                          </div>
                        </div>
                        <div className='flex flex-wrap gap-2'>
                          {STATUS_ACTIONS.map((option) => (
                            <Button
                              key={`${item.id}-${option.value}`}
                              size='sm'
                              variant={item.status === option.value ? 'default' : 'outline'}
                              disabled={actingId === `status-${item.id}-${option.value}`}
                              onClick={() => updateStatus(item.id, option.value)}
                            >
                              {option.label}
                            </Button>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>

              <div className='hidden md:block'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>海报</TableHead>
                      <TableHead>标题</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>提交时间</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {requests.map((item) => {
                      const statusMeta = getStatusMeta(item.status)
                      return (
                        <TableRow key={item.id}>
                          <TableCell>
                            <div className='w-16 overflow-hidden rounded-md bg-muted aspect-[3/4]'>
                              {item.poster_url ? <img src={item.poster_url} alt={item.title} className='h-full w-full object-cover' /> : null}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className='font-medium'>{item.title}</div>
                            <div className='line-clamp-2 max-w-xl text-xs text-muted-foreground'>{item.overview || '暂无简介'}</div>
                          </TableCell>
                          <TableCell>{item.media_type === 'movie' ? '电影' : '剧集'}</TableCell>
                          <TableCell>
                            <Badge variant={statusMeta.variant}>{statusMeta.label}</Badge>
                          </TableCell>
                          <TableCell>{item.created_at}</TableCell>
                          <TableCell>
                            <div className='flex flex-wrap gap-2'>
                              {STATUS_ACTIONS.map((option) => (
                                <Button
                                  key={`${item.id}-${option.value}`}
                                  size='sm'
                                  variant={item.status === option.value ? 'default' : 'outline'}
                                  disabled={actingId === `status-${item.id}-${option.value}`}
                                  onClick={() => updateStatus(item.id, option.value)}
                                >
                                  {option.label}
                                </Button>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
