import { useEffect, useMemo, useState } from 'react'

import UserIdentity from '@/components/UserIdentity'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { apiRequest } from '@/types/api'

export default function GroupsPage() {
  const [groups, setGroups] = useState([])
  const [users, setUsers] = useState([])
  const [newGroupName, setNewGroupName] = useState('')
  const [activeGroupId, setActiveGroupId] = useState('')
  const [memberId, setMemberId] = useState('')
  const [selectedMembers, setSelectedMembers] = useState({})
  const [filterText, setFilterText] = useState('')
  const [days, setDays] = useState('30')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const activeGroup = useMemo(() => groups.find((group) => group.id === activeGroupId), [groups, activeGroupId])
  const activeMemberIds = activeGroup?.members || []

  useEffect(() => {
    let cancelled = false

    const loadAll = async () => {
      try {
        const [groupData, userData] = await Promise.all([apiRequest('/admin/groups'), apiRequest('/admin/users')])
        if (cancelled) return
        setGroups(groupData.groups || [])
        setUsers(userData.users || [])
        if (!activeGroupId && groupData.groups?.[0]?.id) {
          setActiveGroupId(groupData.groups[0].id)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message)
        }
      }
    }

    loadAll()

    return () => {
      cancelled = true
    }
  }, [activeGroupId])

  const loadAll = async () => {
    try {
      const [groupData, userData] = await Promise.all([apiRequest('/admin/groups'), apiRequest('/admin/users')])
      setGroups(groupData.groups || [])
      setUsers(userData.users || [])
      if (!activeGroupId && groupData.groups?.[0]?.id) {
        setActiveGroupId(groupData.groups[0].id)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const createGroup = async () => {
    if (!newGroupName.trim()) return
    await apiRequest('/admin/groups', {
      method: 'POST',
      body: JSON.stringify({ name: newGroupName.trim() }),
    })
    setNotice('用户组创建成功')
    setNewGroupName('')
    await loadAll()
  }

  const removeGroup = async (groupId) => {
    await apiRequest(`/admin/groups/${groupId}`, { method: 'DELETE' })
    setNotice('用户组已删除')
    if (activeGroupId === groupId) setActiveGroupId('')
    await loadAll()
  }

  const addMember = async () => {
    if (!activeGroupId || !memberId) return
    await apiRequest(`/admin/groups/${activeGroupId}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_id: memberId }),
    })
    setNotice('成员添加成功')
    setMemberId('')
    await loadAll()
  }

  const addSelectedMembers = async () => {
    if (!activeGroupId) return
    const ids = Object.entries(selectedMembers)
      .filter(([, checked]) => checked)
      .map(([id]) => id)
    if (!ids.length) return

    for (const id of ids) {
      await apiRequest(`/admin/groups/${activeGroupId}/members`, {
        method: 'POST',
        body: JSON.stringify({ user_id: id }),
      })
    }
    setNotice(`已批量添加 ${ids.length} 个成员`)
    setSelectedMembers({})
    await loadAll()
  }

  const removeMember = async (userId) => {
    if (!activeGroupId) return
    await apiRequest(`/admin/groups/${activeGroupId}/members/${userId}`, { method: 'DELETE' })
    setNotice('成员已移除')
    await loadAll()
  }

  const doGroupBatch = async (kind) => {
    if (!activeMemberIds.length) return

    if (kind === 'add_days') {
      await apiRequest('/admin/users/batch_expiry', {
        method: 'POST',
        body: JSON.stringify({ user_ids: activeMemberIds, days: Number(days || 30) }),
      })
      setNotice(`已为组成员增加 ${days} 天到期时间`)
    } else if (kind === 'clear_expiry') {
      await apiRequest('/admin/users/batch_clear_expiry', {
        method: 'POST',
        body: JSON.stringify({ user_ids: activeMemberIds }),
      })
      setNotice('已清除组成员到期时间')
    } else if (kind === 'never_expire') {
      await apiRequest('/admin/users/batch_never_expire', {
        method: 'POST',
        body: JSON.stringify({ user_ids: activeMemberIds }),
      })
      setNotice('已设置组成员永不过期')
    } else if (kind === 'ban' || kind === 'unban') {
      await apiRequest('/admin/users/batch_toggle', {
        method: 'POST',
        body: JSON.stringify({ user_ids: activeMemberIds, action: kind }),
      })
      setNotice(`已${kind === 'ban' ? '禁用' : '启用'}组成员`)
    }

    await loadAll()
  }

  return (
    <div className='mx-auto max-w-7xl space-y-6 p-4 pb-8 md:p-8'>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <h1 className='text-2xl font-bold'>用户组管理</h1>
      </div>

      {error ? <p className='text-sm text-destructive'>{error}</p> : null}
      {notice ? <p className='text-sm text-primary'>{notice}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>创建用户组</CardTitle>
        </CardHeader>
        <CardContent className='flex gap-2'>
          <Input placeholder='例如 家庭组' value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)} />
          <Button onClick={createGroup}>创建</Button>
        </CardContent>
      </Card>

      <div className='grid gap-4 md:grid-cols-2'>
        <Card>
          <CardHeader>
            <CardTitle>用户组列表</CardTitle>
          </CardHeader>
          <CardContent className='space-y-2'>
            {groups.map((group) => (
              <div
                key={group.id}
                role='button'
                tabIndex={0}
                onClick={() => setActiveGroupId(group.id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') setActiveGroupId(group.id)
                }}
                className={`flex items-center justify-between rounded border p-3 transition-colors hover:bg-accent/40 ${
                  activeGroupId === group.id ? 'border-primary' : ''
                }`}
              >
                <div className='text-left'>
                  <div className='font-medium'>{group.name}</div>
                  <div className='text-xs text-muted-foreground'>{group.members?.length || 0} 个成员</div>
                </div>
                <Button
                  size='sm'
                  variant='destructive'
                  onClick={(event) => {
                    event.stopPropagation()
                    removeGroup(group.id)
                  }}
                >
                  删除
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>成员与组批量操作</CardTitle>
          </CardHeader>
          <CardContent className='space-y-3'>
            {!activeGroup ? (
              <p className='text-sm text-muted-foreground'>请选择一个用户组</p>
            ) : (
              <>
                <div className='space-y-2 rounded border p-3'>
                  <div className='flex gap-2'>
                    <select
                      className='h-10 w-full rounded-md border border-input bg-background px-3 text-sm'
                      value={memberId}
                      onChange={(event) => setMemberId(event.target.value)}
                    >
                      <option value=''>选择要添加的用户</option>
                      {users
                        .filter((user) => !(activeGroup.members || []).includes(user.id))
                        .map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.name}
                            {user.groups?.length ? ` (${user.groups.join(' / ')})` : ''}
                          </option>
                        ))}
                    </select>
                    <Button onClick={addMember}>添加</Button>
                  </div>

                  <div className='flex items-center gap-2'>
                    <Input placeholder='批量筛选用户' value={filterText} onChange={(event) => setFilterText(event.target.value)} />
                    <Button variant='secondary' onClick={addSelectedMembers}>
                      批量添加
                    </Button>
                  </div>

                  <div className='max-h-48 space-y-2 overflow-auto rounded border p-2'>
                    {users
                      .filter((user) => !(activeGroup.members || []).includes(user.id))
                      .filter((user) => user.name.toLowerCase().includes(filterText.toLowerCase()))
                      .map((user) => (
                        <label key={user.id} className='flex items-center gap-2 text-sm'>
                          <input
                            type='checkbox'
                            checked={Boolean(selectedMembers[user.id])}
                            onChange={(event) =>
                              setSelectedMembers((prev) => ({ ...prev, [user.id]: event.target.checked }))
                            }
                          />
                          <UserIdentity name={user.name} groups={user.groups || []} />
                        </label>
                      ))}
                    {!users
                      .filter((user) => !(activeGroup.members || []).includes(user.id))
                      .filter((user) => user.name.toLowerCase().includes(filterText.toLowerCase())).length ? (
                      <p className='text-xs text-muted-foreground'>没有可添加的用户</p>
                    ) : null}
                  </div>
                </div>

                <div className='grid gap-3 rounded border p-3'>
                  <div className='font-medium'>组内批量操作</div>
                  <div className='flex flex-wrap items-center gap-2'>
                    <Input type='number' className='w-24' value={days} onChange={(event) => setDays(event.target.value)} />
                    <Button size='sm' onClick={() => doGroupBatch('add_days')}>
                      增加到期天数
                    </Button>
                    <Button size='sm' variant='secondary' onClick={() => doGroupBatch('clear_expiry')}>
                      清除到期
                    </Button>
                    <Button size='sm' variant='secondary' onClick={() => doGroupBatch('never_expire')}>
                      永不过期
                    </Button>
                    <Button size='sm' variant='destructive' onClick={() => doGroupBatch('ban')}>
                      禁用组成员
                    </Button>
                    <Button size='sm' onClick={() => doGroupBatch('unban')}>
                      启用组成员
                    </Button>
                  </div>
                </div>

                <div className='rounded border p-3'>
                  <div className='mb-2 font-medium'>当前成员</div>
                  <div className='space-y-2'>
                    {(activeGroup.members || []).length ? (
                      activeGroup.members.map((userId) => {
                        const user = users.find((currentUser) => currentUser.id === userId)
                        if (!user) return null
                        return (
                          <div key={userId} className='flex items-center justify-between gap-2 rounded border p-2'>
                            <UserIdentity name={user.name} groups={user.groups || []} />
                            <Button size='sm' variant='destructive' onClick={() => removeMember(userId)}>
                              移除
                            </Button>
                          </div>
                        )
                      })
                    ) : (
                      <p className='text-sm text-muted-foreground'>当前组暂无成员</p>
                    )}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
