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
import ModelConfigPage from '@/pages/model-config';
import ProcessingTasksPage from '@/pages/processing-tasks';
import UserPage from '@/pages/system/users';
import RolePage from '@/pages/system/roles';
import MenuManagementPage from '@/pages/system/menus';
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
          colorPrimary: '#3f6f8f',
          colorInfo: '#3f6f8f',
          colorSuccess: '#547b63',
          colorWarning: '#b9893a',
          colorError: '#b84b44',
          colorBgContainer: '#ffffff',
          colorBgElevated: '#ffffff',
          colorBgLayout: '#f4f7fa',
          colorBorder: '#d9e1e8',
          colorBorderSecondary: '#e7edf2',
          colorText: '#202a34',
          colorTextSecondary: '#667482',
          colorTextTertiary: '#96a2ae',
          borderRadius: 8,
          borderRadiusLG: 10,
          fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
          fontSize: 14,
          controlHeight: 38,
          boxShadow: '0 10px 30px rgba(25, 39, 52, 0.08)',
          boxShadowSecondary: '0 18px 45px rgba(25, 39, 52, 0.12)',
        },
        components: {
          Table: {
            headerBg: '#eef3f6',
            headerColor: '#667482',
            borderColor: '#e7edf2',
            rowHoverBg: '#f1f5f8',
            cellPaddingBlock: 14,
          },
          Card: {
            headerFontSize: 16,
            colorBorderSecondary: '#e7edf2',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(63,111,143,0.18)',
            darkItemHoverBg: 'rgba(255,255,255,0.07)',
            darkItemColor: 'rgba(248,251,253,0.68)',
            darkItemSelectedColor: '#f8fbfd',
          },
          Button: {
            primaryShadow: '0 10px 22px rgba(63,111,143,0.18)',
          },
          Tag: {
            defaultBg: '#f1f5f8',
          },
          Input: {
            activeBorderColor: '#3f6f8f',
            hoverBorderColor: '#315974',
          },
          Select: {
            optionSelectedBg: '#e8f0f5',
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
            <Route path="model-config" element={<ModelConfigPage />} />
            <Route path="processing-tasks" element={<ProcessingTasksPage />} />
            <Route path="system/users" element={<UserPage />} />
            <Route path="system/roles" element={<RolePage />} />
            <Route path="system/menus" element={<MenuManagementPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
