import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Sources from './pages/Sources'
import SourceDetail from './pages/SourceDetail'
import DocumentDetail from './pages/DocumentDetail'
import CrawlJobs from './pages/CrawlJobs'
import CrawlDetail from './pages/CrawlDetail'
import SnippetDetail from './pages/SnippetDetail'
import Upload from './pages/Upload'

function App() {
  return (
    <>
      <Toaster />
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="search" element={<Search />} />
          <Route path="sources" element={<Sources />} />
          <Route path="sources/:id" element={<SourceDetail />} />
          <Route path="sources/:sourceId/documents/:documentId" element={<DocumentDetail />} />
          <Route path="crawl" element={<CrawlJobs />} />
          <Route path="crawl/:id" element={<CrawlDetail />} />
          <Route path="snippets/:id" element={<SnippetDetail />} />
          <Route path="upload" element={<Upload />} />
        </Route>
      </Routes>
    </>
  )
}

export default App