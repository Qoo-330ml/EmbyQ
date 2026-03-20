import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { apiRequest } from '@/types/api'

export default function InviteRegisterPage() {
  const { code } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [invite, setInvite] = useState(null)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const data = await apiRequest(`/public/invite/${code}`)
        setInvite(data.invite)
      } catch (e) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    if (code) load()
  }, [code])

  const onSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      const data = await apiRequest(`/public/invite/${code}/register`, {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })

      const redirectUrl = data.redirect_url
      if (redirectUrl) {
        window.location.href = redirectUrl
        return
      }

      navigate('/')
    } catch (e2) {
      setError(e2.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className='flex min-h-screen items-center justify-center p-4'>
      <Card className='w-full max-w-md'>
        <CardHeader>
          <CardTitle>邀请注册</CardTitle>
          <CardDescription>
            {invite ? `邀请码：${invite.code}` : '加载邀请信息中...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? <p className='text-sm text-muted-foreground'>加载中...</p> : null}
          {error ? <p className='mb-3 text-sm text-destructive'>{error}</p> : null}

          {!loading && !error ? (
            <form className='space-y-4' onSubmit={onSubmit}>
              <div className='space-y-2'>
                <label className='text-sm text-muted-foreground'>用户名</label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
              </div>
              <div className='space-y-2'>
                <label className='text-sm text-muted-foreground'>密码（可不填，默认=用户名）</label>
                <Input type='password' value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <Button type='submit' className='w-full' disabled={submitting}>
                {submitting ? '提交中...' : '创建账号并跳转 Emby'}
              </Button>
            </form>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
