import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CalendarPlus, Link2, Lock, LockOpen, UserPlus } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import UserIdentity from '@/components/UserIdentity'
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
  const [createOpen, setCreateOpen] = useState(false)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [allGroups, setAllGroups] = useState([])
  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [templateUserId, setTemplateUserId] = useState('')
  const [createGroupIds, setCreateGroupIds] = useState([])

  const [inviteHours, setInviteHours] = useState('24')
  const [inviteCount, setInviteCount] = useState('1')
  const [inviteGroupId, setInviteGroupId] = useState('')
  const [inviteExpiryDate, setInviteExpiryDate] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [inviteList, setInviteList] = useState([])
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

  const loadGroups = async () => {
    try {
      const g = await apiRequest('/admin/groups')
      setAllGroups(g.groups || [])
    } catch (e) {
      // ignore
    }
  }

  const loadInvites = async () => {
    try {
      const data = await apiRequest('/admin/invites')
      setInviteList(data.invites || [])
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    loadUsers()
    loadGroups()
    loadInvites()
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
        <CardHeader className='flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'>
          <CardTitle>用户列表</CardTitle>
          <div className='flex flex-wrap items-center gap-2'>
            <Button variant='secondary' onClick={() => { setInviteOpen(true); setInviteUrl(''); loadInvites() }}>
              <Link2 className='mr-2 h-4 w-4' /> 邀请
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <UserPlus className='mr-2 h-4 w-4' /> 新建用户
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? <p className='text-sm text-muted-foreground'>加载中...</p> : null}
          {error ? <p className='text-sm text-destructive'>{error}</p> : null}
          {notice ? <p className='mb-3 text-sm text-primary'>{notice}</p> : null}

          <div className='space-y-3 md:hidden'>
            {users.map((u) => {
              const status = getUserStatus(u)
              return (
                <Card key={`mobile-${u.id}`}>
                  <CardContent className='space-y-2 p-4'>
                    <div className='flex items-start justify-between gap-2'>
                      <button
                        type='button'
                        className='text-left text-primary hover:underline'
                        onClick={() => navigate(`/search?username=${encodeURIComponent(u.name)}`)}
                      >
                        <UserIdentity name={u.name} groups={u.groups || []} />
                      </button>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </div>
                    <div className='text-sm text-muted-foreground'>
                      到期：{u.never_expire ? '永不过期' : u.expiry_date || '未设置'}
                    </div>
                    <div className='flex flex-wrap gap-2'>
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
                      <Button
                        size='sm'
                        variant='destructive'
                        onClick={async () => {
                          if (!window.confirm(`确定删除用户 ${u.name} 吗？`)) return
                          try {
                            await apiRequest(`/admin/users/${u.id}`, { method: 'DELETE' })
                            setNotice(`已删除用户 ${u.name}`)
                            await loadUsers()
                          } catch (e) {
                            setNotice(`删除失败：${e.message}`)
                          }
                        }}
                      >
                        删除
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>

          <div className='hidden overflow-x-auto md:block'>
            <Table className='w-full table-fixed'>
            <TableHeader>
              <TableRow>
                <TableHead className='w-12'>
                  <Checkbox
                    checked={users.length > 0 && selectedIds.length === users.length}
                    onChange={(e) => toggleAll(e.target.checked)}
                  />
                </TableHead>
                <TableHead className='w-[36%]'>用户</TableHead>
                <TableHead className='w-[18%]'>到期时间</TableHead>
                <TableHead className='w-[12%]'>状态</TableHead>
                <TableHead className='w-[24%]'>操作</TableHead>
                <TableHead className='w-[10%] text-right'>删除</TableHead>
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
                    <TableCell className='align-top'>
                      <button
                        type='button'
                        className='block w-full text-left text-primary hover:underline'
                        onClick={() => navigate(`/search?username=${encodeURIComponent(u.name)}`)}
                      >
                        <UserIdentity name={u.name} groups={u.groups || []} />
                      </button>
                    </TableCell>
                    <TableCell className='align-top whitespace-nowrap'>{u.never_expire ? '永不过期' : u.expiry_date || '未设置'}</TableCell>
                    <TableCell className='align-top'>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </TableCell>
                    <TableCell className='align-top'>
                      <div className='flex flex-wrap gap-2'>
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
                      </div>
                    </TableCell>
                    <TableCell className='align-top text-right'>
                      <Button
                        size='sm'
                        variant='destructive'
                        onClick={async () => {
                          if (!window.confirm(`确定删除用户 ${u.name} 吗？`)) return
                          try {
                            await apiRequest(`/admin/users/${u.id}`, { method: 'DELETE' })
                            setNotice(`已删除用户 ${u.name}`)
                            await loadUsers()
                          } catch (e) {
                            setNotice(`删除失败：${e.message}`)
                          }
                        }}
                      >
                        删除
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {createOpen ? (
        <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4'>
          <Card className='w-full max-w-lg'>
            <CardHeader>
              <CardTitle>新建用户</CardTitle>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='grid gap-3 md:grid-cols-2'>
                <div className='space-y-2'>
                  <label className='text-sm text-muted-foreground'>用户名</label>
                  <Input value={createUsername} onChange={(e) => setCreateUsername(e.target.value)} />
                </div>
                <div className='space-y-2'>
                  <label className='text-sm text-muted-foreground'>密码（可不填，默认=用户名）</label>
                  <Input type='password' value={createPassword} onChange={(e) => setCreatePassword(e.target.value)} />
                </div>
              </div>

              <div className='space-y-2'>
                <label className='text-sm text-muted-foreground'>用户模板（复制该用户的权限/功能）</label>
                <select
                  className='h-10 w-full rounded-md border border-input bg-background px-3 text-sm'
                  value={templateUserId}
                  onChange={(e) => setTemplateUserId(e.target.value)}
                >
                  <option value=''>不使用模板</option>
                  {users.map((u) => (
                    <option key={`tpl-${u.id}`} value={u.id}>
                      {u.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className='space-y-2'>
                <label className='text-sm text-muted-foreground'>用户组（可多选）</label>
                <div className='grid gap-2 md:grid-cols-2'>
                  {allGroups.map((g) => (
                    <label key={`cg-${g.id}`} className='flex items-center gap-2 text-sm'>
                      <input
                        type='checkbox'
                        checked={createGroupIds.includes(g.id)}
                        onChange={(e) => {
                          const checked = e.target.checked
                          setCreateGroupIds((prev) =>
                            checked ? [...prev, g.id] : prev.filter((x) => x !== g.id)
                          )
                        }}
                      />
                      {g.name}
                    </label>
                  ))}
                </div>
              </div>

              <div className='flex justify-end gap-2'>
                <Button
                  variant='outline'
                  onClick={() => {
                    setCreateOpen(false)
                    setCreateUsername('')
                    setCreatePassword('')
                    setTemplateUserId('')
                    setCreateGroupIds([])
                  }}
                >
                  取消
                </Button>
                <Button
                  onClick={async () => {
                    try {
                      await apiRequest('/admin/users/create', {
                        method: 'POST',
                        body: JSON.stringify({
                          username: createUsername,
                          password: createPassword,
                          template_user_id: templateUserId,
                          group_ids: createGroupIds,
                        }),
                      })
                      setNotice('用户创建成功')
                      setCreateOpen(false)
                      setCreateUsername('')
                      setCreatePassword('')
                      setTemplateUserId('')
                      setCreateGroupIds([])
                      await loadUsers()
                      await loadGroups()
                    } catch (e) {
                      setNotice(`创建失败：${e.message}`)
                    }
                  }}
                >
                  创建
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {inviteOpen ? (
        <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4'>
          <Card className='w-full max-w-lg'>
            <CardHeader>
              <CardTitle>生成邀请链接</CardTitle>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='grid gap-3 md:grid-cols-2'>
                <div className='space-y-2'>
                  <label className='text-sm text-muted-foreground'>有效时间（小时）</label>
                  <Input type='number' min={1} value={inviteHours} onChange={(e) => setInviteHours(e.target.value)} />
                </div>
                <div className='space-y-2'>
                  <label className='text-sm text-muted-foreground'>邀请人数</label>
                  <Input type='number' min={1} value={inviteCount} onChange={(e) => setInviteCount(e.target.value)} />
                </div>
              </div>

              <div className='space-y-2'>
                <label className='text-sm text-muted-foreground'>属于用户组</label>
                <select
                  className='h-10 w-full rounded-md border border-input bg-background px-3 text-sm'
                  value={inviteGroupId}
                  onChange={(e) => setInviteGroupId(e.target.value)}
                >
                  <option value=''>不指定</option>
                  {allGroups.map((g) => (
                    <option key={`ig-${g.id}`} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className='space-y-2'>
                <label className='text-sm text-muted-foreground'>注册账号到期时间（可选）</label>
                <Input type='date' value={inviteExpiryDate} onChange={(e) => setInviteExpiryDate(e.target.value)} />
              </div>

              {inviteUrl ? (
                <div className='space-y-2 rounded border p-3'>
                  <div className='text-sm text-muted-foreground'>新生成链接</div>
                  <div className='break-all font-mono text-sm'>{inviteUrl}</div>
                </div>
              ) : null}

              <div className='space-y-2 rounded border p-3'>
                <div className='text-sm font-medium'>已发邀请链接</div>
                <div className='max-h-56 space-y-2 overflow-auto'>
                  {inviteList.length ? (
                    inviteList.map((inv) => {
                      const exhausted = Number(inv.used_count || 0) >= Number(inv.max_uses || 0)
                      const invalid = exhausted || !inv.is_active
                      return (
                        <div key={inv.code} className='rounded border p-2'>
                          <div className='flex items-start justify-between gap-2'>
                            <div className={`break-all font-mono text-xs ${invalid ? 'line-through text-muted-foreground' : ''}`}>
                              {inv.invite_url}
                            </div>
                            <div className='flex items-center gap-2'>
                              <Button
                                size='sm'
                                variant='outline'
                                onClick={async () => {
                                  try {
                                    if (navigator.clipboard?.writeText) {
                                      await navigator.clipboard.writeText(inv.invite_url)
                                    } else {
                                      const input = document.createElement('input')
                                      input.value = inv.invite_url
                                      document.body.appendChild(input)
                                      input.select()
                                      document.execCommand('copy')
                                      document.body.removeChild(input)
                                    }
                                    setNotice('邀请链接已复制')
                                  } catch {
                                    setNotice('复制失败，请手动复制')
                                  }
                                }}
                              >
                                复制
                              </Button>
                              <Button
                                size='sm'
                                variant='destructive'
                                onClick={async () => {
                                  try {
                                    await apiRequest(`/admin/invites/${inv.code}`, { method: 'DELETE' })
                                    await loadInvites()
                                  } catch (e) {
                                    setNotice(`删除邀请失败：${e.message}`)
                                  }
                                }}
                              >
                                删除
                              </Button>
                            </div>
                          </div>
                          <div className='mt-1 text-xs text-muted-foreground'>
                            使用进度：{inv.used_count}/{inv.max_uses}
                          </div>
                        </div>
                      )
                    })
                  ) : (
                    <div className='text-xs text-muted-foreground'>暂无邀请链接</div>
                  )}
                </div>
              </div>

              <div className='flex justify-end gap-2'>
                <Button variant='outline' onClick={() => setInviteOpen(false)}>
                  关闭
                </Button>
                <Button
                  onClick={async () => {
                    try {
                      const data = await apiRequest('/admin/invites', {
                        method: 'POST',
                        body: JSON.stringify({
                          valid_hours: Number(inviteHours || 24),
                          max_uses: Number(inviteCount || 1),
                          group_id: inviteGroupId,
                          account_expiry_date: inviteExpiryDate,
                        }),
                      })
                      setInviteUrl(data.invite_url)
                      await loadInvites()
                    } catch (e) {
                      setNotice(`生成失败：${e.message}`)
                    }
                  }}
                >
                  生成
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

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
