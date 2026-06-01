import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AdminLayout from '@/layouts/AdminLayout';
import LoginPage from '@/pages/login';
import KnowledgePage from '@/pages/knowledge';
import ChatPage from '@/pages/chat';
import DomainPage from '@/pages/domain';
import UserPage from '@/pages/system/users';
import RolePage from '@/pages/system/roles';
import { isAuthenticated } from '@/utils/auth';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/knowledge" replace />} />
            <Route path="knowledge" element={<KnowledgePage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="domain" element={<DomainPage />} />
            <Route path="system/users" element={<UserPage />} />
            <Route path="system/roles" element={<RolePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
