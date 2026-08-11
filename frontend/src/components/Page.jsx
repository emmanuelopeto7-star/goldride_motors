/** The §3.4 container: 1440px max, 48px padding desktop / 20px mobile. */
function Page({ children }) {
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-16 lg:px-12">{children}</div>
  )
}

export default Page
