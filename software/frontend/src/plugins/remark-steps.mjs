// Turns each "## Step N: Title" (and "## Local Step N: Title") section into
// <section class="step" data-step="NN"> so CSS can draw the numbered badge and the
// dashed connector. The heading keeps its original anchor id (links like
// #step-1-download-the-training-dataset or #local-step-6-install-nnunetv2-and-dependencies)
// but the visible "Step N:" prefix is dropped, since the badge carries the number.
//
// Training page only: when the page has both a VM walkthrough ("Step 1" up to the
// "Alternative: Train on a Local Machine" heading) and a local walkthrough (that heading up
// to "Alternative: Full Retrain"), each one is wrapped in a .training-path container and a
// two-button toggle is inserted before the first h2. The script that shows one path at a time
// lives in src/components/starlight/Sidebar.astro.
import GithubSlugger from 'github-slugger';

const STEP = /^(?:Local )?Step (\d+):\s*/;
const LOCAL_START = /^Alternative: Train on a Local Machine/;
const LOCAL_END = /^Alternative: Full Retrain/;
const text = (node) =>
  node.children.map((c) => (c.type === 'text' || c.type === 'inlineCode' ? c.value : text(c))).join('');

// Build an element from an mdast-style node (data.hName decides the tag).
const el = (hName, hProperties, children = []) => ({ type: 'path-el', data: { hName, hProperties }, children });
const txt = (value) => ({ type: 'text', value });

const PATHS = [
  { key: 'vm', label: 'Training on a VM' },
  { key: 'local', label: 'Training on a Local Machine' },
];

const toggle = () =>
  el(
    'div',
    { className: ['path-toggle'], role: 'tablist', 'aria-label': 'Where are you training?' },
    PATHS.map((p) =>
      el(
        'button',
        {
          type: 'button',
          role: 'tab',
          id: `training-tab-${p.key}`,
          'aria-controls': `training-path-${p.key}`,
          'aria-selected': 'false',
          'data-path': p.key,
        },
        [txt(p.label)],
      ),
    ),
  );

export default function remarkSteps() {
  return (tree) => {
    const nodes = tree.children;

    // Which top-level nodes belong to the VM / local walkthrough (training page only).
    const h2Index = (test) =>
      nodes.findIndex((n) => n.type === 'heading' && n.depth === 2 && test(text(n)));
    const vmStart = h2Index((t) => /^Step 1:/.test(t));
    const localStart = h2Index((t) => LOCAL_START.test(t));
    const localEnd = h2Index((t) => LOCAL_END.test(t));
    const grouped = vmStart >= 0 && localStart > vmStart && localEnd > localStart;
    const pathOf = (i) =>
      !grouped ? null : i >= vmStart && i < localStart ? 'vm' : i >= localStart && i < localEnd ? 'local' : null;

    const out = [];
    const slugger = new GithubSlugger();
    let current = null;
    let group = null; // { key, node }
    let toggled = false;

    nodes.forEach((node, i) => {
      const key = pathOf(i);
      if (key !== (group?.key ?? null)) {
        current = null;
        group = null;
        if (key) {
          group = {
            key,
            node: el(
              'div',
              {
                className: ['training-path'],
                id: `training-path-${key}`,
                role: 'tabpanel',
                'aria-labelledby': `training-tab-${key}`,
                'data-path': key,
              },
              [],
            ),
          };
          out.push(group.node);
        }
      }
      const target = group ? group.node.children : out;

      // The toggle goes right before the first h2 (after the intro paragraph).
      if (grouped && !toggled && node.type === 'heading' && node.depth === 2) {
        out.push(toggle());
        toggled = true;
      }

      if (node.type === 'heading' && node.depth === 2) {
        const label = text(node);
        const m = label.match(STEP);
        const id = slugger.slug(label);
        if (m) {
          node.data = { ...node.data, hProperties: { ...(node.data?.hProperties ?? {}), id } };
          const first = node.children[0];
          if (first?.type === 'text') first.value = first.value.replace(STEP, '');
          current = {
            type: 'step-section',
            data: {
              hName: 'section',
              hProperties: { className: ['step'], 'data-step': m[1].padStart(2, '0') },
            },
            children: [node],
          };
          target.push(current);
          return;
        }
        current = null;
      }
      if (current) current.children.push(node);
      else target.push(node);
    });
    tree.children = out;
  };
}
