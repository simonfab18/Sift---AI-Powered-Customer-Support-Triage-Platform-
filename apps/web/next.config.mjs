/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      { source: "/app", destination: "/dashboard", permanent: false },
      { source: "/app/inbox", destination: "/dashboard/tickets", permanent: false },
      { source: "/app/inbox/:ticketId", destination: "/dashboard/tickets/:ticketId", permanent: false },
      { source: "/app/approvals", destination: "/dashboard/tickets", permanent: false },
      { source: "/app/customers", destination: "/dashboard/tickets", permanent: false },
      { source: "/app/analytics", destination: "/dashboard/analytics", permanent: false },
      { source: "/app/integrations", destination: "/dashboard/settings/gmail", permanent: false },
      { source: "/app/settings", destination: "/dashboard/settings", permanent: false },
      { source: "/app/settings/workspace", destination: "/dashboard/settings/workspace", permanent: false },
      { source: "/app/settings/roles", destination: "/dashboard/settings/team", permanent: false },
      { source: "/app/team", destination: "/dashboard/settings/team", permanent: false },
      { source: "/app/knowledge", destination: "/dashboard/settings/knowledge", permanent: false },
      { source: "/app/automation", destination: "/dashboard/settings/routing", permanent: false },
      { source: "/app/:path*", destination: "/dashboard", permanent: false },
    ];
  },
};

export default nextConfig;