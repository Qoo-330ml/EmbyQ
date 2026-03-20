import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AppShell from '@/components/AppShell'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'
import SearchPage from '@/pages/SearchPage'
import AdminPage from '@/pages/AdminPage'
import ConfigPage from '@/pages/ConfigPage'
import GroupsPage from '@/pages/GroupsPage'
import InviteRegisterPage from '@/pages/InviteRegisterPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path='/login' element={<LoginPage />} />
        <Route path='/invite/:code' element={<InviteRegisterPage />} />

        <Route path='/' element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path='search' element={<SearchPage />} />
          <Route path='admin' element={<Navigate to='/admin/users' replace />} />
          <Route path='admin/users' element={<AdminPage />} />
          <Route path='admin/config' element={<ConfigPage />} />
          <Route path='admin/groups' element={<GroupsPage />} />
        </Route>

        <Route path='*' element={<Navigate to='/' replace />} />
      </Routes>
    </BrowserRouter>
  )
}
