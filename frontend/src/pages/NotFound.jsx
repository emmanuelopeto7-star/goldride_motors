import { Link } from 'react-router-dom'
import Page from '../components/Page'

function NotFound() {
  return (
    <Page>
      <div className="border border-line bg-surface p-12 text-center">
        <p className="font-serif text-h1">404</p>
        <p className="mt-3 text-model text-ink-soft">That page does not exist.</p>
        <Link to="/" className="mt-8 inline-block text-meta text-ink underline">
          Back to all cars
        </Link>
      </div>
    </Page>
  )
}

export default NotFound
