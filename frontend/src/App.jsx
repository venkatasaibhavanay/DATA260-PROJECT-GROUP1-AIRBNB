import { Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'
import HomePage from './pages/HomePage.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'
import UsersPage from './pages/users/UsersPage.jsx'
import PropertiesPage from './pages/properties/PropertiesPage.jsx'
import BookingsPage from './pages/bookings/BookingsPage.jsx'
import MessagingReviewsPage from './pages/messaging-reviews/MessagingReviewsPage.jsx'
import AiPage from './pages/ai/AiPage.jsx'
import AnalyticsPage from './pages/analytics/AnalyticsPage.jsx'

export default function App() {
  return (
    <>
      <NavBar />
      <main className="container">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/properties" element={<PropertiesPage />} />
          <Route path="/bookings" element={<BookingsPage />} />
          <Route path="/messaging-reviews" element={<MessagingReviewsPage />} />
          <Route path="/ai" element={<AiPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </>
  )
}
