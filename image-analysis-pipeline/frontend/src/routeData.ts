import { defineRouteMiddleware } from '@astrojs/starlight/route-data';

// The install guide keeps "Prerequisites" and "Installation" as h3s inside the
// platform tabs, so Starlight's h2-only TOC skips them. Add both to the sidebar's
// "On this page" list, between "Before You Start" and "Updating the Application".
// Sidebar.astro points each link at the heading in whichever tab is open.
export const onRequest = defineRouteMiddleware((context) => {
  const route = context.locals.starlightRoute;
  if (route.entry.id !== 'docs/install' || !route.toc) return;

  const items = route.toc.items;
  const updating = items.findIndex((item) => item.slug === 'updating-the-application');
  items.splice(updating >= 0 ? updating : items.length, 0,
    { depth: 2, slug: 'prerequisites', text: 'Prerequisites', children: [] },
    { depth: 2, slug: 'installation', text: 'Installation', children: [] },
  );

  // Let the TOC's scroll tracking watch h3s too, so these links highlight.
  route.toc.maxHeadingLevel = 3;
});
