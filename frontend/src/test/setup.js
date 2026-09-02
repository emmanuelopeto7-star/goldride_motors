import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest does not do this for us. Without it a query in one test can find a
// node another test left mounted, and the failure appears in the wrong place.
afterEach(cleanup)
