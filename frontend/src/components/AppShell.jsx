import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { FileText, Heart, Info, Moon, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { apiRequest } from '@/types/api'

const navItems = [
  { to: '/', label: '首页' },
  { to: '/admin/users', label: '管理后台' },
]

const adminSubNav = [
  { to: '/admin/users', label: '用户' },
  { to: '/admin/wishes', label: '求片' },
  { to: '/admin/config', label: '配置' },
  { to: '/admin/groups', label: '用户组' },
]

export default function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const [theme, setTheme] = useState(() => localStorage.getItem('emby-ui-theme') || 'light')
  const [version, setVersion] = useState('')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('emby-ui-theme', theme)
  }, [theme])

  useEffect(() => {
    const loadVersion = async () => {
      try {
        const response = await fetch('/VERSION')
        const text = await response.text()
        setVersion(text.trim())
      } catch (error) {
        console.error('加载版本号失败:', error)
      }
    }
    loadVersion()
  }, [])

  const toggleTheme = () => {
    setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
  }

  const logout = async () => {
    try {
      await apiRequest('/auth/logout', { method: 'POST' })
    } catch (error) {
      console.error('退出登录失败:', error)
    }
    navigate('/login')
  }

  const isAdminRoute = location.pathname.startsWith('/admin')

  return (
    <div className='min-h-screen bg-background'>
      <header className='sticky top-0 z-40 border-b bg-background/90 backdrop-blur'>
        <div className='mx-auto flex h-14 max-w-7xl items-center justify-between px-4 md:px-8'>
          <Link to='/' className='flex items-center gap-0 text-sm font-semibold tracking-wide text-primary'>
            <img src='/logo.svg' alt='EmbyQ' className='h-8 w-auto' />
            {version ? <span className='text-xs text-muted-foreground'>v{version}</span> : null}
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
            {isAdminRoute ? (
              <>
                <Link to='/admin/wishes'>
                  <Button size='icon' variant='outline' title='求片管理'>
                    <Heart className='h-4 w-4' />
                  </Button>
                </Link>
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
        {isAdminRoute ? (
          <div className='mx-auto flex max-w-7xl flex-wrap gap-2 px-4 pb-3 md:px-8'>
            {adminSubNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm transition-colors ${
                    isActive ? 'bg-primary text-primary-foreground' : 'bg-accent text-foreground hover:bg-accent/80'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        ) : null}
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  )
}
