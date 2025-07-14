import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Sources from './pages/Sources'
import SourceDetail from './pages/SourceDetail'
import CrawlJobs from './pages/CrawlJobs'
import CrawlDetail from './pages/CrawlDetail'
import SnippetDetail from './pages/SnippetDetail'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="search" element={<Search />} />
        <Route path="sources" element={<Sources />} />
        <Route path="sources/:id" element={<SourceDetail />} />
        <Route path="crawl" element={<CrawlJobs />} />
        <Route path="crawl/:id" element={<CrawlDetail />} />
        <Route path="snippets/:id" element={<SnippetDetail />} />
      </Route>
    </Routes>
  )
}

export default App