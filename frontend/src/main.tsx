import "flatpickr/dist/flatpickr.css";
import "jsvectormap/dist/jsvectormap.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "simplebar-react/dist/simplebar.min.css";
import "swiper/swiper-bundle.css";
import App from "./App.tsx";
import { AuthProvider } from "./auth/AuthContext";
import { AppWrapper } from "./components/common/PageMeta.tsx";
import { LanguageProvider } from "./context/LanguageContext.tsx";
import { ThemeProvider } from "./context/ThemeContext.tsx";
import "./i18n";
import "./index.css";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <LanguageProvider>
          <AuthProvider>
            <AppWrapper>
              <App />
            </AppWrapper>
          </AuthProvider>
        </LanguageProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
