import { Outlet } from 'react-router-dom'

function Layout() {
    return (
         <div className="min-h-screen bg-page text-ink">
      <header className="sticky top-0 z-50 h-[72px] border-b border-line bg-surface">
        <div className="mx-auto flex h-full max-w-[1440px] items-center px-5 lg:px-12">
          <span className="font-serif text-[22px] tracking-[0.08em]">
            GOLDRIDE
          </span>
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
    )
}

export default Layout