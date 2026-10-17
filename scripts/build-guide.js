const fs = require('fs');
const path = require('path');
const MarkdownIt = require('markdown-it');
const mdAnchor = require('markdown-it-anchor');
const { chromium } = require('@playwright/test');

const CALLOUT_OPEN = /^<div class="(step|expected|warning|tip|note|troubleshoot)">\s*$/;

// markdown-it, incluso con html:true, corta los bloques HTML en la primera
// línea en blanco y no procesa el markdown interior. Esta regla consume el
// <div class="..."> ... </div> completo, emite el div de apertura/cierre y
// tokeniza el contenido interior como markdown normal, de modo que listas,
// negritas e imágenes funcionen dentro de las cajas paso/advertencia/consejo.
function stepDivPlugin(md) {
  function stepDiv(state, startLine, endLine, silent) {
    const pos = state.bMarks[startLine] + state.tShift[startLine];
    const max = state.eMarks[startLine];
    const line = state.src.slice(pos, max).trim();
    const match = line.match(CALLOUT_OPEN);
    if (!match) return false;
    if (silent) return true;

    const className = match[1];
    let nextLine = startLine + 1;
    let closed = false;
    while (nextLine < endLine) {
      const lPos = state.bMarks[nextLine] + state.tShift[nextLine];
      const lMax = state.eMarks[nextLine];
      const lText = state.src.slice(lPos, lMax);
      if (lText.trim() === '</div>') {
        closed = true;
        nextLine++;
        break;
      }
      nextLine++;
    }
    if (!closed) return false;

    const open = state.push('html_block', '', 0);
    open.content = `<div class="${className}">\n`;
    open.block = true;

    state.md.block.tokenize(state, startLine + 1, nextLine - 1);

    const close = state.push('html_block', '', 0);
    close.content = '</div>\n';
    close.block = true;

    state.line = nextLine;
    return true;
  }

  md.block.ruler.before('fence', 'step_div', stepDiv, {
    alt: ['paragraph', 'reference', 'blockquote', 'list'],
  });
}

function buildToc(html) {
  const headingRe = /<h([12])\s+id="([^"]+)"[^>]*>([\s\S]*?)<\/h\1>/g;
  const items = [];
  let m;
  while ((m = headingRe.exec(html)) !== null) {
    items.push({
      level: Number(m[1]),
      id: m[2],
      text: m[3].replace(/<[^>]+>/g, '').trim(),
    });
  }

  let out = '<ul class="toc-list">\n';
  let inSub = false;
  for (const it of items) {
    if (it.level === 1) {
      if (inSub) { out += '</ul></li>\n'; inSub = false; }
      out += `<li><a href="#${it.id}">${it.text}</a>`;
    } else {
      if (!inSub) { out += '\n<ul>'; inSub = true; }
      out += `<li><a href="#${it.id}">${it.text}</a></li>`;
    }
  }
  if (inSub) out += '</ul></li>\n';
  out += '</ul>';
  return out;
}

async function build() {
  const guideDir = path.join(__dirname, '..', 'docs', 'guia-usuario');
  const mdFiles = fs.readdirSync(guideDir)
    .filter(f => f.match(/^\d+-.*\.md$/))
    .sort();

  const md = new MarkdownIt({ html: true, linkify: true });
  md.use(mdAnchor);
  md.use(stepDivPlugin);

  let htmlContent = '';
  for (const file of mdFiles) {
    const raw = fs.readFileSync(path.join(guideDir, file), 'utf-8').replace(/^\uFEFF/, '');
    htmlContent += md.render(raw);
    htmlContent += '\n<div class="page-break"></div>\n';
  }

  const dateStr = new Date().toISOString().slice(0, 10);
  const coverHtml = `
<div class="cover">
  <div class="cover-title">Guía de usuario</div>
  <div class="cover-sub">ContaFis · Cumplimiento fiscal, parafiscal y documental (Venezuela)</div>
  <div class="cover-meta">Módulo <code>l10n_ve_compliance_manager</code> · Odoo 19.0<br>Versión 1.0 · ${dateStr}</div>
</div>`;

  const tocHtml = `
<div class="toc">
  <div class="toc-title">Contenido</div>
  ${buildToc(htmlContent)}
</div>`;

  const body = coverHtml + tocHtml + htmlContent;

  const cssPath = path.join(guideDir, 'assets', 'css', 'guide.css');
  const css = fs.readFileSync(cssPath, 'utf-8');

  const html = `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Guía de usuario — ContaFis</title>
<style>${css}</style>
</head>
<body>
${body}
</body>
</html>`;

  const tmpHtml = path.join(guideDir, '_build.html');
  fs.writeFileSync(tmpHtml, html);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + tmpHtml, { waitUntil: 'load' });
  await page.pdf({
    path: path.join(guideDir, 'guia-usuario.pdf'),
    format: 'A4',
    printBackground: true,
    margin: { top: '2cm', bottom: '2cm', left: '1.8cm', right: '1.8cm' },
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: '<div style="font-size:9px;width:100%;text-align:center;color:#888;">Página <span class="pageNumber"></span> de <span class="totalPages"></span></div>',
  });
  await browser.close();

  fs.unlinkSync(tmpHtml);
  console.log('✓ PDF generado: docs/guia-usuario/guia-usuario.pdf');
}

if (require.main === module) {
  build().catch(err => { console.error(err); process.exit(1); });
}

module.exports = { stepDivPlugin };
