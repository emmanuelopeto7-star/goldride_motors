/** Shaped like a real CarCard - same border, same 4:3, same 16px body - so
 *  nothing moves when the data lands. */
function CardSkeleton() {
  return (
    <div className="border border-line bg-surface">
      <div className="aspect-[4/3] animate-pulse bg-line" />
      <div className="space-y-3 p-4">
        <div className="h-5 w-32 animate-pulse bg-line" />
        <div className="h-4 w-44 animate-pulse bg-line" />
      </div>
    </div>
  )
}

export default CardSkeleton
