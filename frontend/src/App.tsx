import { Routes, Route } from 'react-router-dom'
import { LoginPage } from '@/pages/LoginPage'
import { SignupPage } from '@/pages/SignupPage'
import { ChatHome } from '@/pages/ChatHome'
import { ChatPage } from '@/pages/ChatPage'
import { AppLayout } from '@/components/AppLayout'
import { RequireAuth } from '@/components/RequireAuth'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<ChatHome />} />
          <Route path="/chat/:threadId" element={<ChatPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
