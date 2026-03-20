import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest } from '@/types/api'

export default function ConfigPage() {
  const [config, setConfig] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiRequest('/admin/config')
        setConfig(data.config)
      } catch (err) {
        setError(err.message)
      }
    }
    load()
  }, [])

  const update = (path, value) => {
    setConfig((prev) => {
      const next = structuredClone(prev)
      let cursor = next
      for (let i = 0; i < path.length - 1; i += 1) {
        cursor = cursor[path[i]]
      }
      cursor[path[path.length - 1]] = value
      return next
    })
  }

  const updateWhitelistItem = (index, value) => {
    const current = [...(config?.security?.whitelist || [])]
    current[index] = value
    update(['security', 'whitelist'], current)
  }

  const addWhitelistItem = () => {
    const current = [...(config?.security?.whitelist || [])]
    current.push('')
    update(['security', 'whitelist'], current)
  }

  const removeWhitelistItem = (index) => {
    const current = [...(config?.security?.whitelist || [])]
    current.splice(index, 1)
    update(['security', 'whitelist'], current)
  }

  const onSave = async () => {
    setSaving(true)
    setNotice('')
    setError('')

    const nextConfig = structuredClone(config)
    nextConfig.security.whitelist = (nextConfig.security.whitelist || [])
      .map((v) => String(v || '').trim())
      .filter(Boolean)

    try {
      await apiRequest('/admin/config', {
        method: 'PUT',
        body: JSON.stringify({ config: nextConfig }),
      })
      setNotice('配置已保存')
      setConfig(nextConfig)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!config) {
    return <div className='p-8 text-center text-muted-foreground'>加载配置中...</div>
  }

  return (
    <div className='mx-auto max-w-7xl space-y-6 p-4 pb-8 md:p-8'>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <h1 className='text-2xl font-bold'>配置管理</h1>
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

      <Card>
        <CardHeader>
          <CardTitle>Emby 配置</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>服务器地址（内网）</label>
            <Input
              value={config.emby.server_url || ''}
              onChange={(e) => update(['emby', 'server_url'], e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>服务器外网地址</label>
            <Input
              value={config.emby.external_url || ''}
              onChange={(e) => update(['emby', 'external_url'], e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>IPLimit 外网地址</label>
            <Input
              value={config.service?.external_url || ''}
              onChange={(e) => update(['service', 'external_url'], e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>API Key</label>
            <Input
              value={config.emby.api_key || ''}
              onChange={(e) => update(['emby', 'api_key'], e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>检查间隔(秒)</label>
            <Input
              type='number'
              value={config.monitor?.check_interval || 10}
              onChange={(e) => update(['monitor', 'check_interval'], Number(e.target.value || 10))}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>安全与通知</CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-3'>
            <div className='space-y-2'>
              <label className='text-sm text-muted-foreground'>告警阈值</label>
              <Input
                type='number'
                value={config.notifications.alert_threshold || 2}
                onChange={(e) => update(['notifications', 'alert_threshold'], Number(e.target.value || 2))}
              />
            </div>
            <label className='flex items-center gap-2 pt-8 text-sm'>
              <input
                type='checkbox'
                checked={Boolean(config.notifications.enable_alerts)}
                onChange={(e) => update(['notifications', 'enable_alerts'], e.target.checked)}
              />
              启用异常告警
            </label>
            <label className='flex items-center gap-2 pt-8 text-sm'>
              <input
                type='checkbox'
                checked={Boolean(config.security.auto_disable)}
                onChange={(e) => update(['security', 'auto_disable'], e.target.checked)}
              />
              自动禁用异常用户
            </label>
          </div>

          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <label className='text-sm text-muted-foreground'>白名单用户</label>
              <Button size='sm' variant='secondary' onClick={addWhitelistItem}>
                添加
              </Button>
            </div>
            <div className='space-y-2'>
              {(config.security.whitelist || []).map((name, idx) => (
                <div key={`wl-${idx}`} className='flex gap-2'>
                  <Input value={name} onChange={(e) => updateWhitelistItem(idx, e.target.value)} />
                  <Button size='sm' variant='destructive' onClick={() => removeWhitelistItem(idx)}>
                    删除
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Webhook 配置</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4 md:grid-cols-2'>
          <label className='flex items-center gap-2 text-sm md:col-span-2'>
            <input
              type='checkbox'
              checked={Boolean(config.webhook?.enabled)}
              onChange={(e) => update(['webhook', 'enabled'], e.target.checked)}
            />
            启用 Webhook
          </label>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>Webhook URL</label>
            <Input
              value={config.webhook?.url || ''}
              onChange={(e) => update(['webhook', 'url'], e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>超时(秒)</label>
            <Input
              type='number'
              value={config.webhook?.timeout || 10}
              onChange={(e) => update(['webhook', 'timeout'], Number(e.target.value || 10))}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>重试次数</label>
            <Input
              type='number'
              value={config.webhook?.retry_attempts || 3}
              onChange={(e) => update(['webhook', 'retry_attempts'], Number(e.target.value || 3))}
            />
          </div>
          <div className='space-y-2 md:col-span-2'>
            <label className='text-sm text-muted-foreground'>Webhook Body (YAML)</label>
            <Textarea
              className='min-h-48 font-mono'
              value={
                typeof config.webhook?.body === 'string'
                  ? config.webhook.body
                  : config.webhook?.body
                    ? JSON.stringify(config.webhook.body, null, 2)
                    : ''
              }
              onChange={(e) => update(['webhook', 'body'], e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>管理后台账号</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>管理员用户名</label>
            <Input
              value={config.web?.admin_username || 'admin'}
              onChange={(e) => update(['web', 'admin_username'], e.target.value)}
            />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>管理员密码</label>
            <Input
              type='password'
              value={config.web?.admin_password || ''}
              onChange={(e) => update(['web', 'admin_password'], e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {error ? <p className='text-sm text-destructive'>{error}</p> : null}
      {notice ? <p className='text-sm text-primary'>{notice}</p> : null}
      <Button onClick={onSave} disabled={saving}>
        {saving ? '保存中...' : '保存配置'}
      </Button>
    </div>
  )
}
