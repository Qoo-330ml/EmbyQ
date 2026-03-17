import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarPlus, Lock, LockOpen } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { apiRequest } from '@/types/api'
import { getUserStatus } from '@/types/format'

export default function AdminPage() {
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState({ total: 0, disabled: 0, expired: 0, never_expire: 0 })
  const [selected, setSelected] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [customDays, setCustomDays] = useState('')
  const [notice, setNotice] = useState('')
  const [editingUser, setEditingUser] = useState(null)
  const [expiryDate, setExpiryDate] = useState('')
  const [neverExpire, setNeverExpire] = useState(false)
  const navigate = useNavigate()

  const selectedIds = useMemo(
    () => Object.entries(selected).filter(([, checked]) => checked).map(([id]) => id),
    [selected]
  )

  const loadUsers = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest('/admin/users')
      setUsers(data.users || [])
      setStats(data.stats || { total: 0, disabled: 0, expired: 0, never_expire: 0 })
    } catch (err) {
      setError(err.message)
      if (String(err.message || '').includes('未登录')) {
        navigate('/login')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const toggleAll = (checked) => {
    if (!checked) {
      setSelected({})
      return
    }
    const next = {}
    users.forEach((u) => {
      next[u.id] = true
    })
    setSelected(next)
  }

  const updateUser = async (id, action) => {
    await apiRequest('/admin/users/toggle', {
      method: 'POST',
      body: JSON.stringify({ user_id: id, action }),
    })
    setNotice(`用户已${action === 'ban' ? '禁用' : '启用'}`)
    await loadUsers()
  }

  const openExpiryEditor = (user) => {
    setEditingUser(user)
    setExpiryDate(user.expiry_date || '')
    setNeverExpire(Boolean(user.never_expire))
  }

  const saveExpiry = async () => {
    if (!editingUser) return
    await apiRequest('/admin/users/expiry', {
      method: 'POST',
      body: JSON.stringify({
        user_id: editingUser.id,
        expiry_date: neverExpire ? '' : expiryDate,
        never_expire: neverExpire,
      }),
    })
    setNotice('到期设置已更新')
    setEditingUser(null)
    await loadUsers()
  }

  const clearExpiry = async () => {
    if (!editingUser) return
    await apiRequest('/admin/users/expiry', {
      method: 'POST',
      body: JSON.stringify({ user_id: editingUser.id, expiry_date: '', never_expire: false }),
    })
    setNotice('到期设置已清除')
    setEditingUser(null)
    await loadUsers()
  }

  const batchAction = async (action) => {
    if (!selectedIds.length) return

    const payload = { user_ids: selectedIds }
    if (action === 'add_days') {
      const days = Number(customDays || 0)
      if (!days) return
      payload.days = days
      await apiRequest('/admin/users/batch_expiry', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setCustomDays('')
      setNotice(`已为 ${selectedIds.length} 个用户增加到期天数`)
    } else if (action === 'clear_expiry') {
      await apiRequest('/admin/users/batch_clear_expiry', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setNotice(`已清除 ${selectedIds.length} 个用户到期时间`)
    } else if (action === 'never_expire') {
      await apiRequest('/admin/users/batch_never_expire', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setNotice(`已设置 ${selectedIds.length} 个用户永不过期`)
    } else if (action === 'ban' || action === 'unban') {
      await apiRequest('/admin/users/batch_toggle', {
        method: 'POST',
        body: JSON.stringify({ ...payload, action }),
      })
      setNotice(`已${action === 'ban' ? '禁用' : '启用'} ${selectedIds.length} 个用户`)
    }

    setSelected({})
    await loadUsers()
  }

  return (
    <div className='mx-auto max-w-7xl space-y-6 p-4 pb-8 md:p-8'>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <h1 className='text-2xl font-bold'>用户管理</h1>
        <div className='flex flex-wrap items-center gap-2'>
          <Button variant='outline' onClick={() => navigate('/admin/users')}>
            用户
          </Button>
          <Button variant='outline' onClick={() => navigate('/admin/config')}>
            配置
          </Button>
          <Button variant='outline' onClick={() => navigate('/admin/groups')}>
            用户组
          </Button>
        </div>
      </div>

      <div className='grid grid-cols-2 gap-4 md:grid-cols-4'>
        <Card>
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm'>用户总数</CardTitle>
          </CardHeader>
          <CardContent className='text-2xl font-bold'>{stats.total}</CardContent>
        </Card>
        <Card>
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm'>禁用用户</CardTitle>
          </CardHeader>
          <CardContent className='text-2xl font-bold text-destructive'>{stats.disabled}</CardContent>
        </Card>
        <Card>
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm'>已到期</CardTitle>
          </CardHeader>
          <CardContent className='text-2xl font-bold'>{stats.expired}</CardContent>
        </Card>
        <Card>
          <CardHeader className='pb-2'>
            <CardTitle className='text-sm'>永不过期</CardTitle>
          </CardHeader>
          <CardContent className='text-2xl font-bold'>{stats.never_expire}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>批量操作（已选 {selectedIds.length}）</CardTitle>
        </CardHeader>
        <CardContent className='flex flex-wrap items-center gap-2'>
          <Input
            type='number'
            min={1}
            value={customDays}
            onChange={(e) => setCustomDays(e.target.value)}
            className='w-24'
            placeholder='天数'
          />
          <Button size='sm' onClick={() => batchAction('add_days')}>
            <CalendarPlus className='mr-2 h-4 w-4' /> 增加到期天数
          </Button>
          <Button size='sm' variant='secondary' onClick={() => batchAction('clear_expiry')}>
            清除到期
          </Button>
          <Button size='sm' variant='secondary' onClick={() => batchAction('never_expire')}>
            永不过期
          </Button>
          <Button size='sm' variant='destructive' onClick={() => batchAction('ban')}>
            <Lock className='mr-2 h-4 w-4' /> 批量禁用
          </Button>
          <Button size='sm' onClick={() => batchAction('unban')}>
            <LockOpen className='mr-2 h-4 w-4' /> 批量启用
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>用户列表</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? <p className='text-sm text-muted-foreground'>加载中...</p> : null}
          {error ? <p className='text-sm text-destructive'>{error}</p> : null}
          {notice ? <p className='mb-3 text-sm text-primary'>{notice}</p> : null}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className='w-12'>
                  <Checkbox
                    checked={users.length > 0 && selectedIds.length === users.length}
                    onChange={(e) => toggleAll(e.target.checked)}
                  />
                </TableHead>
                <TableHead>用户</TableHead>
                <TableHead>到期时间</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => {
                const status = getUserStatus(u)
                return (
                  <TableRow key={u.id}>
                    <TableCell>
                      <Checkbox
                        checked={Boolean(selected[u.id])}
                        onChange={(e) => setSelected((prev) => ({ ...prev, [u.id]: e.target.checked }))}
                      />
                    </TableCell>
                    <TableCell>
                      <button
                        type='button'
                        className='text-left text-primary hover:underline'
                        onClick={() => navigate(`/search?username=${encodeURIComponent(u.name)}`)}
                      >
                        {u.name}
                      </button>
                      {u.groups?.length ? (
                        <div className='mt-1 flex flex-wrap gap-1'>
                          {u.groups.map((g) => (
                            <Badge key={`${u.id}-${g}`} variant='secondary'>
                              {g}
                            </Badge>
                          ))}
                        </div>
                      ) : null}
                    </TableCell>
                    <TableCell>{u.never_expire ? '永不过期' : u.expiry_date || '未设置'}</TableCell>
                    <TableCell>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className='space-x-2'>
                      <Button size='sm' variant='outline' onClick={() => openExpiryEditor(u)}>
                        设置到期
                      </Button>
                      {u.is_disabled ? (
                        <Button size='sm' onClick={() => updateUser(u.id, 'unban')}>
                          启用
                        </Button>
                      ) : (
                        <Button size='sm' variant='destructive' onClick={() => updateUser(u.id, 'ban')}>
                          禁用
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {editingUser ? (
        <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4'>
          <Card className='w-full max-w-md'>
            <CardHeader>
              <CardTitle>设置到期时间 · {editingUser.name}</CardTitle>
            </CardHeader>
            <CardContent className='space-y-3'>
              <label className='flex items-center gap-2 text-sm'>
                <input
                  type='checkbox'
                  checked={neverExpire}
                  onChange={(e) => setNeverExpire(e.target.checked)}
                />
                永不过期
              </label>
              <Input
                type='date'
                disabled={neverExpire}
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
              />
              <div className='flex justify-end gap-2'>
                <Button variant='secondary' onClick={clearExpiry}>
                  清除
                </Button>
                <Button variant='outline' onClick={() => setEditingUser(null)}>
                  取消
                </Button>
                <Button onClick={saveExpiry}>保存</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
