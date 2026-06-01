import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import './global.css';
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
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          // Warm neutral palette
          colorPrimary: '#e8653a',
          colorBgContainer: '#ffffff',
          colorBgLayout: '#f4f3f1',
          colorBorder: '#eae8e4',
          colorBorderSecondary: '#f0eeeb',
          colorText: '#1a1a1a',
          colorTextSecondary: '#6b6560',
          colorTextTertiary: '#a09a94',
          borderRadius: 8,
          borderRadiusLG: 12,
          fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
          fontSize: 14,
          controlHeight: 38,
          // Shadows — warm tinted
          boxShadow: '0 1px 3px rgba(30,27,22,0.04), 0 4px 12px rgba(30,27,22,0.03)',
          boxShadowSecondary: '0 4px 16px rgba(30,27,22,0.06)',
        },
        components: {
          Table: {
            headerBg: '#fafaf8',
            headerColor: '#6b6560',
            borderColor: '#f0eeeb',
            rowHoverBg: '#fafaf8',
          },
          Card: {
            headerFontSize: 16,
          },
          Menu: {
            darkItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(255,255,255,0.08)',
            darkItemHoverBg: 'rgba(255,255,255,0.04)',
          },
          Button: {
            primaryShadow: '0 1px 2px rgba(232,101,58,0.15)',
          },
          Tag: {
            defaultBg: '#f4f3f1',
          },
          Input: {
            activeBorderColor: '#e8653a',
            hoverBorderColor: '#d4572e',
          },
        },
      }}
    >
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
