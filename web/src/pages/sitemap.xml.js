import { getAllIssues } from "../lib/issues.ts";

export async function GET(context) {
  const issues = getAllIssues();
  const siteUrl = context.site?.toString().replace(/\/$/, "") ?? "";
  const latestModified = issues[0]?.generated_at ?? new Date().toISOString();

  const staticUrls = [
    { loc: `${siteUrl}/`, lastmod: latestModified },
    { loc: `${siteUrl}/archive`, lastmod: latestModified },
  ];

  const issueUrls = issues.map((issue) => ({
    loc: `${siteUrl}/w/${issue.week}`,
    lastmod: issue.generated_at,
  }));

  const urls = [...staticUrls, ...issueUrls]
    .map(
      (u) => `
  <url>
    <loc>${u.loc}</loc>
    <lastmod>${new Date(u.lastmod).toISOString()}</lastmod>
  </url>`
    )
    .join("");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}
</urlset>`;

  return new Response(body, { headers: { "Content-Type": "application/xml" } });
}
