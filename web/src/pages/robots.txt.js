export async function GET(context) {
  const siteUrl = context.site?.toString().replace(/\/$/, "") ?? "";
  const body = `User-agent: *
Allow: /

Sitemap: ${siteUrl}/sitemap.xml
`;
  return new Response(body, { headers: { "Content-Type": "text/plain" } });
}
