import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { apiRequest } from '@/types/api'

export default function ConfigPage() {
  const [config, setConfig] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [testingWebhook, setTestingWebhook] = useState(false)
  const [webhookNotice, setWebhookNotice] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncNotice, setSyncNotice] = useState('')

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

  const onSyncShadow = async () => {
    setSyncing(true)
    setSyncNotice('')
    try {
      const result = await apiRequest('/admin/shadow/sync', { method: 'POST' })
      const { movies, series } = result.result || {}
      setSyncNotice(
        `同步完成：电影 ${movies?.synced || 0} 部（新增）, 剧集 ${series?.synced || 0} 部（新增）`
      )
    } catch (err) {
      setSyncNotice(`同步失败：${err.message}`)
    } finally {
      setSyncing(false)
    }
  }

  const onTestWebhook = async () => {
    setTestingWebhook(true)
    setWebhookNotice('')
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
      setConfig(nextConfig)
      await apiRequest('/admin/webhook/test', { method: 'POST' })
      setWebhookNotice('测试通知已发送')
    } catch (err) {
      setWebhookNotice(`测试失败：${err.message}`)
    } finally {
      setTestingWebhook(false)
    }
  }

  if (!config) {
    return <div className='p-8 text-center text-muted-foreground'>加载配置中...</div>
  }

  return (
    <div className='mx-auto max-w-7xl space-y-6 p-4 pb-8 md:p-8'>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        <h1 className='text-2xl font-bold'>配置管理</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Emby 配置</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>Emby服务器地址（内网）</label>
            <Input value={config.emby.server_url || ''} onChange={(e) => update(['emby', 'server_url'], e.target.value)} />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>Emby服务器外网地址</label>
            <Input value={config.emby.external_url || ''} onChange={(e) => update(['emby', 'external_url'], e.target.value)} />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>EmbyQ外网地址（用于发送邀请链接）</label>
            <Input value={config.service?.external_url || ''} onChange={(e) => update(['service', 'external_url'], e.target.value)} />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>Emby API Key</label>
            <Input value={config.emby.api_key || ''} onChange={(e) => update(['emby', 'api_key'], e.target.value)} />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>检查间隔(秒)</label>
            <Input
              type='number'
              value={config.monitor?.check_interval || 10}
              onChange={(e) => update(['monitor', 'check_interval'], Number(e.target.value || 10))}
            />
          </div>
          <div className='flex items-end gap-2'>
            <Button onClick={onSyncShadow} disabled={syncing}>
              {syncing ? '同步中...' : '同步影子库'}
            </Button>
            {syncNotice && <span className='text-sm text-muted-foreground'>{syncNotice}</span>}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>TMDB搜索</CardTitle>
        </CardHeader>
        <CardContent className='grid gap-4 md:grid-cols-2'>
          <label className='flex items-center gap-2 text-sm'>
            <Checkbox
              checked={Boolean(config.guest_request?.enabled)}
              onChange={(e) => update(['guest_request', 'enabled'], e.target.checked)}
            />
            启用TMDB搜索
          </label>
          <label className='flex items-center gap-2 text-sm'>
            <Checkbox
              checked={Boolean(config.tmdb?.include_adult)}
              onChange={(e) => update(['tmdb', 'include_adult'], e.target.checked)}
            />
            搜索时包含成人内容
          </label>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>TMDB API Key</label>
            <Input value={config.tmdb?.api_key || ''} onChange={(e) => update(['tmdb', 'api_key'], e.target.value)} />
          </div>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>TMDB 语言</label>
            <Input value={config.tmdb?.language || 'zh-CN'} onChange={(e) => update(['tmdb', 'language'], e.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>IP 归属地解析</CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          <label className='flex items-start gap-2 text-sm'>
            <Checkbox
              checked={Boolean(config.ip_location?.use_geocache)}
              onChange={(e) => update(['ip_location', 'use_geocache'], e.target.checked)}
              className='mt-1'
            />
            <div className='flex-1'>
              <div className='font-medium'>启用自建库解析</div>
              <div className='mt-1 text-xs text-muted-foreground'>
                默认使用IP138解析归属地，启用后会切换到优先自建归属地库，并清空已有解析缓存。
              </div>
            </div>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>系统代理</CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          <label className='flex items-center gap-2 text-sm'>
            <Checkbox
              checked={Boolean(config.proxy?.enabled)}
              onChange={(e) => update(['proxy', 'enabled'], e.target.checked)}
            />
            启用代理
          </label>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>代理地址</label>
            <Input
              placeholder='http://127.0.0.1:7890 或 socks5://127.0.0.1:7890'
              value={config.proxy?.url || ''}
              onChange={(e) => update(['proxy', 'url'], e.target.value)}
            />
          </div>
          <p className='text-xs text-muted-foreground'>
            设置后 TMDB 搜索请求将通过指定代理转发。支持 http、https、socks5 协议。
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>自动封禁</CardTitle>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2'>
            <div className='space-y-2'>
              <label className='text-sm text-muted-foreground'>告警阈值</label>
              <Input
                type='number'
                value={config.notifications.alert_threshold || 2}
                onChange={(e) => update(['notifications', 'alert_threshold'], Number(e.target.value || 2))}
              />
            </div>
            <label className='flex items-center gap-2 pt-8 text-sm'>
              <Checkbox
                checked={Boolean(config.notifications.enable_alerts)}
                onChange={(e) => update(['notifications', 'enable_alerts'], e.target.checked)}
              />
              启用异常封禁
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
            <Checkbox
              checked={Boolean(config.webhook?.enabled)}
              onChange={(e) => update(['webhook', 'enabled'], e.target.checked)}
            />
            启用 Webhook
          </label>
          <div className='space-y-2'>
            <label className='text-sm text-muted-foreground'>Webhook URL</label>
            <Input value={config.webhook?.url || ''} onChange={(e) => update(['webhook', 'url'], e.target.value)} />
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
            <div className='flex items-center justify-between gap-3'>
              <label className='text-sm text-muted-foreground'>Webhook Body (YAML 或 JSON)</label>
              <Button type='button' variant='secondary' onClick={onTestWebhook} disabled={testingWebhook || saving}>
                {testingWebhook ? '测试中...' : '测试 Webhook'}
              </Button>
            </div>
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
            {webhookNotice ? <p className='text-sm text-muted-foreground'>{webhookNotice}</p> : null}
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
            <Input value={config.web?.admin_username || 'admin'} onChange={(e) => update(['web', 'admin_username'], e.target.value)} />
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
