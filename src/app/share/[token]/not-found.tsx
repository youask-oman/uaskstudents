export default function SharedSolutionNotFound() {
  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-6">
      <div className="max-w-md w-full rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-bold text-slate-800 mb-2">Shared solution unavailable</h1>
        <p className="text-sm text-slate-500 mb-6">
          This shared solution is unavailable. The link may be invalid, expired, or revoked.
        </p>
        <a
          href="/solve"
          className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold"
        >
          Go to Solve
        </a>
      </div>
    </div>
  );
}

