import { getAllIssues } from "../lib/issues.ts";

export async function GET(context) {
  const issues = getAllIssues();
  const siteUrl = context.site?.toString().replace(/\/$/, "") ?? "";
  const items = issues
    .map(
      (issue) => `
    <item>
      <title>tentac — ${issue.week}</title>
      <link>${siteUrl}/w/${issue.week}</link>
      <guid>${siteUrl}/w/${issue.week}</guid>
      <pubDate>${new Date(issue.generated_at).toUTCString()}</pubDate>
      <description><![CDATA[${issue.headline}]]></description>
    </item>`
    )
    .join("");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>tentac</title>
  <link>${siteUrl}</link>
  <description>A weekly digest of what happened in AI, picked and summarized by Claude.</description>
  ${items}
</channel></rss>`;

  return new Response(body, { headers: { "Content-Type": "application/xml" } });
}
