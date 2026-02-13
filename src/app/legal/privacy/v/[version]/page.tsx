import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import { fetchPublicPrivacyPolicy, formatEffectiveDate } from "@/lib/legal";
import AdminLegalActions from "@/components/legal/AdminLegalActions";

type PrivacyVersionPageProps = {
  params: Promise<{ version: string }>;
};

export default async function PrivacyPolicyVersionPage({ params }: PrivacyVersionPageProps) {
  const { version } = await params;
  const doc = await fetchPublicPrivacyPolicy(version);

  return (
    <main className="min-h-screen bg-background-light dark:bg-background-dark">
      <section className="max-w-4xl mx-auto px-6 py-12">
        <div className="mb-6">
          <h1 className="text-3xl md:text-4xl font-black font-display text-[#111318] dark:text-white">Privacy Policy</h1>
          <p className="text-sm text-slate-500 mt-2">
            Effective date: {formatEffectiveDate(doc.effective_at)} | Version: {doc.version}
          </p>
        </div>
        <AdminLegalActions docKey="privacy_policy" />
        <article suppressHydrationWarning className="prose prose-slate dark:prose-invert max-w-none markdown-math">
          <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
            {doc.content_md}
          </ReactMarkdown>
        </article>
      </section>
    </main>
  );
}
