import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Moon, Sun, Info, FileText } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { apiRequest } from '@/types/api'

const navItems = [
  { to: '/', label: '首页' },
  { to: '/admin/users', label: '管理后台' },
]

const adminSubNav = [
  { to: '/admin/users', label: '用户' },
  { to: '/admin/config', label: '配置' },
  { to: '/admin/groups', label: '用户组' },
]

export default function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const [theme, setTheme] = useState('light')
  const [version, setVersion] = useState('')

  useEffect(() => {
    const saved = localStorage.getItem('emby-ui-theme')
    const initial = saved || 'light'
    setTheme(initial)
    document.documentElement.classList.toggle('dark', initial === 'dark')
  }, [])

  useEffect(() => {
    const loadVersion = async () => {
      try {
        const response = await fetch('/VERSION')
        const text = await response.text()
        setVersion(text.trim())
      } catch (e) {
        console.error('加载版本号失败:', e)
      }
    }
    loadVersion()
  }, [])

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('emby-ui-theme', next)
    document.documentElement.classList.toggle('dark', next === 'dark')
  }

  const logout = async () => {
    try {
      await apiRequest('/auth/logout', { method: 'POST' })
    } catch (e) {
      // ignore
    }
    navigate('/login')
  }

  return (
    <div className='min-h-screen bg-background'>
      <header className='sticky top-0 z-40 border-b bg-background/90 backdrop-blur'>
        <div className='mx-auto flex h-14 max-w-7xl items-center justify-between px-4 md:px-8'>
          <Link to='/' className='flex items-center gap-0 text-sm font-semibold tracking-wide text-primary'>
            <img src='/logo.svg' alt='EmbyQ' className='h-8 w-auto' />
            {version && <span className='text-xs text-muted-foreground'>v{version}</span>}
          </Link>
          <nav className='hidden items-center gap-2 md:flex'>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm transition-colors ${
                    isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className='flex items-center gap-2'>
            {location.pathname.startsWith('/admin') ? (
              <>
                <Button size='sm' variant='destructive' onClick={logout}>
                  退出
                </Button>
                <Link to='/admin/logs'>
                  <Button size='icon' variant='outline' title='日志'>
                    <FileText className='h-4 w-4' />
                  </Button>
                </Link>
              </>
            ) : null}
            <Button size='icon' variant='outline' onClick={toggleTheme} title='切换主题'>
              {theme === 'dark' ? <Sun className='h-4 w-4' /> : <Moon className='h-4 w-4' />}
            </Button>
            <Link to='/about'>
              <Button size='icon' variant='outline' title='关于'>
                <Info className='h-4 w-4' />
              </Button>
            </Link>
          </div>
        </div>
        <div className='mx-auto flex max-w-7xl gap-2 px-4 pb-3 md:hidden'>
          {navItems.map((item) => (
            <NavLink
              key={`mobile-${item.to}`}
              to={item.to}
              className={({ isActive }) =>
                `flex-1 rounded-md px-3 py-1.5 text-center text-sm transition-colors ${
                  isActive ? 'bg-primary text-primary-foreground' : 'bg-accent text-foreground'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  )
}
