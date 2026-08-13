/** The seller's walkthrough, when there is one.
 *
 *  The embed URL is worked out by the API, so this never has to know the
 *  difference between a youtu.be link and a player.vimeo.com one. Renders
 *  nothing at all when the listing has no video - an empty player frame reads
 *  as a broken page.
 */
function VideoWalkthrough({ src, title }) {
  if (!src) return null

  return (
    <section className="mt-12">
      <h2 className="font-serif text-section">Walkthrough</h2>
      <div className="mt-4 aspect-video w-full border border-line bg-surface">
        <iframe
          src={src}
          title={`${title} walkthrough`}
          className="h-full w-full"
          loading="lazy"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          referrerPolicy="strict-origin-when-cross-origin"
          allowFullScreen
        />
      </div>
    </section>
  )
}

export default VideoWalkthrough
