import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { TopBar } from "./components/TopBar";
import { ApplicationDetail } from "./pages/ApplicationDetail";
import { Dashboard } from "./pages/Dashboard";
import { MasterCv } from "./pages/MasterCv";
import { NewApplication } from "./pages/NewApplication";
import { SettingsPage } from "./pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-canvas">
        <TopBar />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/new" element={<NewApplication />} />
          <Route path="/master" element={<MasterCv />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/applications/:id" element={<ApplicationDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
