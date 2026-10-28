import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import remarkSteps from './src/plugins/remark-steps.mjs';
import { readFileSync } from 'node:fs';

// Scroll effects (reveal on scroll, progress bar, smooth anchors), inlined in <head>.
// The landing page inlines the same file; see src/scripts/scroll-effects.js.
const scrollEffects = readFileSync(new URL('./src/scripts/scroll-effects.js', import.meta.url), 'utf8');

// Deployed to GitHub Pages. Never hard-code root-relative links; build them
// from import.meta.env.BASE_URL.
const base = '/ArabidopsisAnalysisV2';

export default defineConfig({
  site: 'https://calvinyong1.github.io',
  base,
  // The old Jekyll site served .html URLs; those are static meta-refresh files in public/.
  markdown: { remarkPlugins: [remarkSteps] },
  integrations: [
    starlight({
      title: 'ArabidopsisAnalysisV2',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/calvinyong1/ArabidopsisAnalysisV2' },
      ],
      components: {
        Header: './src/components/starlight/Header.astro',
        Sidebar: './src/components/starlight/Sidebar.astro',
        PageSidebar: './src/components/starlight/PageSidebar.astro',
        PageTitle: './src/components/starlight/PageTitle.astro',
        MobileMenuFooter: './src/components/starlight/MobileMenuFooter.astro',
      },
      pagefind: false,
      routeMiddleware: './src/routeData.ts',
      expressiveCode: {
        themes: ['github-dark'],
        useStarlightUiThemeColors: false,
        useStarlightDarkModeSwitch: false,
        styleOverrides: {
          borderRadius: '4px',
          borderColor: '#14201A',
          codeBackground: '#14201A',
          codeForeground: '#E8EEE9',
          codeFontFamily: "'IBM Plex Mono', ui-monospace, monospace",
          codeFontSize: '14px',
          frames: {
            frameBoxShadowCssValue: 'none',
            terminalBackground: '#14201A',
            terminalTitlebarBackground: '#1E2B24',
            terminalTitlebarForeground: '#B5C2B9',
            terminalTitlebarBorderBottomColor: '#3A4A40',
            editorTabBarBackground: '#1E2B24',
            editorActiveTabBackground: '#14201A',
            editorActiveTabForeground: '#B5C2B9',
            editorTabBarBorderBottomColor: '#3A4A40',
            editorActiveTabBorderColor: 'transparent',
            editorActiveTabIndicatorTopColor: 'transparent',
            editorActiveTabIndicatorBottomColor: 'transparent',
          },
        },
      },
      customCss: ['./src/styles/tokens.css', './src/styles/starlight.css'],
      head: [
        { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
        { tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' } },
        {
          tag: 'link',
          attrs: { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@600;700&display=swap' },
        },
        { tag: 'script', content: scrollEffects },
      ],
      sidebar: [
        { label: 'Installation Guide', slug: 'docs/install' },
        { label: 'Image Aligner', slug: 'docs/image-aligner' },
        { label: 'Segmentation', slug: 'docs/segmentation' },
        { label: 'Single Plant Analysis', slug: 'docs/single-plant-analysis' },
        { label: "What's New in This Fork", slug: 'docs/model-and-improvements' },
        { label: 'Training the Model', slug: 'docs/training' },
        { label: 'Architecture Notes', slug: 'docs/architecture' },
      ],
    }),
  ],
});
